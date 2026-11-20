# Biblioteca · Administrador de Préstamos de Libros

Aplicación de escritorio en **Python + Tkinter** para administrar el acervo, los usuarios y los préstamos de una biblioteca. Incluye **búsqueda semántica** de libros por el significado de su sinopsis y **protección de datos personales** inspirada en la LFPDPPP.

> Proyecto académico de la materia de Bases de Datos NoSQL: combina un almacén clave-valor (Redis) con una base vectorial (ChromaDB) y un modelo de embeddings multilingüe.

---

## Instalación rápida para colaboradores

Requisitos previos: Python 3.10–3.14, Git y **un servidor Redis 6+ en funcionamiento** (tu instalación local; Docker es opcional). Ver [Requisitos](#requisitos).

```bash
# 1. Clonar
git clone https://github.com/<usuario>/<repositorio>.git
cd <repositorio>

# 2. Entorno virtual
python -m venv .venv
# Windows (PowerShell):   .\.venv\Scripts\Activate.ps1
# Linux / macOS:          source .venv/bin/activate

# 3. Dependencias (PyTorch primero: elige CUDA o CPU, ver "Instalación de dependencias")
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# 4. Configuración local
cp .env.example .env            # Windows: copy .env.example .env

# 5. Redis: comprueba que tu servidor responde y que la base elegida (REDIS_DB=2) está vacía
redis-cli ping                  # → PONG
redis-cli -n 2 DBSIZE           # → 0   (si no, elige otra REDIS_DB vacía en .env)
#    ¿Sin Redis instalado? Opcional:  docker compose up -d

# 6. Diagnóstico (Redis, modelo, llaves)
python verificar.py

# 7. Ejecutar
python main.py
```

Al abrir la aplicación por primera vez:

1. **Crea tu contraseña de operador.** La pantalla de acceso la pide.
2. **Descarga el modelo.** Si no está en tu equipo, la aplicación ofrece descargarlo (~1.2 GB, una sola vez).
3. **Carga los datos de ejemplo** desde **Configuración › Sistema › Cargar datos de ejemplo** (200 libros).

Cada instalación genera **su propia llave de cifrado** y usa **su propio Redis y su propia ChromaDB**: no se comparte ningún dato entre integrantes.

> **¿Trabajas solo en la interfaz?** `python demo_interfaz.py` abre la aplicación completa con datos de ejemplo **en memoria** (sin Redis, sin GPU y sin tocar datos reales; contraseña `demo1234`). Lee [INTEGRACION.md](INTEGRACION.md).

---

## Contenido

- [Características](#características)
- [Tecnologías](#tecnologías)
- [Arquitectura](#arquitectura)
- [Requisitos](#requisitos)
- [Instalación paso a paso](#instalación-paso-a-paso)
- [Ejecución](#ejecución)
- [Modelo semántico: distribución y licencia](#modelo-semántico-distribución-y-licencia)
- [Configuración y claves](#configuración-y-claves)
- [Solución de errores comunes](#solución-de-errores-comunes)
- [Pruebas](#pruebas)
- [Colaborar](#colaborar)
- [Estructura del proyecto](#estructura-del-proyecto)

---

## Características

- **Dashboard** con indicadores reales: libros (totales, disponibles y prestados), personas, préstamos activos, vencidos e históricos, actividad reciente y próximos vencimientos.
- **Libros**: catálogo con filtros, búsqueda por texto, ordenamiento y ficha completa. Alta validada (ISBN con dígito de control, campos obligatorios), **importación por lote** desde CSV o JSON con reporte por fila, edición, eliminación con confirmación y «Buscar similares».
- **Búsqueda semántica**: consultas en lenguaje natural, en español u otros idiomas, comparadas por significado con las sinopsis.
- **Personas**: alta con aceptación obligatoria del aviso de privacidad y edad calculada automáticamente. Búsqueda por nombre y campos no sensibles, y derechos ARCO: acceso, exportación a JSON, rectificación y cancelación.
- **Préstamos**: de 1 a 3 libros por persona, en una sola operación o en varias, con fecha y estado. Devoluciones de uno, de varios o de todos los libros, **conservando el historial**.
- **Personas con préstamos**: vista agrupada; el contacto se muestra solo a petición.
- **Configuración**: descarga y cambio del modelo con reindexado, contador de tokens, sincronización Redis ↔ Chroma, seguridad y estado del sistema.
- **Seguridad**: AES-256-GCM por campo, contraseña de operador (scrypt), bloqueo por inactividad y registro sin datos personales.

## Tecnologías

| Tecnología | Uso |
|---|---|
| Python 3.10+ / Tkinter (ttk) | Aplicación de escritorio. |
| Redis 6+ (instalación local o Docker opcional) | Fuente de verdad: libros, personas cifradas, préstamos con historial y bitácora. |
| ChromaDB 1.5 | Índice vectorial persistente: sinopsis, embeddings y metadatos. |
| sentence-transformers + PyTorch | Ejecución del modelo de embeddings (GPU con CUDA o CPU). |
| Hugging Face Hub | Descarga del modelo en una revisión fija. |
| cryptography | AES-256-GCM y HKDF. |
| pytest + fakeredis | Pruebas automatizadas. |

## Arquitectura

```
Interfaz Tkinter (ui/) ──► servicios.py ──┬─► db_catalogo · db_personas · db_prestamos ──► Redis
                                          └─► db_libros ──► modelos.py / gestor_modelos.py ──► ChromaDB
```

- **Redis** guarda los identificadores, los metadatos y la disponibilidad de los libros, las personas (cifradas), los préstamos y la bitácora, en una base dedicada con prefijo `bib:`.
- **ChromaDB** guarda las sinopsis (`documents`), los embeddings y una copia de los metadatos (`metadatas`).
- Las operaciones que tocan ambas bases **compensan los fallos**. Préstamos y devoluciones usan transacciones `WATCH/MULTI`.

Detalle completo en [ARQUITECTURA.md](ARQUITECTURA.md).

## Requisitos

| | Mínimo | Recomendado |
|---|---|---|
| Sistema | Windows 10/11, Linux o macOS | Windows 11 o Linux |
| Python | 3.10 con Tkinter | 3.12–3.14 |
| RAM | 8 GB | 16 GB |
| Disco | 4 GB (dependencias + modelo de 1.2 GB) | 6 GB |
| GPU | No necesaria (funciona en CPU) | NVIDIA con 2 GB de VRAM y CUDA |
| Redis | 6.0 o superior, local o accesible por red | 7.x u 8.x |
| Docker | **Opcional**: solo si no tienes Redis instalado | — |

## Instalación paso a paso

### 1. Python

- **Windows**: descarga el instalador de [python.org](https://www.python.org/downloads/). Marca **«Add python.exe to PATH»** y, en *Optional features*, **«tcl/tk and IDLE»** (Tkinter).
- **Linux (Debian/Ubuntu)**: `sudo apt install python3 python3-venv python3-tk`
- **macOS**: `brew install python python-tk`

Comprueba la instalación con `python --version` y `python -m tkinter`; el segundo comando abre una ventana pequeña.

### 2. Git

- **Windows**: [git-scm.com/download/win](https://git-scm.com/download/win).
- **Linux**: `sudo apt install git`
- **macOS**: `xcode-select --install`

Configura tu identidad una vez:

```bash
git config --global user.name "Tu Nombre"
git config --global user.email "tu-correo@ejemplo.com"
```

### 3. Docker (opcional)

Solo hace falta si no tienes Redis instalado. Instala [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows o macOS) o Docker Engine con el plugin Compose (Linux), y comprueba con `docker compose version`.

### 4. Clonar el repositorio

```bash
git clone https://github.com/<usuario>/<repositorio>.git
cd <repositorio>
```

### 5. Instalación de dependencias

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Windows PowerShell
source .venv/bin/activate             # Linux / macOS
python -m pip install --upgrade pip
```

Instala primero **PyTorch** según tu hardware ([guía oficial](https://pytorch.org/get-started/locally/)):

```bash
# GPU NVIDIA (ajusta cu130/cu128/cu126 a tu versión de CUDA)
pip install torch --index-url https://download.pytorch.org/whl/cu130
# Solo CPU
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

Y después el resto:

```bash
pip install -r requirements.txt
```

### 6. Configuración de Redis

La aplicación funciona con **cualquier Redis 6+**: el que ya tienes instalado, uno en otro equipo de la red o, de forma opcional, el de `docker-compose.yml`.

#### 6.1 Usar tu instalación local de Redis (recomendado)

1. **Comprueba que Redis está en marcha:**

   | Sistema | Iniciar el servicio | Verificar |
   |---|---|---|
   | Linux / WSL | `sudo service redis-server start` (o `sudo systemctl start redis-server`) | `redis-cli ping` → `PONG` |
   | macOS (Homebrew) | `brew services start redis` | `redis-cli ping` → `PONG` |
   | Windows | Inicia el servicio de Redis o Memurai (*services.msc*), o Redis dentro de WSL | `redis-cli ping` (o `memurai-cli ping`) → `PONG` |

   Si tu Redis tiene contraseña: `redis-cli -a TU_CONTRASEÑA ping`. Con un usuario ACL: `redis-cli --user USUARIO -a TU_CONTRASEÑA ping`. En otro equipo o puerto: `redis-cli -h HOST -p PUERTO ping`.

2. **Elige una base de datos vacía** (Redis tiene las bases 0–15). La aplicación usa la 2 por defecto y **se niega a arrancar si la base contiene llaves de otro proyecto**:
   ```bash
   redis-cli -n 2 DBSIZE          # debe responder 0; si no, prueba otra base y ajusta REDIS_DB
   ```
3. **Configura la conexión** en `.env` (copiado de `.env.example`):

   | Variable | Ejemplo | Para qué |
   |---|---|---|
   | `REDIS_HOST` | `localhost` | Equipo donde corre Redis. |
   | `REDIS_PORT` | `6379` | Puerto. |
   | `REDIS_DB` | `2` | Base dedicada y vacía. |
   | `REDIS_USUARIO` | *(vacío)* | Usuario ACL (Redis 6+), solo si lo usas. |
   | `REDIS_PASSWORD` | *(vacío)* | Contraseña (`requirepass` o ACL). |
   | `REDIS_SSL` | `0` | `1` para TLS (Redis remoto o en la nube). |
   | `REDIS_PREFIJO` | `bib:` | Prefijo de todas las llaves de la aplicación. |
   | `REDIS_TIMEOUT` | `3` | Segundos de espera al conectar. |

   Las variables de entorno del sistema tienen prioridad sobre `.env`, así que también puedes hacer `REDIS_PORT=6380 python main.py`.
4. **Verifica desde el proyecto:**
   ```bash
   python verificar.py
   ```
   Debe mostrar `[OK] responde en HOST:PUERTO, base N` y `[OK] la base solo contiene llaves con el prefijo 'bib:'`.

#### 6.2 Alternativa opcional: Redis con Docker Compose

Para quien no tenga Redis instalado. Lee `REDIS_PORT`, `REDIS_PASSWORD` y `REDIS_BIND` del mismo `.env`:

| Acción | Comando |
|---|---|
| Iniciar | `docker compose up -d` |
| Estado (debe decir *healthy*) | `docker compose ps` |
| Detener (conserva los datos) | `docker compose stop` |
| Eliminar el contenedor (conserva el volumen) | `docker compose down` |
| Borrar también los datos | `docker compose down -v` |
| Ver el registro | `docker compose logs -f redis` |

Publica Redis solo en `127.0.0.1` y usa persistencia AOF en un volumen. Si ya tienes otro Redis en 6379, cambia `REDIS_PORT` (por ejemplo, a `6380`).

### 7. Preparación de ChromaDB

No requiere instalación aparte: es una base embebida. Los datos se guardan en `BIBLIOTECA_CHROMA_PATH` (por defecto `./chroma_db`), que se crea al primer arranque, persiste entre ejecuciones y está excluida de git. Para empezar de cero, cierra la aplicación y borra esa carpeta. Si también quieres borrar los datos de Redis, usa `docker compose down -v`.

### 8. Descarga automática del modelo

Al abrir la aplicación, si el modelo no está en tu equipo aparece un diálogo con el tamaño, el destino y el espacio libre, y la opción de descargarlo con barra de progreso. También puedes descargarlo desde la terminal:

```bash
python gestionar_modelos.py estado        # qué modelos están descargados
python gestionar_modelos.py descargar     # descarga el modelo activo (revisión fija) y lo valida
python gestionar_modelos.py validar       # comprueba que carga y produce vectores de 1024 dimensiones
```

La descarga se reutiliza en ejecuciones posteriores y, si se interrumpe, solo se descargan los archivos que faltan.

### 9. Configuración de claves

No hay nada que copiar de otro integrante: **cada instalación crea sus propios secretos**.

- **Llave de cifrado (AES-256)**: se genera en `secrets/biblioteca_aes.key` al primer arranque. Alternativa: `python gestionar_secretos.py nueva-llave` y pegar el resultado en `BIBLIOTECA_AES_KEY` dentro de `.env`.
- **Contraseña de operador**: se crea en la pantalla de acceso o con `python gestionar_secretos.py contrasena`.
- **Respaldo**: copia `secrets/` a un lugar seguro, como un gestor de contraseñas o una memoria cifrada. Sin la llave, los datos personales de tu Redis **no se pueden recuperar**.
- **Recuperación**: restaura `secrets/biblioteca_aes.key` (o `BIBLIOTECA_AES_KEY`) antes de abrir la aplicación. Si olvidas la contraseña de operador, cámbiala con `python gestionar_secretos.py contrasena`: no afecta a los datos cifrados.

Más detalle en [SEGURIDAD.md](SEGURIDAD.md).

## Ejecución

```bash
python verificar.py      # diagnóstico: dependencias, configuración, Redis, modelo y secretos
python main.py           # aplicación
```

### Apariencia y animaciones

La interfaz usa la paleta índigo del proyecto, tipografía con serifa para los títulos (Cambria, Georgia u otra disponible en el sistema) y la fuente sans del sistema para la lectura. Las animaciones (contadores del dashboard, transiciones de botones, avisos y el fondo de la pantalla de acceso) son breves y no bloquean la ventana ni las tareas en curso. Para desactivarlas, define la variable de entorno `BIBLIOTECA_SIN_ANIMACIONES=1` antes de ejecutar; las pruebas ya la activan por sí solas.

Si `main.py` se ejecuta con un Python que no tiene las dependencias (por ejemplo, la extensión Code Runner usando el Python global), se relanza automáticamente con `.venv` o `../.venv` si existen.

## Modelo semántico: distribución y licencia

| Dato | Valor |
|---|---|
| Modelo | **Qwen3-Embedding-0.6B** |
| Repositorio | [`Qwen/Qwen3-Embedding-0.6B`](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) |
| Revisión fijada | `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3` |
| Licencia | **Apache-2.0** (de Alibaba/Qwen; no es la licencia de este proyecto) |
| Tamaño | ~1.21 GB (`model.safetensors` 1.19 GB + tokenizador y configuración) |
| Archivos descargados | `model.safetensors`, `config.json`, `modules.json`, `config_sentence_transformers.json`, `1_Pooling/config.json`, `tokenizer.json`, `tokenizer_config.json`, `vocab.json`, `merges.txt`, `generation_config.json` |
| Embeddings | 1024 dimensiones, *last-token pooling*, normalizados (coseno) |
| Ejecución | float16 en GPU, float32 en CPU; instrucción solo en las consultas |
| Ubicación local | `BIBLIOTECA_DIR_MODELOS` o, si está vacío, la caché de Hugging Face (`~/.cache/huggingface/hub`) |

**Los pesos no se incluyen en el repositorio.** Se descargan de Hugging Face Hub en la revisión fijada, de modo que todos los integrantes usan exactamente los mismos archivos y obtienen los mismos embeddings. La aplicación nunca descarga nada sin que el usuario lo acepte (`BIBLIOTECA_PERMITIR_DESCARGA=0` lo desactiva por completo).

Modelos alternativos, seleccionables en Configuración (cada uno con su revisión fijada):

| Modelo | Licencia | Tamaño |
|---|---|---|
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Apache-2.0 | ~500 MB |
| `intfloat/multilingual-e5-small` | MIT | ~490 MB |
| `intfloat/multilingual-e5-base` | MIT | ~1.1 GB |
| `hiiamsid/sentence_similarity_spanish_es` | Apache-2.0 | ~440 MB |

Cambiar de modelo reindexa las sinopsis en una colección propia. La calidad medida de cada modelo está en [PRUEBAS.md](PRUEBAS.md).

## Configuración y claves

Toda la configuración está en `.env`; [`.env.example`](.env.example) documenta cada variable. `config.py` valida los valores al arrancar y muestra mensajes claros: puertos fuera de rango, prefijos inválidos, un modelo inexistente, una llave mal formada o una carpeta sin permisos.

| Variable | Por defecto | Descripción |
|---|---|---|
| `REDIS_HOST` / `REDIS_PORT` / `REDIS_DB` | `localhost` / `6379` / `2` | Conexión a Redis. |
| `REDIS_USUARIO` / `REDIS_PASSWORD` | vacío | Credenciales, si tu Redis las exige (Docker Compose también usa `REDIS_PASSWORD`). |
| `REDIS_SSL` | `0` | Conexión TLS. |
| `REDIS_PREFIJO` | `bib:` | Prefijo de todas las llaves. |
| `BIBLIOTECA_CHROMA_PATH` | `chroma_db` | Carpeta de ChromaDB. |
| `BIBLIOTECA_MODELO` | `qwen3-embedding-0.6b` | Modelo activo por defecto. |
| `BIBLIOTECA_DIR_MODELOS` | caché de Hugging Face | Carpeta de modelos descargados. |
| `BIBLIOTECA_PERMITIR_DESCARGA` | `1` | `0` impide cualquier descarga. |
| `BIBLIOTECA_DISPOSITIVO` | `auto` | `auto`, `cuda` o `cpu`. |
| `BIBLIOTECA_DIR_SECRETOS` | `secrets` | Carpeta de la llave AES y del hash de la contraseña. |
| `BIBLIOTECA_AES_KEY` | vacío | Llave AES en base64 (tiene prioridad sobre el archivo). |
| `BIBLIOTECA_MINUTOS_BLOQUEO` | `15` | Bloqueo por inactividad. |
| `BIBLIOTECA_DIAS_PRESTAMO` | `14` | Plazo de los préstamos. |

## Solución de errores comunes

| Síntoma | Causa y solución |
|---|---|
| `ModuleNotFoundError: No module named 'chromadb'` | Se ejecutó con un Python sin dependencias. Activa `.venv` o selecciona su intérprete en el IDE (VS Code: *Python: Select Interpreter*). |
| «No se pudo conectar a Redis» | Redis no está encendido o el host o puerto no coinciden. Inicia tu servicio (ver 6.1), comprueba con `redis-cli -h HOST -p PUERTO ping` y revisa `REDIS_HOST`/`REDIS_PORT`. |
| `port is already allocated` al hacer `docker compose up` | Otro programa usa ese puerto: cambia `REDIS_PORT` en `.env`. |
| «Redis rechazó la conexión» | `REDIS_USUARIO`/`REDIS_PASSWORD` no coinciden con los del servidor. Si la cambiaste después de crear el volumen, recrea el contenedor: `docker compose up -d --force-recreate`. |
| «Base de Redis ocupada» | La base elegida tiene llaves de otro proyecto: usa otra `REDIS_DB` vacía. |
| «Modelo no disponible» | Descárgalo desde el diálogo o con `python gestionar_modelos.py descargar`. |
| «No hay conexión con Hugging Face Hub» | Revisa tu conexión, el proxy o el firewall, y que `HF_HUB_OFFLINE` no esté definido. Reintenta: solo se descargan los archivos faltantes. |
| «Espacio insuficiente» | Libera espacio o define `BIBLIOTECA_DIR_MODELOS` en otra unidad. |
| `No module named 'tkinter'` / `_tkinter` | Reinstala Python con Tcl/Tk (Windows) o `sudo apt install python3-tk`. |
| `CUDA out of memory` o una GPU sin soporte | Usa `BIBLIOTECA_DISPOSITIVO=cpu`. |
| «Error de integridad» o datos ilegibles | Cambió la llave de cifrado: restaura tu respaldo de `secrets/biblioteca_aes.key`. |
| Iconos como cuadros en Linux o macOS | Normal: se usan símbolos Unicode de respaldo en lugar de la fuente Segoe Fluent Icons. |

## Pruebas

```bash
python -m pytest tests                                   # pruebas sin servicios externos
BIBLIOTECA_PRUEBAS_REALES=1 python -m pytest tests       # + integración con Redis, Chroma y el modelo reales
python evaluar_busqueda.py                               # calidad de la búsqueda (Hit@k, MRR)
```

En PowerShell: `$env:BIBLIOTECA_PRUEBAS_REALES="1"; python -m pytest tests`. Los resultados están en [PRUEBAS.md](PRUEBAS.md).

## Colaborar

Responsabilidades (frontend / backend), módulos que cada área puede modificar, flujo de ramas (`main`, `develop`, `feature/*`, `fix/*`), commits y Pull Requests en [CONTRIBUTING.md](CONTRIBUTING.md). El contrato entre la interfaz y el backend, con la API, los ejemplos y las excepciones, está en [INTEGRACION.md](INTEGRACION.md).

## Datos de ejemplo

| Archivo | Contenido |
|---|---|
| `datos/libros_lote.csv` · `datos/libros_lote_nuevos.csv` | 75 libros (libro01–libro75). |
| `datos/libros_catalogo_ampliado.csv` | 125 libros (libro76–libro200): clásicos, éxitos de venta, novedades 2020–2024 y divulgación. |
| `datos/consultas_evaluacion.json` | 60 consultas etiquetadas para medir la búsqueda. |

Título, autor, año y argumento corresponden a las obras reales; **las sinopsis son de redacción propia**. En el catálogo ampliado, ISBN, editorial, páginas y calificación son **ilustrativos**. El repositorio **no contiene datos personales**: las personas se registran en cada instalación local.

## Estructura del proyecto

```
├── main.py                  Punto de entrada
├── config.py                Configuración centralizada y validación (.env)
├── validaciones.py          Reglas de libros y personas
├── seguridad.py             AES-256-GCM, HKDF, HMAC, scrypt, aviso de privacidad
├── modelos.py               Catálogo de modelos (revisiones fijadas) y carga
├── gestor_modelos.py        Disponibilidad, descarga con progreso y validación de modelos
├── db_redis.py              Conexión, espacio de nombres y bitácora
├── db_catalogo.py           Libros en Redis
├── db_personas.py           Personas cifradas en Redis
├── db_prestamos.py          Préstamos con historial (WATCH/MULTI)
├── db_libros.py             Índice semántico en ChromaDB
├── servicios.py             Lógica de negocio y API pública para la interfaz (ver INTEGRACION.md)
├── ui/                      Interfaz: tema, fondos ilustrados y animaciones (fondos.py), componentes, acceso,
│                            descarga del modelo y 7 secciones
├── datos/                   Datasets y consultas de evaluación
├── tests/                   Pruebas automatizadas
├── docker-compose.yml       Redis con persistencia (opcional)
├── demo_interfaz.py         Interfaz con datos en memoria para trabajar en el frontend
├── modelo_simulado.py       Modelo de embeddings simulado (pruebas y demostración)
├── gestionar_modelos.py     CLI de modelos
├── gestionar_secretos.py    CLI de llave y contraseña
├── verificar.py             Diagnóstico del entorno
├── evaluar_busqueda.py      Evaluación de la búsqueda semántica
└── comparar_modelos.py      Comparación entre dos modelos
```

No se versionan (ver `.gitignore`): `.env`, `secrets/`, `chroma_db/`, los modelos descargados, los registros ni los entornos virtuales.

## Documentación

[ARQUITECTURA.md](ARQUITECTURA.md) · [INTEGRACION.md](INTEGRACION.md) · [SEGURIDAD.md](SEGURIDAD.md) · [PRUEBAS.md](PRUEBAS.md) · [CONTRIBUTING.md](CONTRIBUTING.md) · [ANALISIS_PROYECTO.md](ANALISIS_PROYECTO.md) · [GITHUB_PUBLICACION.md](GITHUB_PUBLICACION.md)

## Licencia

Código distribuido bajo la licencia **MIT** (ver [LICENSE](LICENSE)), © 2026 Vessel-dot. El modelo Qwen3-Embedding-0.6B no forma parte del repositorio: se descarga por separado y se rige por su propia licencia Apache-2.0.
