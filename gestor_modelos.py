"""Administrador de modelos de embeddings: disponibilidad local, descarga y validación.

Los pesos no forman parte del repositorio. Se descargan de Hugging Face Hub en una
revisión fija (commit) para que todos los integrantes usen exactamente los mismos
archivos, y se guardan en BIBLIOTECA_DIR_MODELOS o, si no se define, en la caché
estándar de Hugging Face (~/.cache/huggingface/hub), donde se reutilizan.
"""
import fnmatch
import shutil
import socket
from pathlib import Path

import config
from modelos import MODELOS

PATRONES_INCLUIDOS = ["*.json", "*.txt", "*.model", "model.safetensors"]
PATRONES_EXCLUIDOS = ["onnx/*", "openvino/*", "*.onnx", "*.h5", "*.msgpack", "*.bin", "*.csv", ".gitattributes"]
MARGEN_ESPACIO_BYTES = 300 * 1024 * 1024


class ErrorDescarga(RuntimeError):
    """La descarga del modelo no se completó."""


class SinConexion(ErrorDescarga):
    """No hay acceso a Hugging Face Hub."""


class EspacioInsuficiente(ErrorDescarga):
    """No hay espacio en disco para el modelo."""


def directorio_modelos() -> Path:
    if config.DIR_MODELOS is not None:
        return config.DIR_MODELOS
    from huggingface_hub import constants
    return Path(constants.HF_HUB_CACHE)


def _cache_dir() -> str | None:
    return str(config.DIR_MODELOS) if config.DIR_MODELOS is not None else None


def _ruta_en_cache(clave: str, archivo: str) -> str | None:
    from huggingface_hub import try_to_load_from_cache
    info = MODELOS[clave]
    ruta = try_to_load_from_cache(info["nombre_completo"], archivo, cache_dir=_cache_dir(),
                                  revision=info["revision"])
    return ruta if isinstance(ruta, str) and Path(ruta).exists() else None


def archivos_faltantes(clave: str) -> list[str]:
    return [archivo for archivo in MODELOS[clave]["archivos"] if _ruta_en_cache(clave, archivo) is None]


def ruta_local(clave: str) -> Path | None:
    """Carpeta local de la revisión fijada, solo si contiene todos los archivos necesarios."""
    if archivos_faltantes(clave):
        return None
    return Path(_ruta_en_cache(clave, "config.json")).parent


def esta_descargado(clave: str) -> bool:
    return ruta_local(clave) is not None


def espacio_libre(ruta: Path) -> int:
    existente = ruta
    while not existente.exists() and existente.parent != existente:
        existente = existente.parent
    return shutil.disk_usage(existente).free


def estado(clave: str) -> dict:
    info = MODELOS[clave]
    faltantes = archivos_faltantes(clave)
    return {"clave": clave, "repositorio": info["nombre_completo"], "revision": info["revision"],
            "licencia": info["licencia"], "tamano": info["tamano"], "tamano_mb": info["tamano_mb"],
            "disponible": not faltantes, "faltantes": faltantes, "directorio": directorio_modelos(),
            "ruta": ruta_local(clave), "espacio_libre": espacio_libre(directorio_modelos())}


def _incluido(archivo: str) -> bool:
    if any(fnmatch.fnmatch(archivo, patron) for patron in PATRONES_EXCLUIDOS):
        return False
    return any(fnmatch.fnmatch(archivo, patron) for patron in PATRONES_INCLUIDOS)


def _clasificar(error: Exception) -> ErrorDescarga:
    if isinstance(error, ErrorDescarga):
        return error
    nombre = type(error).__name__
    texto = str(error)
    sin_red = (isinstance(error, (ConnectionError, socket.gaierror, TimeoutError))
               or any(p in nombre for p in ("Connect", "Timeout", "Offline", "NetworkError"))
               or "offline" in texto.lower())
    if sin_red:
        return SinConexion("No hay conexión con Hugging Face Hub (huggingface.co). Revisa tu conexión a "
                           "Internet, el proxy o que HF_HUB_OFFLINE no esté activado, y vuelve a intentarlo.")
    return ErrorDescarga(f"La descarga falló ({nombre}): {texto[:300]}")


def plan_descarga(clave: str) -> list[tuple[str, int]]:
    """Archivos de la revisión fijada que se descargarán, con su tamaño en bytes."""
    from huggingface_hub import HfApi
    info = MODELOS[clave]
    try:
        datos = HfApi().model_info(info["nombre_completo"], revision=info["revision"], files_metadata=True)
    except Exception as error:  # noqa: BLE001
        raise _clasificar(error) from error
    plan = [(s.rfilename, int(s.size or 0)) for s in datos.siblings if _incluido(s.rfilename)]
    ausentes = [a for a in info["archivos"] if a not in {archivo for archivo, _ in plan}]
    if ausentes:
        raise ErrorDescarga(f"La revisión fijada no contiene: {', '.join(ausentes)}.")
    return sorted(plan, key=lambda p: p[1])


def _clase_progreso(al_avanzar):
    from huggingface_hub.utils import tqdm as BarraHF

    class Barra(BarraHF):
        def __init__(self, *argumentos, **opciones):
            opciones["disable"] = True
            super().__init__(*argumentos, **opciones)

        def update(self, n=1):
            if n:
                al_avanzar(n)
            return super().update(n)

    return Barra


def descargar(clave: str, progreso=None) -> Path:
    """Descarga la revisión fijada del modelo y verifica que quede completa.

    `progreso(bytes_hechos, bytes_totales, archivo)` se llama durante la descarga.
    """
    from huggingface_hub import hf_hub_download
    info = MODELOS[clave]
    plan = plan_descarga(clave)
    total = sum(tamano for _, tamano in plan)
    pendientes = [(archivo, tamano) for archivo, tamano in plan if _ruta_en_cache(clave, archivo) is None]
    por_bajar = sum(tamano for _, tamano in pendientes)
    destino = directorio_modelos()
    libre = espacio_libre(destino)
    if libre < por_bajar + MARGEN_ESPACIO_BYTES:
        raise EspacioInsuficiente(
            f"Se necesitan {(por_bajar + MARGEN_ESPACIO_BYTES) / 1e9:.2f} GB libres en {destino} y hay "
            f"{libre / 1e9:.2f} GB. Libera espacio o define BIBLIOTECA_DIR_MODELOS en otra unidad.")
    hechos = [total - por_bajar]
    if progreso:
        progreso(hechos[0], total, "")
    for archivo, tamano in pendientes:
        inicio = hechos[0]

        def avanzar(n, archivo=archivo):
            hechos[0] = min(hechos[0] + n, inicio + tamano)
            if progreso:
                progreso(hechos[0], total, archivo)
        try:
            hf_hub_download(info["nombre_completo"], archivo, revision=info["revision"], cache_dir=_cache_dir(),
                            tqdm_class=_clase_progreso(avanzar))
        except Exception as error:  # noqa: BLE001
            raise _clasificar(error) from error
        hechos[0] = inicio + tamano
        if progreso:
            progreso(hechos[0], total, archivo)
    faltantes = archivos_faltantes(clave)
    if faltantes:
        raise ErrorDescarga(f"La descarga terminó incompleta; faltan: {', '.join(faltantes)}.")
    return ruta_local(clave)


def validar(clave: str) -> dict:
    """Carga el modelo y genera un embedding de prueba para confirmar que los archivos sirven."""
    from modelos import ModeloEmbeddings
    if not esta_descargado(clave):
        raise ErrorDescarga(f"Faltan archivos: {', '.join(archivos_faltantes(clave))}.")
    modelo = ModeloEmbeddings(clave)
    try:
        vector = modelo.embeber_consulta("prueba de validación del modelo")
        dispositivo = modelo.descripcion_dispositivo()
    except Exception as error:  # noqa: BLE001
        raise ErrorDescarga(f"Los archivos están presentes pero el modelo no carga ({type(error).__name__}: "
                            f"{str(error)[:200]}). Bórralos y descárgalos de nuevo.") from error
    finally:
        modelo.liberar()
    esperado = MODELOS[clave]["dim"]
    if len(vector) != esperado:
        raise ErrorDescarga(f"El modelo produjo vectores de {len(vector)} dimensiones; se esperaban {esperado}.")
    return {"dimensiones": len(vector), "dispositivo": dispositivo}
