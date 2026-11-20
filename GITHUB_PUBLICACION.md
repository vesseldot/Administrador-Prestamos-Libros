# Preparación para la publicación en GitHub

Fecha: 2026-11-19. Estado: **publicación autorizada** en `https://github.com/vesseldot/Administrador-Prestamos-Libros` (público), con las ramas `main` y `develop`.

Se creó un repositorio Git **local** (`git init -b main`), sin commits y sin remotos. No se ejecutó `git push`, no se creó ningún repositorio en GitHub y no se modificó ningún historial (no existía uno previo).

## 1. Archivos incluidos (72 archivos, ~0.6 MB sin comprimir)

| Grupo | Archivos |
|---|---|
| Aplicación | `main.py`, `config.py`, `validaciones.py`, `seguridad.py`, `modelos.py`, `gestor_modelos.py`, `servicios.py`, `db_redis.py`, `db_catalogo.py`, `db_personas.py`, `db_prestamos.py`, `db_libros.py`, `modelo_simulado.py` |
| Interfaz | `ui/` (tema, componentes, acceso, tareas, descarga del modelo, ventana y `ui/vistas/` con 7 secciones) |
| Herramientas | `verificar.py`, `gestionar_modelos.py`, `gestionar_secretos.py`, `evaluar_busqueda.py`, `comparar_modelos.py`, `demo_interfaz.py` |
| Datos de ejemplo | `datos/libros_lote.csv`, `datos/libros_lote_nuevos.csv`, `datos/libros_catalogo_ampliado.csv`, `datos/consultas_evaluacion.json` (sin datos personales) |
| Pruebas | `tests/` (12 archivos, 124 pruebas) |
| Entorno | `requirements.txt`, `docker-compose.yml`, `.env.example`, `.gitignore`, `.gitattributes` |
| Colaboración | `CONTRIBUTING.md`, `INTEGRACION.md`, `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/` (error y funcionalidad), `.github/CODEOWNERS` (plantilla comentada), `.github/workflows/pruebas.yml` |
| Documentación | `README.md`, `INTEGRACION.md`, `PRUEBAS.md`, `CONTRIBUTING.md`, `ANALISIS_PROYECTO.md`, `GITHUB_PUBLICACION.md` y la carpeta `docs/` (guías, arquitectura, seguridad y sus PDF) |

El archivo más grande es `datos/libros_catalogo_ampliado.csv` (48 KB). Lista exacta: `git add --dry-run .`

## 2. Archivos excluidos (`.gitignore`)

Excluidos que existen hoy en la carpeta, verificado con `git status --ignored`:

| Archivo o carpeta | Motivo |
|---|---|
| `.env` | Configuración local. No contiene secretos, pero es de cada equipo. |
| `secrets/` (`biblioteca_aes.key`, `operador.hash`) | **Llave AES-256 y hash de la contraseña del operador.** |
| `clave.key` | **Llave Fernet heredada del proyecto original.** |
| `chroma_db/` | Índice vectorial local (embeddings y sinopsis). |
| `biblioteca.log` | Registro local. |
| `__pycache__/` (3 carpetas) | Caché de Python. |

`.gitignore` excluye además, aunque hoy no existan:

- Entornos virtuales y otras variantes de `.env`.
- Archivos `*.key`, `*.pem`, `*.p12` y `*.pfx`.
- Bases locales (`*.sqlite3`, `*.db`), persistencia de Redis (`*.rdb`, `*.aof`, `appendonlydir/`) y exportaciones ARCO (`datos_P*.json`).
- Modelos y pesos (`modelos_descargados/`, `*.safetensors`, `*.bin`, `*.pt`, `*.onnx`, `*.gguf`, `huggingface/`), embeddings locales (`*.npy`, `*.parquet`) y `modelo_activo.txt`.
- Cachés de pruebas, archivos temporales y configuraciones de IDE (`.vscode/`, `.idea/`).
- Configuraciones de asistentes de IA (`.claude/`, `CLAUDE.md`, `.mcp.json`, `.cursor/`).

## 3. Comprobaciones de seguridad

| Comprobación | Resultado |
|---|---|
| ¿Existe historial de Git con secretos? | **No.** No había repositorio (ni en el proyecto ni en carpetas superiores); se creó uno nuevo y vacío. |
| Contenido real de `secrets/biblioteca_aes.key`, `secrets/operador.hash` y `clave.key` dentro de archivos publicables | Ninguno. Se comparó byte a byte sin mostrar los valores. |
| Patrones de credenciales (tokens de Hugging Face y GitHub, llaves privadas PEM, hashes scrypt, llaves base64 de 32 bytes, tokens Fernet o `v2:`, asignaciones de contraseña) | Ninguno. |
| Datos personales | Ninguno real. Los únicos correos y teléfonos son ficticios en `tests/` (`ana.lopez@mail.com`, `5512345678`) y ejemplos de formato (`nombre@dominio.com`). Los CSV no contienen personas. |
| Rutas o nombres del equipo local | Ninguno. Se eliminaron de `ANALISIS_PROYECTO.md` y `PRUEBAS.md` las referencias al entorno de desarrollo. |
| Dependencia de Claude Code | Ninguna. No hay `.claude/` ni `CLAUDE.md` en el proyecto, ni importaciones o dependencias relacionadas. La única mención son las reglas de exclusión de `.gitignore`. |
| Modelos pesados | Ninguno. Los pesos se descargan aparte (sección 5). |
| `.env` excluido | Sí (`git check-ignore .env`). |

> **`clave.key`**: es la llave del proyecto original del que se partió. Queda fuera del repositorio. Si nunca se subió a ningún sitio no hay nada que hacer; si alguna vez se compartió, considérala comprometida, aunque hoy no protege ningún dato.

## 4. Configuración necesaria para cada colaborador

1. Python 3.10+ con Tkinter, Git y un servidor Redis 6+ (instalación local; Docker opcional).
2. `pip install torch` (CUDA o CPU) y `pip install -r requirements.txt`.
3. `cp .env.example .env` y ajustar la conexión a **su Redis local** (`REDIS_HOST`, `REDIS_PORT`, `REDIS_DB` vacía, `REDIS_USUARIO` y `REDIS_PASSWORD` si aplica).
4. Comprobar con `redis-cli ping` y `python verificar.py`. Docker Compose es una alternativa opcional.
5. Primer arranque: crear la contraseña de operador, aceptar la descarga del modelo y cargar los datos de ejemplo.

Cada instalación genera su propia llave AES, usa su propio Redis y su propia ChromaDB; **no se comparten secretos ni datos entre integrantes**.

## 5. Modelo y procedimiento de descarga

| Dato | Valor |
|---|---|
| Modelo | `Qwen/Qwen3-Embedding-0.6B` (Hugging Face Hub, público, sin restricción de acceso) |
| Revisión fijada | `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3` (la misma que se usó durante el desarrollo) |
| Licencia | Apache-2.0 |
| Tamaño | ~1.21 GB (`model.safetensors` 1.19 GB) |
| Dimensión | 1024; sin cambios respecto al proyecto |
| Ubicación | `BIBLIOTECA_DIR_MODELOS` o la caché de Hugging Face |

Procedimiento:

1. Al iniciar sesión, la aplicación comprueba si están completos los archivos de la revisión fijada.
2. Si faltan, muestra el tamaño, el destino y el espacio libre, y ofrece descargar.
3. La descarga muestra el progreso en bytes y la velocidad.
4. Al terminar se valida que el modelo cargue y produzca vectores de 1024 dimensiones.
5. Las ejecuciones siguientes reutilizan la descarga.

Alternativa por terminal: `python gestionar_modelos.py descargar`.

**Verificación real** (con `BIBLIOTECA_DIR_MODELOS` apuntando a una carpeta vacía, como en el equipo de un colaborador nuevo):

| Paso | Resultado |
|---|---|
| Estado inicial | `no descargado`. |
| Descarga | ✅ 1207.5 MB en 1010 s (1.2 MB/s con la conexión de prueba). Se bajaron solo 10 archivos: `model.safetensors`, `config.json`, `modules.json`, `config_sentence_transformers.json`, `1_Pooling/config.json`, `tokenizer.json`, `tokenizer_config.json`, `vocab.json`, `merges.txt` y `generation_config.json`. |
| Validación | ✅ «Modelo válido: 1024 dimensiones en cuda:0 · float16». |
| Segunda ejecución | ✅ «Ya está descargado… No se descarga de nuevo» (1 s). |
| Progreso | ✅ 52 actualizaciones a lo largo de los 11 s de descarga de un archivo de 11 MB: la barra avanza durante la descarga, no solo al final. |
| Errores | ✅ Sin conexión, espacio insuficiente, revisión incompleta y reanudación cubiertos en `tests/test_gestor_modelos.py`. |

La carpeta de prueba (1.2 GB) se eliminó después. La copia del modelo que ya existía en la caché de Hugging Face del equipo de desarrollo es exactamente la revisión fijada, así que se reutiliza sin descargar nada.

## 6. Dependencias

`requirements.txt`: chromadb, redis, sentence-transformers, transformers, torch, huggingface_hub, cryptography, python-dotenv, numpy, pytest y fakeredis. Se comprobó con un análisis de importaciones (`ast`) que todos los paquetes de terceros usados por el código están declarados. PyTorch se instala primero, según el hardware (README).

## 7. Verificaciones realizadas

| Verificación | Resultado |
|---|---|
| Pruebas automatizadas | ✅ 124/124, incluida la integración con Redis, ChromaDB y el modelo reales. La suite sin servicios externos pasó 3 corridas seguidas (ver limitaciones en PRUEBAS.md). |
| Dependencias completas | ✅ Análisis de importaciones frente a `requirements.txt`. |
| Redis desde Docker Compose | ✅ Arranque `healthy`; publicado solo en `127.0.0.1:<REDIS_PORT>`; contraseña exigida cuando se define y sin ella en la variante sin contraseña; datos conservados tras `restart` y tras `down` + `up`; `restart: unless-stopped`; `verificar.py` conecta con contraseña. Se usaron proyectos y puertos de prueba (6391 y 6392), eliminados después con sus volúmenes. |
| ChromaDB persistente | ✅ Un proceso distinto lee los documentos escritos (`tests/test_config.py`). |
| Descarga automática del modelo | ✅ Descarga real de 1.2 GB, validación y reutilización (sección 5). |
| Validación de configuración | ✅ Valores inválidos producen mensajes claros (`tests/test_config.py`). |
| `.env`, llaves y modelos excluidos | ✅ `git status --ignored` y comparación de contenido. |
| GitHub Actions (`.github/workflows/pruebas.yml`) | ⚠️ No ejecutado: solo correrá en GitHub después de publicar. |

## 8. Decisiones de publicación

| Tema | Decisión |
|---|---|
| Licencia | MIT, © 2026 Vessel-dot (`LICENSE`). Elegida por el titular del proyecto. |
| Autorización | El titular confirmó que tiene autorización para publicar el código derivado del proyecto académico original. |
| Atribuciones | El titular confirmó que el proyecto original no requiere créditos adicionales (sus archivos no declaraban autores). |
| Identidad de los commits | `Vessel-dot` con el correo *noreply* de GitHub de la cuenta `vesseldot`, configurado solo para este repositorio, para no exponer el correo personal. |
| Colaboradores | `miasmee` y `NoJumper1`, con permiso de escritura (*write/push*): pueden clonar, crear ramas, subir cambios y abrir Pull Requests, pero no administrar el repositorio. |
| Ramas | `main` (estable) y `develop` (integración), creadas a partir del commit inicial. |

Si alguna vez se sube un secreto por error: **cámbialo de inmediato** (genera una llave nueva o cambia la contraseña) y limpia el historial con `git filter-repo`. Esa operación es destructiva y requiere coordinar a todo el equipo.
