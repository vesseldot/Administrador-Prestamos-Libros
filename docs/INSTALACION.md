# Instalación y configuración en Windows

Guía paso a paso para dejar el proyecto funcionando en Windows 10 u 11 con PowerShell. En Linux y macOS los pasos son equivalentes; el [README](../README.md#instalación-rápida) muestra las diferencias de esos sistemas.

> **Nota.** Docker **no es obligatorio**. El proyecto funciona con cualquier servidor Redis 6 o superior: uno instalado en el equipo, en WSL, Memurai o uno en la red.

## 1. Requisitos

| Componente | Mínimo | Comprobación |
|---|---|---|
| Windows | 10 u 11, 64 bits | — |
| Python | 3.10 o superior, con Tcl/Tk (probado con 3.14.6) | `python --version` y `python -m tkinter` |
| Git | Cualquier versión reciente | `git --version` |
| Redis | 6.0 o superior | `redis-cli ping` → `PONG` |
| Disco | ~4 GB (dependencias + modelo de 1.2 GB) | — |
| GPU | Opcional (NVIDIA con CUDA); sin GPU funciona en CPU | `nvidia-smi` |

## 2. Python

1. Descarga el instalador desde <https://www.python.org/downloads/windows/>.
2. Marca **«Add python.exe to PATH»** y, en *Customize installation › Optional features*, **«tcl/tk and IDLE»**.
3. Comprueba la instalación:
   ```powershell
   python --version
   python -m tkinter        # abre una ventana pequeña de prueba
   ```

## 3. Git

1. Instala Git desde <https://git-scm.com/download/win>.
2. Configura tu identidad (una sola vez):
   ```powershell
   git config --global user.name "Tu Nombre"
   git config --global user.email "tu-correo@ejemplo.com"
   ```
   Para no exponer tu correo personal en un repositorio público, puedes usar la dirección *noreply* de GitHub (*Settings › Emails*).

## 4. Clonar el repositorio

```powershell
git clone https://github.com/vesseldot/Administrador-Prestamos-Libros.git
cd Administrador-Prestamos-Libros
git switch develop
```

## 5. Entorno virtual y dependencias

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

Si PowerShell bloquea la activación con un mensaje sobre *Execution Policy*, ejecuta una vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` y vuelve a activar el entorno.

Instala primero **PyTorch** según tu hardware (<https://pytorch.org/get-started/locally/>) y después el resto:

```powershell
# GPU NVIDIA (ajusta cu130 a tu versión de CUDA: cu126, cu128…)
pip install torch --index-url https://download.pytorch.org/whl/cu130
# Solo CPU
pip install torch --index-url https://download.pytorch.org/whl/cpu

pip install -r requirements.txt
```

`requirements.txt` incluye chromadb, redis, sentence-transformers, transformers, torch, huggingface_hub, cryptography, python-dotenv, numpy, pillow, pytest y fakeredis.

> **Nota.** Si `main.py` se ejecuta con un Python que no tiene las dependencias, por ejemplo desde la extensión Code Runner de VS Code, `main.asegurar_entorno()` lo relanza automáticamente con `.venv\Scripts\python.exe` o `..\.venv\Scripts\python.exe` si existen. En VS Code conviene seleccionar el intérprete del entorno: `Ctrl+Shift+P` › *Python: Select Interpreter*.

## 6. Archivo de configuración `.env`

```powershell
copy .env.example .env
notepad .env
```

Todas las variables están documentadas en [`.env.example`](../.env.example). Las más importantes:

| Variable | Por defecto | Para qué |
|---|---|---|
| `REDIS_HOST` / `REDIS_PORT` | `localhost` / `6379` | Dónde está Redis. |
| `REDIS_DB` | `2` | Base dedicada y **vacía**. |
| `REDIS_USUARIO` / `REDIS_PASSWORD` | vacías | Solo si tu Redis exige autenticación. |
| `REDIS_SSL` | `0` | `1` para TLS. |
| `REDIS_PREFIJO` | `bib:` | Prefijo de todas las llaves; debe terminar en `:`. |
| `BIBLIOTECA_CHROMA_PATH` | `chroma_db` | Carpeta de ChromaDB. |
| `BIBLIOTECA_MODELO` | `qwen3-embedding-0.6b` | Modelo activo por defecto. |
| `BIBLIOTECA_DIR_MODELOS` | caché de Hugging Face | Carpeta de modelos. |
| `BIBLIOTECA_PERMITIR_DESCARGA` | `1` | `0` impide descargar modelos. |
| `BIBLIOTECA_DISPOSITIVO` | `auto` | `auto`, `cuda` o `cpu`. |
| `BIBLIOTECA_DIR_SECRETOS` | `secrets` | Llave AES y hash de la contraseña. |
| `BIBLIOTECA_MINUTOS_BLOQUEO` | `15` | Bloqueo por inactividad. |
| `BIBLIOTECA_DIAS_PRESTAMO` | `14` | Plazo de préstamo. |
| `BIBLIOTECA_DIR_PORTADAS` | `portadas` | Carpeta de las portadas (excluida de Git). |
| `BIBLIOTECA_DESCARGAR_PORTADAS` | `1` | `0` impide buscar portadas en Open Library. |

Las variables de entorno del sistema tienen prioridad sobre `.env`. `config.validar()` revisa los valores al arrancar y muestra un mensaje claro si alguno es inválido.

## 7. Redis local

### 7.1 Opciones en Windows

| Opción | Instalación | Iniciar | Verificar |
|---|---|---|---|
| **Memurai** (compatible con Redis, servicio de Windows) | Instalador de <https://www.memurai.com/> | Se inicia como servicio (*services.msc*) | `memurai-cli ping` |
| **Redis en WSL** | `wsl --install` y, dentro de Ubuntu, `sudo apt install redis-server` | `sudo service redis-server start` (en WSL) | `redis-cli ping` (en WSL) |
| **Redis que ya tengas instalado** | — | Según tu instalación | `redis-cli ping` |
| **Docker (opcional)** | Docker Desktop | `docker compose up -d` (en la carpeta del proyecto) | `docker compose ps` → *healthy* |

Con WSL 2, Windows llega a Redis por `localhost` gracias al reenvío de puertos. Si no responde, revisa la configuración de red de WSL.

### 7.2 Elegir una base vacía y verificar

```powershell
redis-cli ping                 # → PONG
redis-cli -n 2 DBSIZE          # → 0  (si no, prueba otra base y cambia REDIS_DB en .env)
# Con contraseña:   redis-cli -a TU_CONTRASEÑA ping
# Con usuario ACL:  redis-cli --user USUARIO -a TU_CONTRASEÑA ping
```

La aplicación **se niega a arrancar** si la base elegida contiene llaves que no empiezan por `REDIS_PREFIJO`. Esto protege los datos de otros proyectos.

### 7.3 Docker Compose (opcional)

`docker-compose.yml` lee `REDIS_PORT`, `REDIS_PASSWORD` y `REDIS_BIND` del mismo `.env`. Publica Redis en `127.0.0.1`, con persistencia AOF en el volumen `redis_datos` y reinicio `unless-stopped`.

```powershell
docker compose up -d       # iniciar
docker compose ps          # estado (healthy)
docker compose stop        # detener sin borrar datos
docker compose logs -f redis   # ver el registro
docker compose down        # eliminar el contenedor (conserva el volumen)
docker compose down -v     # borrar contenedor y DATOS
```

Si `docker compose up` responde `port is already allocated`, otro programa usa ese puerto: cambia `REDIS_PORT` en `.env` (por ejemplo, a `6380`). Si cambias `REDIS_PASSWORD` después de crear el volumen, recrea el contenedor con `docker compose up -d --force-recreate`.

## 8. ChromaDB

No requiere instalación aparte: es una base embebida que se instala con `requirements.txt`. La carpeta `BIBLIOTECA_CHROMA_PATH` (por defecto `chroma_db\`) se crea en el primer arranque y está excluida de Git. Para empezar de cero, cierra la aplicación y borra esa carpeta; los datos de Redis se borran aparte.

## 9. Modelo semántico

```powershell
python gestionar_modelos.py estado        # qué modelos hay y dónde
python gestionar_modelos.py descargar     # descarga la revisión fijada (~1.2 GB) y la valida
python gestionar_modelos.py validar       # comprueba que produce vectores de 1024 dimensiones
```

También puedes descargarlo desde la propia aplicación: al iniciar sesión, si el modelo falta, aparece un diálogo de descarga con barra de progreso. Más detalles en [MODELO_SEMANTICO.md](MODELO_SEMANTICO.md).

## 10. Claves y contraseña

- La **llave AES-256** se genera sola en `secrets\biblioteca_aes.key` en el primer arranque. Para usar una variable de entorno, ejecuta `python gestionar_secretos.py nueva-llave` y copia el resultado en `BIBLIOTECA_AES_KEY`.
- La **contraseña de operador** se crea en la primera pantalla de la aplicación. También puedes crearla o cambiarla con `python gestionar_secretos.py contrasena`.
- `python gestionar_secretos.py estado` indica qué secretos existen, sin mostrarlos.
- **Respalda `secrets\`**: sin la llave, los datos personales no se pueden recuperar.

## 11. Verificación y ejecución

```powershell
python verificar.py      # dependencias, configuración, Redis, modelo y secretos
python main.py           # aplicación
```

`verificar.py` termina con «Todo listo, ejecuta: python main.py» si todo está en orden.

**Primer uso:**

1. Crea la contraseña del operador.
2. Acepta la descarga del modelo si te la ofrece.
3. Ve a **Configuración › Sistema › Cargar datos de ejemplo** para importar los 200 libros de `datos\`.
4. Opcional: en la misma pestaña, **Descargar portadas faltantes** busca las portadas en Open Library (unos 4 s por libro; puedes detenerla y continuar después).

## 12. Modo de demostración

```powershell
python demo_interfaz.py                  # datos de ejemplo en memoria, modelo simulado
python demo_interfaz.py --sin-datos      # bases vacías
python demo_interfaz.py --modelo-real    # usa el modelo descargado (si existe)
```

- No usa Redis real, ChromaDB real, `.env` ni `secrets\`; todo se pierde al cerrar.
- La contraseña es `demo1234`.
- Carga los 200 libros, 4 personas ficticias y varios préstamos, uno de ellos vencido.
- El modelo simulado no necesita GPU, pero su búsqueda solo compara palabras y no capta significado.

## 13. Pruebas

```powershell
python -m pytest tests                                          # sin servicios externos
$env:BIBLIOTECA_PRUEBAS_REALES="1"; python -m pytest tests      # + integración con Redis, Chroma y el modelo reales
```

La prueba de integración real usa la base `REDIS_DB` con el prefijo `prueba_integracion:` y, al terminar, borra solo esas llaves.

## 14. Solución de problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| `ModuleNotFoundError: No module named 'chromadb'` | Python sin dependencias: activa `.venv` o selecciona su intérprete en el IDE. |
| `No module named 'tkinter'` | Reinstala Python marcando «tcl/tk and IDLE». |
| «No se pudo conectar a Redis» | Inicia el servicio (sección 7) y revisa `REDIS_HOST` y `REDIS_PORT`. |
| «Redis rechazó la conexión» | `REDIS_USUARIO` o `REDIS_PASSWORD` incorrectos. |
| «Base de Redis ocupada» | La base tiene llaves de otro proyecto: elige otra `REDIS_DB` vacía. |
| «Configuración inválida» | Corrige los valores indicados en `.env` (ver `.env.example`). |
| «Modelo no disponible» | `python gestionar_modelos.py descargar` o acepta la descarga en la aplicación. |
| «No hay conexión con Hugging Face Hub» | Revisa la red y el proxy, y que `HF_HUB_OFFLINE` no esté definida. |
| «Espacio insuficiente» | Libera espacio o define `BIBLIOTECA_DIR_MODELOS` en otra unidad. |
| `CUDA out of memory` | `BIBLIOTECA_DISPOSITIVO=cpu`. |
| Activación de `.venv` bloqueada | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. |
| Texto borroso en pantallas al 125–150 % | Ejecuta siempre con `python main.py`, que activa el modo de alta densidad. |

Más diagnósticos en [MANTENIMIENTO.md](MANTENIMIENTO.md).
