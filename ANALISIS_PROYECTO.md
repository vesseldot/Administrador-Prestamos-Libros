# Análisis del proyecto: Administrador de Préstamos de Libros

**Fase 1: auditoría y análisis.** Este documento describe el proyecto tal como se recibió, antes de cualquier refactorización.

> **Nota posterior.** El plan de la sección 11 se ejecutó con los ajustes que resume la sección 13. Las rutas de archivo y los números de línea citados corresponden a la versión **original**. Para la versión actual, consulta [ARQUITECTURA.md](ARQUITECTURA.md), [SEGURIDAD.md](SEGURIDAD.md) y [PRUEBAS.md](PRUEBAS.md).

- Fecha del análisis: 2026-11-19
- Alcance: todos los archivos de `biblioteca/`, el entorno Python que usa (`../.venv`), la caché local de modelos y el servidor Redis local. Todas las comprobaciones fueron de solo lectura.
- No se modificó código, configuración, claves ni bases de datos. No se leyó `clave.key`.

---

## 1. Resumen ejecutivo

El proyecto es una aplicación de escritorio en **Python + Tkinter (ttk)** para administrar una biblioteca:

- **ChromaDB** guarda el catálogo de libros y resuelve la búsqueda semántica por sinopsis.
- **Redis** guarda las personas (con sus datos personales cifrados con Fernet) y los préstamos.
- **sentence-transformers** genera los embeddings, con un catálogo de cuatro modelos seleccionables.

La base es sólida. Tiene capa de datos separada de la interfaz, cifrado por campo, índice ciego (HMAC) del correo, tareas pesadas en hilos y una colección de Chroma por modelo. Los principales puntos débiles son cinco:

1. La aplicación **no arranca** en el entorno actual: falta el paquete `cryptography`.
2. El modelo configurado por defecto (`multilingual-e5-base`) **no está descargado**; el único modelo del catálogo que sí está en la caché local es `paraphrase-multilingual-MiniLM-L12-v2`.
3. Los libros viven **solo en Chroma**. La especificación nueva pide que Redis sea dueño de los identificadores, los metadatos y la disponibilidad.
4. Los préstamos **se borran al devolverse**: no hay historial, ni estado, ni fecha de devolución.
5. Las operaciones que tocan Redis y Chroma no tienen compensación ante fallos. Además, las llaves de Redis no tienen prefijo y se usaría la base 0, que en el entorno de desarrollo ya contenía llaves de otros proyectos.

---

## 2. Tecnologías y entorno verificado

| Elemento | Versión o estado | Cómo se comprobó |
|---|---|---|
| Python | 3.14.6 (`../.venv`, fuera del proyecto) | `python --version` |
| Tkinter / Tk | 8.6, escala de pantalla 1.33 (alta densidad de píxeles) | `tkinter.TkVersion` |
| chromadb | 1.5.9, funcional con Python 3.14 | Prueba real en carpeta temporal |
| redis (cliente) | 8.1.0 | `pip list` |
| sentence-transformers | 6.1.0 | `pip list` |
| torch | 2.14.1+cu130, **CUDA disponible** | `torch.cuda.is_available()` |
| transformers | 5.20.2 | `pip list` |
| numpy, pandas, python-dotenv | Instalados | `pip list` |
| **cryptography** | **NO instalado** (está declarado en `requirements.txt`) | `importlib.util.find_spec` |
| ttkbootstrap, pytest, fakeredis | No instalados | `pip list` |
| Fuentes | Segoe UI, Segoe UI Variable, **Segoe Fluent Icons**, Segoe MDL2 Assets, Consolas, Cascadia Code | `tkinter.font.families()` |

### Servidor Redis

- Contenedor Docker `redis`, Redis 8.10.1, puerto 6379 publicado en el equipo y **activo**.
- Persistencia: RDB con la política por defecto (`3600 1 300 100 60 10000`) y AOF desactivado. Los datos viven en `/data` dentro del contenedor, sin un volumen declarado en `docker inspect`. Si se elimina el contenedor, se pierden los datos.
- Se revisaron todas las bases (0–15): varias contenían llaves de otros proyectos y **ninguna** contenía llaves con los patrones de la biblioteca.

**Conclusión: en Redis no hay datos de la biblioteca que migrar.** Sin embargo, la configuración actual (`REDIS_DB=0`, llaves sin prefijo) mezclaría los datos con los de otros proyectos que compartan la instancia (en el entorno de desarrollo ya existían llaves como `historial:*`).

### ChromaDB

- `config.CHROMA_PATH` apunta a `biblioteca/chroma_db`, que **no existe** en la copia: al primer arranque se crearía una base vacía.
- En el directorio superior existen `NoSQL/chroma_db` y `NoSQL/chromadb`. No forman parte de este proyecto y no se inspeccionaron ni se tocarán.

---

## 3. Estructura de directorios

```
biblioteca/
├── main.py                   Interfaz Tkinter completa y punto de entrada (1309 líneas)
├── config.py                 Configuración: Redis (variables de entorno), rutas, regla de máx. 3 libros
├── db_libros.py              GestorLibros: libros en ChromaDB
├── db_personas.py            GestorPersonas: personas y préstamos en Redis
├── modelos.py                Catálogo de modelos de embeddings y envoltura de sentence-transformers
├── seguridad.py              Cifrado Fernet, HMAC del correo, enmascaramiento, aviso de privacidad
├── validaciones.py           Validación de libros y personas; listas cerradas
├── verificar.py              Diagnóstico de dependencias y de Redis
├── comparar_modelos.py       Experimento: tokens y búsquedas con dos modelos
├── requirements.txt          4 dependencias, sin versiones fijas
├── libros_lote.csv           20 libros (libro01–libro20)
├── libros_lote_nuevos.csv    55 libros (libro21–libro75)
├── clave.key                 Llave Fernet (44 bytes). SECRETO, no se leyó
├── share/man/man1/isympy.1   Manual de SymPy: residuo de pip, AJENO al proyecto
└── ANALISIS_PROYECTO.md      Este documento
```

Archivos que el código genera al ejecutarse: `chroma_db/`, `modelo_activo.txt` y `clave.key` (este último solo si no existe).
Archivos ausentes: `README.md`, `.gitignore`, `.env.example`, pruebas automatizadas.

---

## 4. Responsabilidad de cada archivo y sus componentes

### 4.1 `config.py`
Constantes globales. Redis (`REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD`) se lee de variables de entorno con valores por defecto. También define `CHROMA_PATH`, `ARCHIVO_MODELO_ACTIVO`, `ARCHIVO_LLAVE` y `MAX_LIBROS_POR_PERSONA = 3`. **No contiene secretos.**

Valores que están dispersos en otros archivos y deberían centralizarse aquí:
- Tamaño de lote de 32 en `db_libros`.
- Número de resultados por defecto (5 y 10).
- Tiempo de espera de conexión de 3 s.
- Modelo por defecto, que está definido en `modelos.py`.

### 4.2 `validaciones.py`
- Listas cerradas: `ESTADOS_MEXICO` (32), `GENEROS_PERSONA` (incluye «Prefiero no decir»), `OCUPACIONES`, `TIPOS_USUARIO`, `TIPOS_PASTA`.
- `CAMPOS_LIBRO` contiene los 14 campos que pide la especificación. `CAMPOS_PERSONA` contiene los 15 campos.
- `validar_libro(dict)` devuelve `(limpio, errores)`:
  - Obligatorios: id, sinopsis, título, autor, ISBN.
  - Tipos: año (`int`), páginas (`int`), calificación (`float`, entre 0 y 5), pasta (lista cerrada), disponible (`bool`, mediante `a_bool`).
  - El ISBN solo se valida con una expresión regular; no se comprueba el dígito de control.
  - Editorial, género, tema e idioma no son obligatorios.
- `validar_persona(dict)` aplica el correo (`@` y un punto posterior), el teléfono (10 dígitos), el C. P. (5 dígitos), las listas cerradas y el aviso de privacidad obligatorio. La fecha se valida como `AAAA-MM-DD` y con una edad entre 0 y 120 años.
- `calcular_edad()` deriva la edad de la fecha de nacimiento; **no se almacena**, lo que cumple la especificación.

### 4.3 `seguridad.py`
- `_cargar_o_crear_llave()` toma la llave de `BIBLIOTECA_KEY`, de `clave.key` o, si no hay ninguna, genera una y la guarda.
- `Cifrador`:
  - `cifrar` y `descifrar` usan **Fernet** (AES-128-CBC con HMAC-SHA256).
  - `hash_indice` calcula un HMAC-SHA256 determinista para el índice del correo. La llave del HMAC se deriva con `sha256(llave + etiqueta)`.
  - Si el descifrado falla, devuelve un texto fijo («no se pudo descifrar»).
- `enmascarar_correo` y `enmascarar_telefono` ocultan parte de los datos al mostrarlos.
- `AVISO_PRIVACIDAD` es el texto del aviso simplificado.

### 4.4 `modelos.py`
- `MODELOS`: cuatro modelos con su dimensión, tokens máximos, uso de prefijos y tamaño.
- `MODELO_POR_DEFECTO = "multilingual-e5-base"`.
- `nombre_coleccion(clave)` genera el nombre `libros_<modelo>`; hay una colección por modelo.
- `ModeloEmbeddings`:
  - Carga el modelo la primera vez que se usa.
  - `embeber_documentos` antepone `passage:` y `embeber_consulta` antepone `query:` cuando el modelo es e5.
  - Normaliza los vectores para usar similitud coseno.
  - `contar_tokens` cuenta los tokens de un texto.

### 4.5 `db_libros.py` → `GestorLibros` (ChromaDB)
- Usa `PersistentClient(CHROMA_PATH)` y una colección por modelo con `hnsw:space=cosine` y `embedding_function=None`: los embeddings los calcula la propia aplicación.
- Funciones de modelo: `leer_modelo_activo` y `guardar_modelo_activo` usan `modelo_activo.txt`. `cambiar_modelo` reindexa en lotes de 32 y conserva la colección anterior.
- Altas: `agregar`, `agregar_lote` (valida fila por fila y detecta ids repetidos en el archivo y en la base), `leer_archivo` y `cargar_archivo`. Lee CSV con detección de `,` o `;` y con `utf-8-sig`, y JSON como lista o `{"libros": [...]}`.
- Consultas: `buscar(texto, n, solo_disponibles)` usa `query` con `where={"disponible": True}` y calcula la similitud como `1 - distancia`. También hay `obtener`, `catalogo` (ordenado por id) y `contar`.
- Cambios: `actualizar` recalcula el embedding, `marcar_disponible` solo modifica metadatos y `borrar`.
- Estructura en Chroma: `ids` = id del libro, `documents` = sinopsis, `metadatas` = los 12 campos restantes, incluido `disponible`.

### 4.6 `db_personas.py` → `GestorPersonas` (Redis)
Estructuras actuales:

| Llave | Tipo | Contenido |
|---|---|---|
| `persona:contador` | STRING (INCR) | Generador de ids `P0001`… |
| `personas` | SET | Ids de todas las personas |
| `persona:{id}` | HASH | 13 campos cifrados, `tipo_usuario` en claro, `correo_hash`, fechas de aviso y de registro |
| `idx:correo:{hmac}` | STRING | Id de la persona dueña del correo (índice ciego, evita duplicados) |
| `prestamos:{id}` | HASH | `libro_id` → JSON `{titulo, fecha}` |
| `libro:prestado:{libro_id}` | STRING | Id de la persona que tiene el libro (se crea con `SET NX`) |
| `personas_con_prestamo` | SET | Personas con al menos un préstamo |

Métodos:
- `registrar` y `actualizar` llaman a `_guardar`, que cifra y escribe todo en un *pipeline*.
- `obtener` descifra y calcula la edad. `listar` también existe.
- `eliminar` implementa el derecho ARCO de cancelación y se bloquea si la persona tiene préstamos.
- `prestamos_de` y `libro_prestado_a` consultan préstamos.
- `prestar(persona, [libros])`:
  1. Valida que la persona tenga cupo.
  2. Valida que cada libro exista en Chroma y esté disponible.
  3. Aparta los libros con `SET NX`; si alguno falla, revierte los apartados.
  4. Escribe el HASH de préstamos.
  5. Marca los libros como no disponibles en Chroma.
- `devolver` borra la entrada del HASH, borra la llave `libro:prestado` y marca los libros como disponibles. **El préstamo desaparece: no queda historial.**

### 4.7 `main.py` (interfaz)

| Bloque | Líneas | Contenido |
|---|---|---|
| Tema | 23–184 | Paleta `COLOR` y `aplicar_tema()` con estilos ttk sobre el tema `clam` |
| Utilidades | 189–292 | `tarjeta`, `encabezado_tarjeta`, `caja_texto`, `crear_tabla`, `llenar_tabla`, `centrar`, `cabecera_dialogo`, logotipo dibujado en un Canvas |
| `Formulario` | 294–381 | Diálogo genérico. Los campos son tuplas `(clave, etiqueta, tipo, opciones)`. La ventana no se cierra si `al_guardar` lanza `ValueError` |
| `App` | 387–542 | Ventana principal: encabezado con indicadores, barra de navegación superior, `Notebook` sin pestañas visibles y barra de estado. `en_segundo_plano` ejecuta tareas en un hilo y `_revisar_cola` recoge los resultados cada 100 ms |
| `TabLibros` | 571–780 | Búsqueda semántica, catálogo, detalle con formato, alta, carga por lote, actualización y borrado |
| `TabModelo` | 786–916 | Tabla de modelos, cambio con reindexado, contador de tokens, revisión de sinopsis que se cortan |
| `TabPersonas` | 1041–1139 | Catálogo con correo y teléfono enmascarados, alta, actualización, ficha (derecho ARCO de acceso), eliminación (cancelación), aviso de privacidad |
| `TabPrestamos` | 1149–1286 | Selector de persona, barra de cupo, libros prestados (para devolver) y disponibles (con búsqueda) |
| `main()` | 1290–1305 | Conecta Redis (muestra un error si no está), construye los gestores y arranca la app |

### 4.8 Scripts auxiliares
- `verificar.py` revisa las dependencias y hace PING a Redis. **No usa** `REDIS_PASSWORD` ni `REDIS_DB`.
- `comparar_modelos.py` usa `numpy`, que no está declarado en `requirements.txt`. Depende de `GestorLibros` y del modelo e5-base, que no está descargado.

---

## 5. Dependencias entre módulos

```
config ◄──────────────┬───────────┬────────────┬─────────┐
   ▲                  │           │            │         │
seguridad          db_libros   db_personas    main    verificar
   ▲                ▲  ▲  ▲      ▲  ▲  ▲        │
   └────────────────┼──┼──┼──────┘  │  │        │
validaciones ◄──────┘  │  └─────────┼──┘ ◄──────┤
modelos ◄──────────────┘ ◄──────────┼─────────── ┤ ◄── comparar_modelos
                                    │            │
db_libros ◄─────────────────────────┘ (inyección: GestorPersonas recibe GestorLibros)
```

| Módulo | Importa | Lo importan |
|---|---|---|
| config | — | seguridad, db_libros, db_personas, main, verificar |
| validaciones | — | db_libros, db_personas, main |
| modelos | sentence_transformers (al primer uso) | db_libros, main, comparar_modelos |
| seguridad | config, cryptography | db_personas, main |
| db_libros | config, modelos, validaciones, chromadb | main, comparar_modelos |
| db_personas | config, seguridad, validaciones, redis | main |
| main | todos | — |

No hay ciclos. La interfaz depende de la capa de datos y no al revés.

---

## 6. Flujo de información

### 6.1 Arranque
1. `main()` → `conectar_redis()` hace PING; si falla, muestra un diálogo de error.
2. `GestorLibros()` abre Chroma y la colección del modelo activo.
3. `GestorPersonas(r, libros)` carga o crea la llave Fernet.
4. `App` construye las pestañas. `TabPersonas` y `TabPrestamos` consultan Redis en el hilo principal.
5. En segundo plano se carga el modelo (`embeber_consulta("hola")`). Si no está descargado, se descarga de internet. Al terminar se muestra el catálogo.

### 6.2 Alta de libro
Formulario → `validar_libro` (en la interfaz) → hilo → `GestorLibros.agregar` (vuelve a validar, calcula el embedding y hace `collection.add`) → la cola entrega el resultado a la interfaz → mensaje y refresco del catálogo.

### 6.3 Búsqueda semántica
Texto → hilo → `embeber_consulta` → `collection.query(n, where disponible)` → similitud `1 - d` → tabla. La ficha de detalle consulta además `libro:prestado:{id}` en Redis.

### 6.4 Préstamo (entre las dos bases)
`TabPrestamos.prestar` (hilo principal) → `GestorPersonas.prestar`:
1. Redis: comprobar que la persona existe y tiene cupo (`HLEN`).
2. Chroma: obtener cada libro.
3. Redis: `SET NX libro:prestado:*`.
4. Redis: `HSET prestamos:*` y `SADD`.
5. Chroma: `marcar_disponible(False)` libro por libro.

Si el paso 5 falla, Redis registra el préstamo pero Chroma sigue mostrando el libro como disponible.

### 6.5 Devolución
`HDEL prestamos:*` → `DEL libro:prestado:*` → `marcar_disponible(True)` en Chroma → `SREM` si la persona ya no tiene préstamos. Se pierde el registro del préstamo.

### 6.6 Personas
Formulario → `validar_persona` → índice HMAC del correo → cifrado de 13 campos → *pipeline* `HSET` + índice + `SADD`. La lectura descifra campo por campo y la tabla enmascara correo y teléfono.

---

## 7. Modelo semántico

### 7.1 Configuración del proyecto
- Catálogo: `paraphrase-multilingual-MiniLM-L12-v2`, `multilingual-e5-small`, `multilingual-e5-base` y `sentence_similarity_spanish_es`.
- Por defecto se usa `multilingual-e5-base`, porque no existe `modelo_activo.txt`.

### 7.2 Disponibilidad local (caché de Hugging Face, comprobada sin conexión)

| Modelo | ¿En el catálogo del proyecto? | ¿Descargado? |
|---|---|---|
| sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 | Sí | **Sí (480 MB)** |
| intfloat/multilingual-e5-base (por defecto) | Sí | **No** (la descarga es de unos 1.1 GB) |
| intfloat/multilingual-e5-small | Sí | No |
| hiiamsid/sentence_similarity_spanish_es | Sí | No |

### 7.3 Características medidas de `paraphrase-multilingual-MiniLM-L12-v2`
- Arquitectura: 12 capas de tipo BERT, 384 dimensiones, *mean pooling* y `max_seq_length = 128`. Es multilingüe e incluye español. No usa prefijos.
- Carga sin conexión en `cuda:0`: entre 3.9 y 5.0 s. Generar los embeddings de las 75 sinopsis tarda 0.49 s.
- Longitud de las 75 sinopsis con su tokenizador: mínimo 44, media 77, máximo 136 tokens. **Solo 1 de 75 supera los 128 tokens**, y pierde 8 tokens del final.
- Búsquedas de prueba en español (75 libros, similitud coseno):

| Consulta | Primer resultado | Siguientes |
|---|---|---|
| «un hombre sobrevive solo en otro planeta» | Proyecto Hail Mary (0.56) | El marciano (0.47), El principito (0.45) |
| «niño que descubre que es mago» | Harry Potter y la piedra filosofal (0.69) | El nombre del viento (0.63), Frankenstein (0.53) |
| «gobierno que vigila todo lo que piensas» | 1984 (0.37) | La sombra del viento (0.30), Pensar rápido pensar despacio (0.27) |
| «amor imposible en tiempos de guerra» | La casa de los espíritus (0.45) | La sombra del viento (0.39), Juego de tronos (0.39) |

### 7.4 Conclusión sobre el modelo
`paraphrase-multilingual-MiniLM-L12-v2` es el modelo que ya está preparado en el proyecto y en el equipo:
- Entiende español.
- Funciona sin conexión y con GPU.
- Con este catálogo, el límite de 128 tokens afecta a un solo libro de forma mínima.

**No hay motivo técnico para descargar otro modelo.** La propuesta es usarlo por defecto y conservar el resto del catálogo como opciones que solo se descargarían si el usuario lo pide expresamente.

---

## 8. Calidad de los datos de ejemplo

Se validaron con `validar_libro` del propio proyecto:
- `libros_lote.csv`: 20 filas, 0 errores y 0 ids duplicados.
- `libros_lote_nuevos.csv`: 55 filas, 0 errores y 0 ids duplicados.
- No hay ids repetidos entre los dos archivos: son 75 libros en total.

---

## 9. Problemas detectados

### 9.1 Críticos (impiden funcionar o ponen datos en riesgo)

| # | Problema | Ubicación |
|---|---|---|
| C1 | Falta `cryptography` en el entorno: la importación falla y la app no arranca | `seguridad.py:25` |
| C2 | El modelo por defecto no está descargado: el primer arranque descargaría 1.1 GB y, sin conexión, falla | `modelos.py:43` |
| C3 | Las llaves de Redis no tienen prefijo y se usa la base 0, compartida con otros proyectos | `config.py:13`, `db_personas.py` |
| C4 | Si una función `al_terminar` lanza una excepción, `_revisar_cola` no se vuelve a programar y la interfaz deja de recibir resultados de las tareas de fondo | `main.py:501-516` |
| C5 | Préstamo y devolución escriben en Redis y en Chroma sin compensación: un fallo intermedio deja datos inconsistentes | `db_personas.py:138-192` |

### 9.2 Diferencias con la especificación nueva

| # | Requisito | Situación actual |
|---|---|---|
| E1 | Redis guarda identificadores, metadatos de libros y disponibilidad | Los libros solo existen en Chroma |
| E2 | Historial de préstamos, estado y fecha de devolución | El préstamo se borra al devolver |
| E3 | Cifrado AES-256-GCM | Se usa Fernet (AES-128-CBC + HMAC) |
| E4 | Menú lateral con 7 secciones y un Dashboard | Barra superior con 4 secciones y sin Dashboard |
| E5 | Catálogo con filtros, búsqueda por texto y ordenamiento | Solo catálogo y búsqueda semántica |
| E6 | Búsqueda de personas por nombre y otros campos | No existe |
| E7 | Vista de personas con préstamos (títulos, fecha, estado) | Solo un filtro de la lista de personas |
| E8 | Actividad reciente | No existe |
| E9 | Duplicados de libro por ISBN | Solo se controla el id |
| E10 | `.env.example`, `README.md`, `ARQUITECTURA.md`, `SEGURIDAD.md`, `PRUEBAS.md` y pruebas | No existen |

### 9.3 Errores y malas prácticas

| # | Problema | Ubicación |
|---|---|---|
| B1 | `cambiar_modelo` cambia el estado antes de reindexar: si falla, la instancia queda con el modelo nuevo y la colección incompleta | `db_libros.py:56-77` |
| B2 | Condiciones de carrera: `registrar` comprueba el correo y lo indexa en pasos separados; `prestar` comprueba el cupo con `HLEN` fuera de una transacción | `db_personas.py:75-78, 145-150` |
| B3 | Las reglas de negocio están en la interfaz: `borrar` no comprueba préstamos en la capa de datos y `actualizar` fuerza `disponible=False` desde la interfaz | `main.py:745-780` |
| B4 | Validación duplicada: la interfaz valida y después el gestor vuelve a validar | `main.py:711-717, 755-758` |
| B5 | `fecha_aviso` (fecha del consentimiento) se sobrescribe en cada actualización | `db_personas.py:56` |
| B6 | `eliminar` no comprueba que la persona exista | `db_personas.py:112` |
| B7 | Si el descifrado falla, se devuelve un texto que puede acabar guardado de nuevo, cifrado, al actualizar | `seguridad.py:57` |
| B8 | La llave del HMAC se deriva con un hash simple, no con HKDF. `clave.key` se crea sin restringir permisos ni ignorarla en git | `seguridad.py:30-48` |
| B9 | `verificar.py` ignora `REDIS_PASSWORD` y `REDIS_DB` | `verificar.py:26` |
| B10 | Subtítulo vacío (`(""))`), restos de código | `main.py:793-794` |
| B11 | `requirements.txt` no fija versiones ni incluye `numpy` | `requirements.txt` |
| B12 | La interfaz es un monolito de 1309 líneas | `main.py` |
| B13 | Faltan `.gitignore` (`clave.key` se publicaría), registro de eventos (logging) y pruebas | raíz |
| B14 | Carpeta `share/` ajena al proyecto | `share/` |
| B15 | Comentarios didácticos dentro del código; la especificación pide eliminarlos | todos los `.py` |

### 9.4 Rendimiento
- `listar()` hace un `HGETALL` y 13 descifrados por persona (N+1). Es aceptable para una demostración (cientos de registros); conviene usar *pipeline*.
- `TabPrestamos.al_mostrar` y `TabLibros.al_mostrar` cargan el catálogo completo en el hilo principal cada vez que se muestra la sección.
- `marcar_disponible` lee el libro completo para reescribir sus metadatos.

---

## 10. Lo que se conserva

- La arquitectura de módulos planos y sus nombres (`config`, `validaciones`, `seguridad`, `modelos`, `db_libros`, `db_personas`, `main`), para no romper importaciones.
- Las listas cerradas, las reglas de validación y el cálculo de la edad.
- El cifrado por campo, el índice ciego HMAC del correo, el enmascaramiento y el aviso de privacidad. Cambia el algoritmo, no el diseño.
- Una colección de Chroma por modelo, los embeddings calculados por la app, la similitud coseno y el reindexado explícito.
- La carga perezosa del modelo, la fábrica de modelos inyectable (permite pruebas sin descargar modelos) y los prefijos de e5.
- La carga por lote de CSV y JSON con reporte por fila.
- La reserva de libros con `SET NX`, el límite de 3 libros y el bloqueo de cancelación si hay préstamos.
- Las tareas pesadas en un hilo con cola, el `Formulario` genérico y la paleta del tema.
- Todas las funciones actuales: contador de tokens, revisión de sinopsis que se cortan, cambio de modelo, ficha ARCO de acceso, rectificación y cancelación.
- `clave.key`: no se borra ni se sobrescribe. Se usaría solo para leer datos heredados cifrados con Fernet (hoy no hay ninguno).

---

## 11. Plan de implementación

### 11.1 Nuevo modelo de datos

**Redis** (base dedicada, prefijo configurable `bib:`). Redis es la fuente de verdad.

| Llave | Tipo | Contenido |
|---|---|---|
| `bib:libro:{id}` | HASH | Los 13 campos (sin sinopsis) y `disponible` |
| `bib:libros` | SET | Ids de los libros |
| `bib:idx:isbn:{isbn}` | STRING | Id del libro; evita ISBN duplicados |
| `bib:persona:contador`, `bib:personas`, `bib:persona:{id}`, `bib:idx:correo:{hmac}` | — | Como ahora, cifrado con AES-256-GCM y conservando `fecha_aviso` original |
| `bib:prestamo:contador` | STRING | Generador de ids `PR000001`… |
| `bib:prestamo:{pid}` | HASH | `persona_id`, `libro_id`, `titulo`, `fecha_prestamo`, `fecha_devolucion`, `estado` (`activo` / `devuelto`) |
| `bib:libro:{id}:prestamo_activo` | STRING | Id del préstamo activo; garantiza un solo préstamo activo por libro |
| `bib:persona:{id}:prestamos_activos` | SET | Ids de los préstamos activos |
| `bib:persona:{id}:historial` | ZSET (fecha) | Todos sus préstamos, que nunca se borran |
| `bib:prestamos:activos` | SET | Préstamos activos globales, para el Dashboard |
| `bib:personas_con_prestamo` | SET | Personas con al menos un préstamo activo |
| `bib:actividad` | LIST (últimos 50) | Eventos `{tipo, ids, fecha}`, sin datos personales |
| `bib:sync:pendientes` | SET | Ids de libros con sincronización Redis↔Chroma pendiente |

- **Préstamo y devolución atómicos con scripts Lua.** Un solo script valida que la persona exista, que tenga cupo, que cada libro exista, esté disponible y no tenga préstamo activo. Después crea todos los registros. Es «todo o nada» y sirve igual para uno o para varios libros.
- **Chroma:** `ids` = id del libro, `documents` = sinopsis y `metadatas` = copia de los 13 campos. La copia sirve para identificar el documento y filtrar; los resultados de búsqueda se completan siempre con los datos de Redis.

### 11.2 Estrategia de compensación Redis ↔ Chroma
- **Alta:** se valida y se reserva el id y el ISBN en Redis (`SET NX`). Después se escribe en Chroma (embedding) y se confirma el HASH en Redis. Si falla Chroma, se liberan las reservas. Si falla la confirmación en Redis, se borra el registro de Chroma.
- **Actualización:** se guarda una copia del estado anterior en Redis y en Chroma. Si un paso falla, se restaura la copia; si la restauración también falla, el id queda en `bib:sync:pendientes`.
- **Eliminación:** se bloquea si hay un préstamo activo. Se guarda una copia que incluye el embedding y se borra de Chroma y de Redis. Si falla, se reinserta desde la copia. El historial de préstamos se conserva.
- **Disponibilidad:** Redis la cambia de forma atómica. Copiarla a Chroma es un paso secundario: si falla, se anota como pendiente.
- **Reconciliación** (al arrancar y con un botón en Configuración): detecta libros que están en Redis y no en Chroma (los reindexa), libros que están en Chroma y no en Redis (los muestra para importarlos o descartarlos, **nunca los borra automáticamente**) y metadatos desincronizados.

### 11.3 Archivos que se modificarán

| Archivo | Cambios |
|---|---|
| `config.py` | Centralizar el prefijo y la base de Redis, rutas de secretos, modelo por defecto, modo sin conexión, tamaños de lote, límites y número de resultados. Cargar `.env` con python-dotenv |
| `validaciones.py` | Conservar las reglas. Añadir dígito de control del ISBN (como aviso o error, por decidir) y normalización. Quitar comentarios didácticos |
| `seguridad.py` | AES-256-GCM con nonce aleatorio de 96 bits y datos asociados (AAD) = `persona_id + campo`, para impedir intercambiar valores cifrados entre campos o registros. HKDF para la llave del índice. Llave desde `BIBLIOTECA_AES_KEY` o `secrets/biblioteca.key` (ignorado en git). Lectura heredada de Fernet. Error explícito si el descifrado falla |
| `modelos.py` | Modelo por defecto `paraphrase-multilingual-MiniLM-L12-v2` y modo sin conexión configurable. Conservar el catálogo |
| `db_libros.py` | Solo Chroma: documentos, metadatos, embeddings y búsqueda. Lectura de embeddings para compensar. Cambio de modelo transaccional |
| `db_personas.py` | Solo personas: prefijo, AES-GCM, `SET NX` en el índice del correo, conservación de `fecha_aviso`, búsqueda por nombre y apellidos (descifrado en memoria), *pipeline* en `listar` |
| `main.py` | Solo punto de entrada (`python main.py` sigue funcionando) |
| `verificar.py` | Redis con contraseña y base, modelo en caché, llave presente, Chroma accesible |
| `comparar_modelos.py` | Usar solo modelos descargados y avisar si falta alguno |
| `requirements.txt` | Versiones mínimas y añadir `numpy`, `python-dotenv`, `pytest` y `fakeredis` (pruebas) |

### 11.4 Archivos nuevos

| Archivo | Propósito |
|---|---|
| `db_redis.py` | Conexión, prefijo, registro de scripts Lua y actividad reciente |
| `db_catalogo.py` | Libros en Redis (HASH, índices, disponibilidad) |
| `db_prestamos.py` | Préstamos con historial y scripts Lua de préstamo y devolución |
| `servicios.py` | `ServicioBiblioteca`: coordina Redis y Chroma con compensación y reconciliación, y calcula las estadísticas del Dashboard |
| `ui/tema.py`, `ui/iconos.py` | Paleta, tipografía e iconos (Segoe Fluent Icons, con Segoe MDL2 como respaldo) |
| `ui/componentes.py` | Tarjetas, tabla ordenable por columna, estado vacío, avisos breves (*toast*), confirmación, formulario e indicador de carga |
| `ui/app.py` | Ventana principal, menú lateral, panel dinámico y tareas en segundo plano (robustas) |
| `ui/vistas/dashboard.py` | Indicadores reales y actividad reciente |
| `ui/vistas/libros.py` | Catálogo con filtros, texto, ordenamiento, detalle, alta, lote, edición y borrado |
| `ui/vistas/busqueda.py` | Búsqueda semántica con ficha del libro |
| `ui/vistas/personas.py` | Catálogo, búsqueda, alta, edición, ficha ARCO, cancelación y aviso |
| `ui/vistas/prestamos.py` | Préstamo de 1 a 3 libros y devolución de uno, varios o todos |
| `ui/vistas/personas_prestamos.py` | Personas con préstamos activos: títulos, fechas, estado y teléfono visible solo a petición |
| `ui/vistas/configuracion.py` | Modelo de embeddings (se conserva la pestaña actual), conexiones, reconciliación, rutas, aviso de privacidad |
| `tests/` | Pruebas con pytest: validaciones, cifrado, catálogo, préstamos (fakeredis), Chroma temporal con modelo simulado y una prueba de integración con el modelo real |
| `.gitignore`, `.env.example` | Excluir secretos y bases; documentar variables |
| `README.md`, `ARQUITECTURA.md`, `SEGURIDAD.md`, `PRUEBAS.md` | Documentación final |

**Archivo que se eliminará:** `ANALISIS_Y_PLAN.md`, el borrador anterior generado en esta misma revisión, sustituido por este documento.

### 11.5 Interfaz
- **Se usará ttk puro** con un tema propio que amplía el actual. No se añade ttkbootstrap: no está instalado, no se ha probado con Python 3.14 y el tema actual ya ofrece la base visual.
- La iconografía usa la fuente **Segoe Fluent Icons**, presente en el equipo, sin imágenes externas.
- Se ajusta la escala para la pantalla de alta densidad (1.33).
- Menú lateral con 7 secciones, panel dinámico, encabezados, tarjetas de indicadores, tablas con filas alternas y ordenamiento, estados vacíos, confirmaciones, avisos de éxito y error, y un indicador de carga.
- Todas las operaciones lentas (embeddings, carga por lote, reindexado y carga del catálogo) se ejecutan en segundo plano.

### 11.6 Fases y verificación

| Fase | Contenido | Verificación |
|---|---|---|
| 0 | `.gitignore`, `.env.example`, configuración centralizada, dependencias | `verificar.py` |
| 1 | Seguridad AES-GCM y personas | Pruebas de cifrado y personas |
| 2 | Catálogo en Redis, Chroma, servicio con compensación | Pruebas CRUD, de lote y de fallos simulados |
| 3 | Préstamos con historial (Lua) | Pruebas de préstamo, devolución, cupo y doble préstamo |
| 4 | Interfaz nueva, sección por sección | Arranque real y recorrido funcional |
| 5 | Limpieza de comentarios y código muerto | Las pruebas siguen pasando |
| 6 | Documentación y `PRUEBAS.md` con resultados reales | — |

---

## 12. Riesgos técnicos

| Riesgo | Mitigación |
|---|---|
| No existe transacción distribuida entre Redis y Chroma | Reservas, compensación, `bib:sync:pendientes` y reconciliación |
| Base 0 de Redis compartida con otros proyectos | Base dedicada (propuesta: 2) y prefijo `bib:`. Nunca usar `FLUSHDB` ni `FLUSHALL`; las pruebas usan fakeredis o borran solo su propio prefijo |
| El contenedor Redis no tiene volumen persistente | Documentarlo y recomendar `docker run -v`, sin cambiar el contenedor sin autorización |
| Perder la llave AES deja los datos personales ilegibles | Advertirlo en `SEGURIDAD.md` e incluir un procedimiento de respaldo y rotación |
| Instalar paquetes en `../.venv` modifica un entorno externo al proyecto | Requiere autorización (ver decisiones) |
| Python 3.14 es muy reciente | chromadb y sentence-transformers ya se probaron. Se evita añadir paquetes sin probar (ttkbootstrap) |
| Una sinopsis (136 tokens) supera los 128 del modelo | Se muestra un aviso en la interfaz (ya existe el contador). Su impacto es mínimo |
| La búsqueda de personas por nombre exige descifrar en memoria | Suficiente para la escala de la demostración; se documenta |
| Cifrar no equivale a cumplir la LFPDPPP | `SEGURIDAD.md` separará las medidas técnicas de los aspectos legales que requieren revisión |

---

## 13. Decisiones tomadas

| # | Tema | Decisión | Resultado |
|---|---|---|---|
| 1 | Entorno | Se autorizó instalar dependencias en `../.venv`. | Instalados cryptography 50.0.2, pytest 9.2.0 y fakeredis 2.40.0. |
| 2 | Redis | Usar una base completamente vacía. | Base 2 (0 llaves al empezar) con prefijo `bib:`. La aplicación rechaza bases con llaves ajenas. |
| 3 | Modelo | Usar **Qwen/Qwen3-Embedding-0.6B** en float16 sobre GPU, ya probado por el equipo. | Qwen3-0.6B en float16 y sin conexión por defecto. Se midió frente a MiniLM con 60 consultas: Hit@1 de 90 % frente a 82 % ([PRUEBAS.md](PRUEBAS.md)). MiniLM se conserva como alternativa. |
| 4 | Acceso | Añadir contraseña de operador. | Pantalla de acceso, hash scrypt, bloqueo por inactividad y espera tras intentos fallidos. |
| 5 | `share/` | Evaluar si es necesaria. | No lo referenciaba ningún archivo (manual de `isympy` dejado por pip): **eliminado**. |
| 6 | ISBN | Corregir lo necesario. | El dígito de control se valida como **error**. En los datos se corrigieron 13 ISBN: 10 recalculando el dígito y 3 con el ISBN real verificado, porque colisionaban con otros libros. |
| 7 | Dataset | Ampliar con clásicos, famosos y recientes para medir la búsqueda. | `datos/libros_catalogo_ampliado.csv` (125 libros) y `datos/consultas_evaluacion.json` (60 consultas). |
