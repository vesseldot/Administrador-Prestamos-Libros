# Pruebas realizadas y resultados

Fecha: 2026-11-19 · Equipo: Windows 11, NVIDIA GeForce RTX 4060 Laptop GPU · Python 3.14.6 · Redis 8.10.1 (Docker) · chromadb 1.5.9 · sentence-transformers 6.1.0 · torch 2.14.1+cu130.

Todos los resultados de este documento provienen de ejecuciones reales. Lo que no se pudo comprobar se indica en la sección 7.

## 1. Cómo ejecutarlas

```powershell
python -m pytest tests                                        # 150 pruebas (fakeredis + Chroma temporal + modelo simulado)
$env:BIBLIOTECA_PRUEBAS_REALES="1"; python -m pytest tests    # 151 pruebas: añade la integración con servicios reales
python verificar.py                                           # diagnóstico del entorno
python evaluar_busqueda.py                                    # calidad de la búsqueda semántica
```

Las pruebas unitarias usan **fakeredis** y una ChromaDB en una carpeta temporal: no tocan la base de la aplicación. Un fixture automático (`portadas_aisladas`) envía las portadas a una carpeta temporal y bloquea cualquier petición a Open Library. La prueba de integración real usa la base configurada con un prefijo propio (`prueba_integracion:`) y al terminar borra solo esas llaves. Se verificó que la base de la aplicación y las demás bases de la instancia de Redis conservaron exactamente el mismo número de llaves.

## 2. Resultado global

| Archivo | Pruebas | Resultado | Qué cubre |
|---|---:|---|---|
| `test_validaciones.py` | 9 | ✅ | ISBN-10/13 con dígito de control; los 14 campos obligatorios del libro y sus tipos; rangos; reglas de personas (correo, teléfono de 10 dígitos, C.P., 32 estados, listas cerradas, aviso obligatorio); edad derivada. |
| `test_seguridad.py` | 11 | ✅ | Ida y vuelta de AES-256-GCM; nonce distinto por valor; AAD que impide intercambiar campos; detección de alteraciones; llave incorrecta; lectura de Fernet heredado; índice ciego; scrypt; llave inválida; creación del archivo de secretos; enmascaramiento. |
| `test_personas.py` | 10 | ✅ | Datos cifrados en Redis (sin texto en claro y sin edad almacenada); rechazo sin aviso; correo duplicado; rectificación que conserva la fecha de consentimiento y reindexa el correo; búsqueda por nombre y campos no sensibles (no por teléfono); cancelación bloqueada con préstamos; dato alterado; exportación ARCO; rechazo de una base con llaves ajenas. |
| `test_libros.py` | 17 | ✅ | Alta en Redis y Chroma con metadatos iguales; duplicados de id e ISBN; alta incompleta sin escrituras; reporte de lote (aceptados y rechazados con motivo); CSV con `;`; actualización sincronizada con re-embedding solo si cambia la sinopsis; cambio de ISBN; eliminación en ambas bases; búsqueda semántica; filtros; **compensación ante fallos simulados** en alta (Redis y Chroma), actualización y eliminación; revisión y reparación de la sincronización; importación de huérfanos; cambio de modelo exitoso y fallido. |
| `test_prestamos.py` | 13 | ✅ | Préstamo de 3 libros en una operación; operaciones separadas hasta el límite; más de 3 rechazado; un libro sin dos préstamos activos; todo o nada; libro marcado no disponible; persona o libro inexistente; devolución de 1, 2 y todos con historial conservado; préstamo ajeno o ya devuelto; libro prestado no eliminable ni marcable como disponible; personas con préstamos y estadísticas; vencimiento derivado; búsqueda «solo disponibles». |
| `test_interfaz.py` | 4 | ✅ | Interfaz Tkinter real: navegación por las 7 secciones y las 4 pestañas de Configuración sin errores. Flujo completo desde la interfaz: alta por formulario, errores en línea, filtro del catálogo, búsqueda semántica, préstamo de 2 libros, contacto visible y vuelto a ocultar, devolución de 1 y de todos, eliminación e indicadores del Dashboard. Bloqueo de sesión. Portada en la ficha del catálogo y en la búsqueda, quitar portada y contador de Configuración. |
| `test_portadas.py` | 26 | ✅ | Normalización a JPEG de 600×900 como máximo; transparencia; rechazo de archivos que no son imagen, diminutos o de más de 15 MB; guardar, consultar, quitar y miniaturas que se renuevan al reemplazar la imagen; identificadores que no son de libro (por ejemplo `../fuera`). Open Library simulado: búsqueda por ISBN con título coincidente, descarte de la edición de otro libro y búsqueda por título, sin resultados, error de red y reintento tras un fallo puntual. Servicio: asignar desde un archivo, validaciones, borrado de la portada al eliminar el libro, búsqueda individual, búsqueda desactivada, descarga solo de las que faltan con progreso, detención a petición e interrupción clara sin red. |
| `test_gestor_modelos.py` | 9 | ✅ | Revisiones fijadas y metadatos de los 5 modelos; filtro de archivos (sin ONNX, OpenVINO ni `.bin`); modelo ausente; descarga con progreso creciente hasta el total; reutilización sin volver a descargar; reanudación de solo los archivos faltantes; sin conexión; espacio insuficiente; revisión incompleta; mensaje claro al cargar un modelo ausente. Usa un Hub simulado, sin red. |
| `test_config.py` | 4 | ✅ | Valores por defecto válidos; mensajes claros para cada variable inválida; rutas relativas de ChromaDB; **persistencia de ChromaDB comprobada desde otro proceso**. |
| `test_arquitectura.py` | 35 | ✅ | Por cada archivo de `ui/`: no importa Redis, ChromaDB, el modelo, los módulos `db_*`, `portadas` ni Pillow; no usa atributos internos del servicio; solo llama a métodos que existen en la API pública. El backend no importa `ui` ni `tkinter`. Se comprobó además que detecta un acceso interno, un método inexistente y dos importaciones prohibidas en un fragmento de ejemplo. |
| `test_api_interfaz.py` | 10 | ✅ | Claves y valores de la API para la interfaz (sistema, modelo, tokens, personas, préstamos, actividad, seguridad, datos de ejemplo); `describir_error` por categoría; `ControlAcceso` (espera tras fallos, cambio de contraseña). |
| `test_demo.py` | 2 | ✅ | El modo de demostración usa fakeredis y el prefijo `demo:`, carga 200 libros, 4 personas y un préstamo vencido, acepta la contraseña `demo1234` y no escribe el `modelo_activo.txt` real. |
| `test_integracion_real.py` | 1 | ✅ | Ver sección 3. |
| **Total** | **151** | **151 aprobadas** | 35 s con la integración real; unos 19 s sin ella. |

### Errores encontrados y corregidos durante las pruebas

| Error | Corrección |
|---|---|
| Chroma intentaba calcular un embedding al actualizar sin pasar uno. | Si la sinopsis no cambia, solo se actualizan los metadatos. |
| Los préstamos creados en el mismo segundo no tenían un orden estable. | Se desempatan por el id del préstamo. |
| `TemporaryDirectory` no podía borrar la carpeta de Chroma en Windows (archivo bloqueado). | La evaluación usa `EphemeralClient`. |
| En pantallas al 133 %, las columnas de las tablas y los textos se recortaban (detectado en capturas). | Escalado según la densidad de la pantalla, reparto proporcional del ancho de las columnas y cabeceras flexibles. |
| Los ids se ordenaban como texto (libro15 tras libro149). | Orden natural (`clave_natural`). |
| `comparar_modelos.py` usaba un método eliminado. | Actualizado a la API nueva. |
| Al corregir solo el dígito de control, 2 ISBN chocaban con los de otros libros. | Se usaron los ISBN reales, verificados, de *1984* y *El resplandor*. |

## 3. Integración con Redis, ChromaDB y el modelo reales

`tests/test_integracion_real.py`, con Redis en `localhost:6379` (base 2), ChromaDB persistente en una carpeta temporal y **Qwen3-Embedding-0.6B en cuda:0 en float16**:

| Comprobación | Resultado |
|---|---|
| Conexión a Redis | ✅ PING correcto. |
| Importación de los 200 libros de `datos/` | ✅ 200 agregados, 0 rechazados, en **16.4 s** (incluye la carga del modelo). |
| Reimportar 3 libros existentes | ✅ 0 agregados y 3 rechazados por duplicado. |
| Búsqueda semántica en español e inglés | ✅ «sociedad en la que los bomberos queman libros» → *Fahrenheit 451*; «niño huérfano que descubre que es mago» → *Harry Potter*; «un capitán obsesionado con una ballena blanca» → *Moby Dick*; «a girl grows up alone in the marsh» → *Donde cantan los cangrejos*. Todos dentro del top 3. |
| Cifrado real en Redis | ✅ El HASH guarda `v2:…`, sin el nombre en claro; el descifrado devuelve el valor original. |
| Préstamo y sincronización | ✅ La disponibilidad cambia en Redis y en Chroma; un libro prestado no aparece en «solo disponibles» ni se puede volver a prestar. |
| Devoluciones | ✅ La disponibilidad se restablece en ambas bases y el historial conserva los 2 préstamos. |
| Actualización y eliminación | ✅ La calificación nueva llega a Chroma; el libro eliminado desaparece de ambas bases. |
| Consistencia final | ✅ `revisar_sincronizacion().consistente == True`. |

**Arranque real de la aplicación** (`main.main()`): conexión a la base 2, verificación de la base, acceso con la contraseña del operador, carga del modelo (`cuda:0 · float16`) y navegación a Configuración › Sistema sin errores. `biblioteca.log` solo registró «Aplicación iniciada (Redis db 2, modelo qwen3-embedding-0.6b)» y «Aplicación cerrada», sin datos personales.

## 4. Calidad de la búsqueda semántica

`evaluar_busqueda.py` indexa los **200 libros** y ejecuta **60 consultas** etiquetadas (`datos/consultas_evaluacion.json`) en cinco categorías:

- **Paráfrasis** (26): describen el libro sin usar sus palabras clave.
- **Discriminación** (18): el libro correcto convive con otros de tema parecido.
- **Conceptual** (10): preguntan por ideas, no por argumentos.
- **Inglés** (4): consultas en otro idioma sobre sinopsis en español.
- **Técnica** (2): libros de programación.

Cada modelo se ejecutó en un proceso separado para medir la VRAM.

| Modelo | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR | Indexar 200 | Consulta | VRAM pico |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Qwen3-Embedding-0.6B, instrucción genérica (por defecto)** | **90 %** | **100 %** | **100 %** | **100 %** | **0.944** | 1.6 s | 44 ms | — ¹ |
| Qwen3-Embedding-0.6B, instrucción para libros | 88 % | 97 % | 97 % | 100 % | 0.926 | 1.6 s | 51 ms | 1.74 GB |
| paraphrase-multilingual-MiniLM-L12-v2 (modelo original del proyecto) | 82 % | 92 % | 95 % | 95 % | 0.864 | 0.4 s | 12 ms | 0.51 GB |

¹ Se ejecutó en el mismo proceso que la variante anterior, así que su pico (2.85 GB) incluye memoria no liberada. El consumo propio de Qwen es el de la otra fila: el modelo ocupa unos 1.12 GB y la indexación por lotes alcanza 1.74 GB.

Hit@k es el porcentaje de consultas cuyo libro correcto aparece entre los k primeros resultados. MRR es la media del inverso de la posición del primer acierto.

### Por categoría (Hit@1)

| Modelo | Conceptual (10) | Discriminación (18) | Inglés (4) | Paráfrasis (26) | Técnica (2) |
|---|---:|---:|---:|---:|---:|
| Qwen3, instrucción genérica | 100 % | 100 % | 100 % | 77 % | 100 % |
| Qwen3, instrucción para libros | 100 % | 94 % | 100 % | 77 % | 100 % |
| MiniLM-L12 | 80 % | 89 % | 100 % | 73 % | 100 % |

### Consultas sin acierto en primera posición

**Qwen3, instrucción genérica (6 de 60). Todas tienen el acierto en la posición 2 o 3:**

- q01 «capitán obsesionado con vengarse de un animal marino gigantesco y blanco» → 1.º *Veinte mil leguas de viaje submarino*, *Moby Dick* en la posición 2.
- q05 «científico que toma un brebaje y se convierte en otra persona malvada» → 1.º *Frankenstein*, *Jekyll y Hyde* en la posición 2.
- q22 «novelista que se apropia de la obra inédita de una colega fallecida» → *Yellowface* en la posición 3.
- q35 «un hijo busca a su padre en un pueblo donde solo quedan fantasmas» → *Pedro Páramo* en la posición 2.
- q37 «dos familias de un pueblo vasco separadas por un atentado» → *Patria* en la posición 3.
- q56 «academia militar donde los cadetes se vinculan con dragones» → 1.º *La ciudad y los perros*, *Alas de sangre* en la posición 2.

**MiniLM-L12 (11 de 60). Tres quedan fuera del top 10:** q05 (*Jekyll y Hyde*), q36 (*Temporada de huracanes*) y q37 (*Patria*).

### Conclusiones

- Qwen3-Embedding-0.6B mejora al modelo original en **+8 puntos de Hit@1** y siempre coloca la respuesta entre los tres primeros resultados. La mayor ganancia está en las consultas conceptuales (+20 puntos) y en distinguir libros de tema parecido (+11 puntos).
- La instrucción genérica que trae el modelo superó a la escrita para libros, por eso es la predeterminada. La diferencia es de una consulta en el primer puesto y de tres en el top 3.
- Sus errores son confusiones razonables entre obras de tema cercano, como ballena y submarino o una pócima frente a una criatura creada por un científico.
- Con este catálogo el límite de longitud no es un problema: la sinopsis más larga ocupa 147 tokens con el tokenizador de Qwen, frente a un máximo configurado de 512. MiniLM corta 1 de las 75 sinopsis originales (136 tokens frente a 128).

## 5. Verificación visual de la interfaz

Se lanzó la interfaz real con el modelo Qwen en la GPU, los 200 libros y 4 personas de demostración. Estos datos estaban en memoria (fakeredis) y no se guardaron en el Redis del usuario. Se capturaron las 7 secciones, la pantalla de acceso y el formulario con errores. Las capturas permitieron detectar y corregir los recortes en pantallas de alta densidad descritos en la sección 2. En la versión final se comprobó que:

- El Dashboard muestra indicadores reales (200 libros, 194 disponibles, 6 prestados, 1 vencido) que coinciden con los datos.
- El catálogo, la búsqueda, los préstamos, la vista agrupada de personas con préstamos y Configuración se ven completos, sin recortes, a la escala del 133 %.
- Los botones deshabilitados se distinguen visualmente, se muestran mensajes cuando una tabla está vacía y el formulario muestra los errores en línea.

### Portadas de los libros

Prueba real contra Open Library con 10 libros elegidos al azar del catálogo (5 del catálogo original y 5 del ampliado). Las imágenes se guardaron en una carpeta temporal; Redis solo se leyó.

- Se encontraron **8 de 10** portadas en 42 s (unos 4 s por libro, por la pausa de 1 s entre peticiones). No se encontraron *Breve historia del tiempo* ni *Neuromante*.
- Se revisaron visualmente las 8 imágenes: todas corresponden al libro correcto, incluidas las del catálogo ampliado, cuyos ISBN son ilustrativos y se resolvieron por título y autor.
- El primer intento falló por un tiempo de espera agotado al conectar con openlibrary.org. La aplicación mostró el error previsto (`ErrorPortada`) y, a raíz de ello, cada petición se reintenta una vez.
- Con la interfaz real (modo de demostración) se capturaron la ficha del catálogo con portada y sin ella, la búsqueda y Configuración › Sistema: se ven completas, sin recortes.

## 6. Diagnóstico del entorno (`verificar.py`)

```
Python 3.14.6 · tkinter · chromadb 1.5.9 · redis 8.1.0 · sentence_transformers 6.1.0
torch 2.14.1+cu130 · cryptography 50.0.2 · dotenv · numpy 2.5.3            [OK]
Redis responde en localhost:6379, base 2; solo llaves con prefijo 'bib:'     [OK]
dispositivo: cuda (NVIDIA GeForce RTX 4060 Laptop GPU)                       [OK]
qwen3-embedding-0.6b descargado en la caché local                           [OK]
llave AES-256 presente · contraseña de operador configurada                 [OK]
```

## 6.1 Distribución: descarga del modelo y Redis con Docker Compose

| Comprobación | Resultado |
|---|---|
| Descarga real del modelo a una carpeta vacía (`python gestionar_modelos.py descargar`) | ✅ 1207.5 MB de la revisión `97b0c614…` en 1010 s; solo los 10 archivos necesarios. |
| Validación tras la descarga | ✅ 1024 dimensiones en `cuda:0 · float16`. |
| Reutilización | ✅ La segunda ejecución no descarga nada (1 s). |
| Progreso incremental | ✅ 52 actualizaciones durante la descarga de un archivo de 11 MB. |
| `docker compose up -d` | ✅ Contenedor `healthy`, publicado solo en `127.0.0.1:<REDIS_PORT>`. |
| Contraseña opcional | ✅ Con `REDIS_PASSWORD` se rechaza el acceso sin autenticar (`NOAUTH`) y la aplicación conecta con la contraseña; una contraseña incorrecta produce `AuthenticationError`. Sin `REDIS_PASSWORD` responde `PONG`. |
| Persistencia de Redis | ✅ El dato se conserva tras `docker compose restart` y tras `down` + `up` (volumen `redis_datos`, AOF activo). |
| Política de reinicio | ✅ `unless-stopped`. |

Las pruebas de Compose usaron proyectos y puertos aislados (6391 y 6392), que se eliminaron después con sus volúmenes.

## 7. Limitaciones y lo que no se comprobó

- **Ejecución en CPU**: no se probó el modelo sin GPU. El código usa float32 en CPU, pero no se midió su rendimiento.
- **Modelos e5 y `sentence_similarity_spanish_es`**: no están descargados; la evaluación y el cambio de modelo real solo se probaron con Qwen y MiniLM. El cambio de modelo se probó con el modelo simulado.
- **Fallos reales de red o de disco**: la compensación entre Redis y Chroma se probó con fallos simulados, no desconectando servicios reales a mitad de una operación.
- **Concurrencia entre varios clientes**: las transacciones `WATCH/MULTI` se validaron en un solo proceso; no se lanzaron dos aplicaciones a la vez contra la misma base.
- **Bloqueo por inactividad y espera tras intentos fallidos**: la lógica está implementada y se probó el bloqueo manual. El paso de 15 minutos y la espera de 30 segundos no se cronometraron en una prueba automatizada.
- **Otros sistemas operativos**: solo se probó en Windows 11. En Linux y macOS los iconos usan el respaldo Unicode.
- **Fallos intermitentes del entorno Windows** observados durante la verificación final:
  1. Tk no pudo leer su `init.tcl` («couldn't read file … No error»), un problema transitorio de acceso al archivo. La prueba de interfaz ahora reintenta crear la ventana.
  2. Una vez, ChromaDB informó «Error in compaction» en la base temporal de una prueba de interfaz. Además, al cerrar cada prueba ahora se espera al hilo trabajador. No se reprodujo en las 3 corridas completas posteriores (76/76 en cada una). Causa no confirmada; las hipótesis son el acceso concurrente a archivos (antivirus, disco al 95 %) o un hilo de la prueba anterior todavía activo. Si ocurriera en la aplicación, la operación se compensa y se informa al usuario.
- **Descarga de las 200 portadas**: no se ejecutó completa contra Open Library; se probó con una muestra de 10 libros. A unos 4 s por libro, la descarga completa tardaría del orden de 10 a 15 minutos.
- **TLS**: no se probó Redis con TLS (`rediss://`). La contraseña sí se probó con Docker Compose.
- **GitHub Actions**: el flujo `.github/workflows/pruebas.yml` no se ha ejecutado; correrá en GitHub después de publicar.
- **Instalación desde cero en otro equipo**: no se creó un entorno virtual nuevo e independiente. Las dependencias se verificaron analizando las importaciones frente a `requirements.txt`.
