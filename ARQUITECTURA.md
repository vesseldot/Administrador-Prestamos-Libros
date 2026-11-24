# Arquitectura

## 1. Visión general

```
┌──────────────────────────── Interfaz (ui/) ────────────────────────────┐
│ app.py: menú lateral · panel dinámico · pantalla de acceso · avisos    │
│ vistas/: dashboard · libros · busqueda · personas · prestamos ·        │
│          personas_prestamos · configuracion                            │
│ tareas.py: un hilo trabajador + cola → resultados en el hilo de Tk     │
└───────────────┬─────────────────────────────────────────┬──────────────┘
                │ lecturas rápidas (Redis)                │ trabajo pesado (Chroma, modelo)
                ▼                                         ▼
┌──────────────────────── servicios.py · ServicioBiblioteca ─────────────┐
│ altas, lote, actualización y eliminación con compensación ·            │
│ búsqueda enriquecida · préstamos · estadísticas · sincronización       │
└──────┬──────────────┬──────────────┬───────────────┬───────────────────┘
       ▼              ▼              ▼               ▼
 db_catalogo.py  db_personas.py  db_prestamos.py   db_libros.py ──► modelos.py
 (libros)        (cifradas)      (WATCH/MULTI)     (ChromaDB)        (Qwen3, fp16)
       └──────────────┴──────────────┘               │
                Redis (base dedicada, prefijo bib:)   ChromaDB persistente (chroma_db/)
```

Transversales: `config.py` (configuración y validación), `validaciones.py` (reglas), `seguridad.py` (cifrado y acceso), `db_redis.py` (conexión, llaves y bitácora), `gestor_modelos.py` (descarga y validación de modelos).

### Dependencias entre módulos (sin ciclos)

| Módulo | Depende de |
|---|---|
| `config` | — |
| `validaciones` | — |
| `seguridad` | config, cryptography |
| `modelos` | config, sentence-transformers (carga perezosa) |
| `gestor_modelos` | config, modelos, huggingface_hub |
| `db_redis` | config, redis |
| `db_catalogo` | db_redis, validaciones |
| `db_personas` | db_redis, seguridad, validaciones |
| `db_prestamos` | config, db_redis |
| `db_libros` | config, modelos, validaciones, chromadb |
| `servicios` | todos los `db_*`, seguridad, validaciones |
| `ui/*` | **Solo** la API pública de `ServicioBiblioteca` (recibida como `app.servicio`) y `servicios.describir_error`; constantes de `config`; funciones puras de `validaciones` y `seguridad` (listas cerradas, normalización, enmascaramiento, aviso) |
| `demo_interfaz` | servicios, modelo_simulado, fakeredis (modo de demostración en memoria) |
| `modelo_simulado` | validaciones |
| `main` | config, servicios, ui |

## 1.1 Separación frontend / backend

| Capa | Módulos | Responsabilidad |
|---|---|---|
| Interfaz gráfica | `ui/` | Presentación, navegación, formularios y avisos. No accede a bases de datos. |
| Lógica de negocio | `servicios.py` (`ServicioBiblioteca`) | Reglas de préstamos, compensación Redis ↔ Chroma, estadísticas y la **API pública para la interfaz**. |
| Acceso a Redis | `db_redis.py`, `db_catalogo.py`, `db_personas.py`, `db_prestamos.py` | Llaves, transacciones y cifrado de campos. |
| Acceso a ChromaDB | `db_libros.py` | Documentos, metadatos, embeddings y consultas vectoriales. |
| Modelo semántico | `modelos.py`, `gestor_modelos.py` | Carga, descarga, revisión fijada y validación. |
| Seguridad y validaciones | `seguridad.py` (cifrado, `ControlAcceso`), `validaciones.py`, `config.py` | Reglas de datos, autenticación y configuración. |

- **Contrato**: la interfaz solo llama a los métodos públicos de `ServicioBiblioteca` documentados en [INTEGRACION.md](INTEGRACION.md). Los errores se traducen a mensajes con `servicios.describir_error`, de modo que `ui/` no depende de `redis`, `chromadb` ni del modelo.
- **Verificación automática**: `tests/test_arquitectura.py` analiza el código de `ui/` y falla si importa módulos de bases de datos o del modelo, si usa atributos internos del servicio (`r`, `catalogo`, `indice`, `personas`, `prestamos`, `actividad`, `llaves`) o si llama a un método que no existe en la API. También comprueba que el backend no importe `ui` ni `tkinter`.
- **Hilos**: lo que toca ChromaDB o el modelo se ejecuta en el hilo trabajador de `ui/tareas.py`; las operaciones solo de Redis pueden llamarse desde la interfaz (columna «Hilo» de INTEGRACION.md).
- **Desarrollo aislado del frontend**: `demo_interfaz.py` construye el mismo `ServicioBiblioteca` sobre fakeredis, ChromaDB en memoria y `modelo_simulado.py`, sin tocar datos reales.

## 2. Responsabilidad de cada base

| Dato | Redis | ChromaDB |
|---|---|---|
| Identificador del libro | ✔ (fuente de verdad) | ✔ (`ids`) |
| Metadatos del libro | ✔ (fuente de verdad) | ✔ copia en `metadatas` |
| Sinopsis | — | ✔ `documents` |
| Embedding | — | ✔ |
| Disponibilidad | ✔ (fuente de verdad, se cambia de forma atómica en préstamos) | ✔ copia sincronizada |
| Personas | ✔ (cifradas) | — |
| Préstamos e historial | ✔ | — |
| Bitácora de actividad | ✔ | — |

Los resultados de la búsqueda semántica se **enriquecen siempre con Redis**: aunque una copia de metadatos en Chroma quedara atrasada, el estado mostrado y el filtro «solo disponibles» son correctos.

## 3. Modelo de datos en Redis

Base dedicada (`REDIS_DB`, por defecto 2) y prefijo `REDIS_PREFIJO` (por defecto `bib:`). Al arrancar, `preparar_base` verifica que la base no contenga llaves ajenas y marca `bib:meta:esquema = 2`.

| Llave | Tipo | Contenido |
|---|---|---|
| `meta:esquema` | STRING | Versión del esquema (2). |
| `libros` | SET | Ids de todos los libros. |
| `libro:{id}` | HASH | isbn, titulo, autor, anio, editorial, genero, tema, idioma, pasta, paginas, calificacion, disponible (`1`/`0`), fecha_alta, fecha_actualizacion. |
| `idx:isbn:{isbn}` | STRING | Id del libro que usa ese ISBN normalizado (evita duplicados). |
| `libro:{id}:prestamo_activo` | STRING | Id del préstamo activo; como máximo uno por libro. |
| `persona:contador` | STRING | Generador de ids `P0001`… |
| `personas` | SET | Ids de todas las personas. |
| `persona:{id}` | HASH | 13 campos cifrados (`v2:` + AES-GCM), `tipo_usuario` en claro, `correo_hash`, consentimiento y fechas. |
| `idx:correo:{hmac}` | STRING | Id de la persona dueña del correo (índice ciego). |
| `persona:{id}:prestamos_activos` | SET | Préstamos activos de la persona. |
| `persona:{id}:historial` | ZSET | Todos sus préstamos, ordenados por fecha. |
| `prestamo:contador` | STRING | Generador de ids `PR000001`… |
| `prestamo:{id}` | HASH | persona_id, libro_id, titulo, autor, fecha_prestamo, fecha_limite, fecha_devolucion, estado (`activo`/`devuelto`). |
| `prestamos:activos` | SET | Préstamos activos de toda la biblioteca. |
| `prestamos:todos` | ZSET | Todos los préstamos, ordenados por fecha. |
| `personas_con_prestamo` | SET | Personas con al menos un préstamo activo. |
| `actividad` | LIST | Últimos 100 eventos `{fecha, tipo, descripcion, refs}`, solo con identificadores. |
| `sync:pendientes` | SET | Libros cuya copia en Chroma quedó pendiente tras un fallo. |

El estado «vencido» no se almacena: se deriva de `fecha_limite` y lo mismo ocurre con la edad de las personas.

## 4. Modelo de datos en ChromaDB

- Una colección por modelo, `libros_<modelo>` (por ejemplo `libros_qwen3_embedding_0_6b`), con espacio coseno. Cada colección conserva lo que su modelo ya procesó: al cambiar de modelo se compara por sinopsis y solo se calculan los libros nuevos o modificados, se reutiliza el resto y se eliminan los que ya no existen (el modelo activo solo cambia cuando la colección destino queda completa).
- `ids` = id del libro · `documents` = sinopsis · `metadatas` = los 12 campos de metadatos · embeddings calculados por la aplicación (`embedding_function=None`).
- El modelo activo se guarda en `modelo_activo.txt`.

## 5. Modelo semántico

| Parámetro | Valor |
|---|---|
| Modelo | `Qwen/Qwen3-Embedding-0.6B` (1024 dimensiones, *last-token pooling*). |
| Precisión | float16 en GPU (`model_kwargs={"dtype": torch.float16}`); float32 en CPU. |
| Documentos | Sinopsis sin instrucción. |
| Consultas | `Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery:` |
| Longitud máxima | 512 tokens (la sinopsis más larga del catálogo tiene 147). |
| Revisión | `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3` (fijada en `modelos.py`). |
| Licencia | Apache-2.0. |
| Carga | Siempre desde la carpeta local de esa revisión (`gestor_modelos.ruta_local`); nunca descarga de forma implícita. |

La instrucción genérica obtuvo mejores resultados que una instrucción específica para libros (Hit@1 de 90 % frente a 88 %, MRR de 0.944 frente a 0.926). El modelo original del proyecto, `paraphrase-multilingual-MiniLM-L12-v2`, sigue disponible en Configuración (Hit@1 de 82 %). Detalle en [PRUEBAS.md](PRUEBAS.md).

### Distribución del modelo (`gestor_modelos.py`)

Los pesos **no están en el repositorio**:

1. Al iniciar sesión, la aplicación comprueba si la revisión fijada está completa en `BIBLIOTECA_DIR_MODELOS` o, si no se define, en la caché estándar de Hugging Face.
2. Si falta, ofrece descargarla con un diálogo que muestra el tamaño, el destino, el espacio libre y el progreso en bytes. También existe `python gestionar_modelos.py descargar`.
3. `plan_descarga` consulta en el Hub la lista de archivos de esa revisión exacta y descarga solo los necesarios: `*.json`, `*.txt`, `*.model` y `model.safetensors`, sin variantes ONNX, OpenVINO ni TensorFlow. Comprueba antes el espacio libre, con un margen de 300 MB.
4. `hf_hub_download` baja cada archivo a la caché; las descargas interrumpidas solo repiten lo que falta.
5. `validar` carga el modelo y comprueba que produzca vectores de la dimensión esperada (1024).
6. Los errores se distinguen en `SinConexion`, `EspacioInsuficiente` y `ErrorDescarga`, con mensajes para el usuario.

## 6. Flujos principales y consistencia

No existe una transacción distribuida entre Redis y ChromaDB. Cada operación sigue el patrón **validar → escribir en Chroma → confirmar en Redis**, y si algo falla **compensa** el paso anterior:

| Operación | Secuencia | Compensación ante fallo |
|---|---|---|
| Alta | validar campos, id e ISBN únicos → embedding y `upsert` en Chroma → transacción `WATCH` en Redis | Se borra el documento de Chroma. |
| Lote | validar fila por fila (duplicados en el archivo y en la base) → embeddings en lotes de 32 → `MULTI` en Redis | Se borran de Chroma los ids insertados. |
| Actualización | copia previa (con embedding) → `update` en Chroma (re-embedding solo si cambia la sinopsis) → transacción en Redis | Se restaura la copia en Chroma. |
| Eliminación | se bloquea si hay un préstamo activo → copia previa → borrado en Chroma → borrado en Redis | Se reinserta la copia en Chroma. |
| Préstamo | transacción `WATCH/MULTI` en Redis (persona, cupo, libros, préstamos activos) → copia de disponibilidad a Chroma | Si falla la copia, el libro se anota en `sync:pendientes`. |
| Devolución | transacción `WATCH/MULTI` en Redis → copia de disponibilidad a Chroma | Igual que en el préstamo. |

Si la compensación también falla, el id queda en `sync:pendientes`. En **Configuración › Sincronización** se puede:

- **Revisar**: libros sin documento, documentos huérfanos, metadatos distintos y pendientes.
- **Reparar metadatos**: copia a Chroma los metadatos de Redis.
- **Importar documentos huérfanos**: da de alta en Redis lo que solo existe en Chroma. Nunca se borran documentos automáticamente.

Al iniciar sesión se ejecuta una revisión y, si hay diferencias, aparece un aviso.

### Concurrencia

- **Préstamo**: vigila con `WATCH` la persona, su conjunto de préstamos activos, cada libro, su marcador de préstamo activo y el contador. Si otro cliente modifica alguno, la transacción se reintenta. Así se garantizan a la vez el cupo de 3 libros, que ningún libro tenga dos préstamos activos y que el registro sea de todo o nada.
- **Registro de personas**: reserva el índice del correo con `SET NX`.
- **Interfaz**: todo el trabajo con Chroma y el modelo se ejecuta en **un único hilo trabajador**, en orden, y los resultados vuelven al hilo de Tkinter por una cola. La interfaz no se congela y nunca hay dos hilos usando Chroma a la vez.

## 7. Interfaz

- Tkinter + ttk con tema propio. Iconos de la fuente Segoe Fluent Icons, con símbolos Unicode como respaldo.
- Escalado para pantallas de alta densidad (`SetProcessDpiAwareness`); las tablas reparten su ancho de forma proporcional.
- Componentes reutilizables en `ui/componentes.py`: botón con estados, tabla ordenable con estado vacío, formulario con errores en línea, diálogos, avisos breves e indicadores.
- Errores centralizados en `AplicacionBiblioteca.manejar_error`: mensajes claros sin datos personales y detalle técnico en `biblioteca.log`.

## 8. Cambios respecto al esquema original (migración)

| Antes (v1) | Ahora (v2) | Migración |
|---|---|---|
| Libros solo en Chroma, con la disponibilidad en metadatos. | Libros en Redis (fuente de verdad) y en Chroma. | **Configuración › Sincronización › Importar documentos huérfanos** da de alta en Redis los libros que solo existen en Chroma. |
| `prestamos:{persona}` HASH que se borraba al devolver. | Registro por préstamo con estado e historial permanente. | No había préstamos v1 que migrar: se verificó que ninguna base de Redis contenía llaves del esquema anterior. |
| Llaves sin prefijo en la base 0. | Base dedicada y prefijo `bib:`. | — |
| Cifrado Fernet con `clave.key`. | AES-256-GCM con llave en `secrets/` o en una variable de entorno. | Los valores Fernet se siguen leyendo (solo lectura) y **Configuración › Seguridad › Migrar cifrado heredado** los vuelve a cifrar. `clave.key` no se modifica. |
| ISBN validado solo con expresión regular. | ISBN-10/13 con dígito de control y único. | Se corrigieron 13 ISBN de los datos de ejemplo. |
