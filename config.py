"""Configuración centralizada del Administrador de Préstamos de Libros.

Los valores se leen de variables de entorno o del archivo `.env` (ver `.env.example`).
Ningún secreto se define en este archivo. `validar()` revisa los valores y regresa
mensajes claros para el usuario.
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parent
ARCHIVO_ENV = BASE_DIR / ".env"
ENV_PRESENTE = ARCHIVO_ENV.exists()

if load_dotenv and ENV_PRESENTE:
    load_dotenv(ARCHIVO_ENV)

_ERRORES: list[str] = []


def _texto(nombre: str, defecto: str) -> str:
    valor = os.environ.get(nombre)
    return defecto if valor is None or valor.strip() == "" else valor.strip()


def _entero(nombre: str, defecto: int, minimo: int | None = None, maximo: int | None = None) -> int:
    valor = os.environ.get(nombre)
    if valor is None or valor.strip() == "":
        return defecto
    try:
        numero = int(valor)
    except ValueError:
        _ERRORES.append(f"{nombre}='{valor}' no es un número entero.")
        return defecto
    if (minimo is not None and numero < minimo) or (maximo is not None and numero > maximo):
        _ERRORES.append(f"{nombre}={numero} está fuera del rango permitido ({minimo}–{maximo}).")
    return numero


def _booleano(nombre: str, defecto: bool) -> bool:
    valor = os.environ.get(nombre)
    if valor is None or valor.strip() == "":
        return defecto
    normalizado = valor.strip().lower()
    if normalizado in ("1", "true", "si", "sí", "yes"):
        return True
    if normalizado in ("0", "false", "no"):
        return False
    _ERRORES.append(f"{nombre}='{valor}' debe ser 1 o 0.")
    return defecto


def _ruta(nombre: str, defecto: Path | None) -> Path | None:
    valor = os.environ.get(nombre)
    if valor is None or valor.strip() == "":
        return defecto
    ruta = Path(os.path.expandvars(os.path.expanduser(valor.strip())))
    return ruta if ruta.is_absolute() else (BASE_DIR / ruta).resolve()


REDIS_HOST = _texto("REDIS_HOST", "localhost")
REDIS_PORT = _entero("REDIS_PORT", 6379, 1, 65535)
REDIS_DB = _entero("REDIS_DB", 2, 0, 15)
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD") or None
REDIS_USUARIO = os.environ.get("REDIS_USUARIO") or None
REDIS_SSL = _booleano("REDIS_SSL", False)
REDIS_PREFIJO = _texto("REDIS_PREFIJO", "bib:")
REDIS_TIMEOUT_SEGUNDOS = _entero("REDIS_TIMEOUT", 3, 1, 60)

CHROMA_PATH = str(_ruta("BIBLIOTECA_CHROMA_PATH", BASE_DIR / "chroma_db"))
ARCHIVO_MODELO_ACTIVO = Path(CHROMA_PATH).parent / "modelo_activo.txt"

DIR_SECRETOS = _ruta("BIBLIOTECA_DIR_SECRETOS", BASE_DIR / "secrets")
ARCHIVO_LLAVE_AES = DIR_SECRETOS / "biblioteca_aes.key"
ARCHIVO_HASH_OPERADOR = DIR_SECRETOS / "operador.hash"
ARCHIVO_LLAVE_LEGADA = BASE_DIR / "clave.key"

MODELO_POR_DEFECTO = _texto("BIBLIOTECA_MODELO", "qwen3-embedding-0.6b")
DIR_MODELOS = _ruta("BIBLIOTECA_DIR_MODELOS", None)
PERMITIR_DESCARGA_MODELOS = _booleano("BIBLIOTECA_PERMITIR_DESCARGA", True)
DISPOSITIVO = _texto("BIBLIOTECA_DISPOSITIVO", "auto").lower()
TAMANO_LOTE_EMBEDDINGS = _entero("BIBLIOTECA_LOTE_EMBEDDINGS", 32, 1, 512)

MAX_LIBROS_POR_PERSONA = 3
DIAS_PRESTAMO = _entero("BIBLIOTECA_DIAS_PRESTAMO", 14, 1, 365)
RESULTADOS_BUSQUEDA = 10
MAX_RESULTADOS_BUSQUEDA = 50
MAX_EVENTOS_ACTIVIDAD = 100

MINUTOS_BLOQUEO_INACTIVIDAD = _entero("BIBLIOTECA_MINUTOS_BLOQUEO", 15, 1, 480)
MAX_INTENTOS_ACCESO = 5
SEGUNDOS_ESPERA_TRAS_FALLOS = 30

DIR_DATOS = BASE_DIR / "datos"

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def _escribible(ruta: Path) -> bool:
    existente = ruta
    while not existente.exists() and existente.parent != existente:
        existente = existente.parent
    return os.access(existente, os.W_OK)


def validar() -> list[str]:
    """Regresa la lista de problemas de configuración (vacía si todo está bien)."""
    errores = list(_ERRORES)
    if not REDIS_PREFIJO.endswith(":") or len(REDIS_PREFIJO) < 2:
        errores.append(f"REDIS_PREFIJO='{REDIS_PREFIJO}' debe terminar en ':' (ej. bib:).")
    if DISPOSITIVO not in ("auto", "cuda", "cpu"):
        errores.append(f"BIBLIOTECA_DISPOSITIVO='{DISPOSITIVO}' debe ser auto, cuda o cpu.")
    from modelos import MODELOS
    if MODELO_POR_DEFECTO not in MODELOS:
        errores.append(f"BIBLIOTECA_MODELO='{MODELO_POR_DEFECTO}' no existe. Opciones: {', '.join(MODELOS)}.")
    for nombre, ruta in (("BIBLIOTECA_CHROMA_PATH", Path(CHROMA_PATH)), ("BIBLIOTECA_DIR_SECRETOS", DIR_SECRETOS),
                         ("BIBLIOTECA_DIR_MODELOS", DIR_MODELOS)):
        if ruta is not None and not _escribible(ruta):
            errores.append(f"{nombre}: no hay permiso de escritura en {ruta}.")
    clave = os.environ.get("BIBLIOTECA_AES_KEY")
    if clave:
        from seguridad import ErrorLlave, _decodificar_llave
        try:
            _decodificar_llave(clave, "BIBLIOTECA_AES_KEY")
        except ErrorLlave as error:
            errores.append(str(error))
    return errores


def advertencias() -> list[str]:
    avisos = []
    if not ENV_PRESENTE:
        avisos.append("No existe el archivo .env: se usan los valores por defecto. Cópialo desde .env.example.")
    return avisos
