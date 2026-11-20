"""Portadas de los libros: almacenamiento local y búsqueda en Open Library.

Las imágenes se guardan como archivos en `config.DIR_PORTADAS` (`{id}.jpg` y `{id}.json` con el
origen), fuera de Redis y de ChromaDB y excluidas de git: las portadas tienen derechos de sus
editoriales, así que cada instalación las obtiene por su cuenta. Toda imagen se valida y se
normaliza con Pillow a JPEG de 600×900 como máximo antes de guardarla.

Open Library (https://openlibrary.org/developers/api) es un catálogo abierto que no requiere
clave. Se consulta primero por ISBN, comprobando que el título de la edición coincida, y después
por título y autor. Entre peticiones se hace una pausa para respetar los límites del servicio.
"""
import io
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import config
from validaciones import RE_ID_LIBRO, normalizar_isbn, normalizar_texto

log = logging.getLogger("biblioteca")

FORMATOS_ACEPTADOS = {"JPEG", "PNG", "WEBP", "GIF", "BMP"}
EXTENSIONES_IMAGEN = ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.gif", "*.bmp")
TAMANO_MAXIMO_BYTES = 15 * 1024 * 1024
MAXIMO_PIXELES = 40_000_000
TAMANO_GUARDADO = (600, 900)
LADO_MINIMO = 40
CALIDAD_JPEG = 88
MAX_MINIATURAS_EN_CACHE = 64

ORIGEN_OPEN_LIBRARY = "Open Library"
ORIGEN_OPERADOR = "Imagen elegida por el operador"
URL_OPEN_LIBRARY = "https://openlibrary.org"
URL_PORTADA = "https://covers.openlibrary.org/b/id/{}-L.jpg?default=false"
AGENTE = "biblioteca-portadas/1.0 (proyecto academico)"
REINTENTOS = 1


class ErrorPortada(RuntimeError):
    """No se pudo consultar o descargar una portada (sin red o fallo del servicio externo)."""


def normalizar_imagen(datos: bytes) -> bytes:
    """Valida una imagen y la convierte a JPEG RGB de 600×900 como máximo. Lanza ValueError."""
    from PIL import Image, ImageOps, UnidentifiedImageError
    if len(datos) > TAMANO_MAXIMO_BYTES:
        raise ValueError("La imagen supera el tamaño máximo de 15 MB.")
    Image.MAX_IMAGE_PIXELS = MAXIMO_PIXELES
    try:
        with Image.open(io.BytesIO(datos)) as original:
            if original.format not in FORMATOS_ACEPTADOS:
                raise ValueError("Formato de imagen no admitido. Usa JPG, PNG, WEBP, GIF o BMP.")
            original.load()
            imagen = ImageOps.exif_transpose(original)
            if min(imagen.size) < LADO_MINIMO:
                raise ValueError(f"La imagen es demasiado pequeña (mínimo {LADO_MINIMO} píxeles por lado).")
            if imagen.mode in ("RGBA", "LA", "P"):
                imagen = imagen.convert("RGBA")
                fondo = Image.new("RGB", imagen.size, (255, 255, 255))
                fondo.paste(imagen, mask=imagen.getchannel("A"))
                imagen = fondo
            elif imagen.mode != "RGB":
                imagen = imagen.convert("RGB")
            imagen.thumbnail(TAMANO_GUARDADO, Image.Resampling.LANCZOS)
            salida = io.BytesIO()
            imagen.save(salida, "JPEG", quality=CALIDAD_JPEG, optimize=True)
            return salida.getvalue()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as error:
        raise ValueError("El archivo no es una imagen válida o está dañado.") from error


class AlmacenPortadas:
    """Carpeta de portadas: `{id}.jpg` (imagen normalizada) y `{id}.json` (origen y fecha)."""

    def __init__(self, directorio: str | Path | None = None):
        self.directorio = Path(directorio or config.DIR_PORTADAS)
        self._cache: dict[tuple, bytes] = {}
        self._candado = threading.Lock()

    def _rutas(self, libro_id: str) -> tuple[Path, Path]:
        if not RE_ID_LIBRO.match(str(libro_id)):
            raise ValueError(f"Identificador de libro no válido: {libro_id!r}")
        return self.directorio / f"{libro_id}.jpg", self.directorio / f"{libro_id}.json"

    def existe(self, libro_id: str) -> bool:
        return self._rutas(libro_id)[0].exists()

    def ids(self) -> set[str]:
        if not self.directorio.exists():
            return set()
        return {ruta.stem for ruta in self.directorio.glob("*.jpg") if RE_ID_LIBRO.match(ruta.stem)}

    def info(self, libro_id: str) -> dict | None:
        imagen, metadatos = self._rutas(libro_id)
        if not imagen.exists():
            return None
        try:
            datos = json.loads(metadatos.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            datos = {}
        return {"origen": datos.get("origen", "desconocido"), "fuente": datos.get("fuente", ""),
                "fecha": datos.get("fecha", "")}

    def guardar(self, libro_id: str, datos: bytes, origen: str, fuente: str = "") -> dict:
        imagen, metadatos = self._rutas(libro_id)
        normalizada = normalizar_imagen(datos)
        self.directorio.mkdir(parents=True, exist_ok=True)
        info = {"origen": origen, "fuente": fuente, "fecha": datetime.now().isoformat(timespec="seconds")}
        for ruta, contenido in ((imagen, normalizada),
                                (metadatos, json.dumps(info, ensure_ascii=False).encode("utf-8"))):
            temporal = ruta.with_name(ruta.name + ".tmp")
            temporal.write_bytes(contenido)
            os.replace(temporal, ruta)
        self._olvidar(libro_id)
        return info

    def quitar(self, libro_id: str) -> bool:
        imagen, metadatos = self._rutas(libro_id)
        existia = imagen.exists()
        imagen.unlink(missing_ok=True)
        metadatos.unlink(missing_ok=True)
        self._olvidar(libro_id)
        return existia

    def miniatura_png(self, libro_id: str, ancho: int, alto: int) -> bytes | None:
        """PNG ajustado a ancho×alto (sin deformar), listo para tk.PhotoImage. None si no hay portada."""
        from PIL import Image
        imagen = self._rutas(libro_id)[0]
        try:
            marca = imagen.stat().st_mtime_ns
        except FileNotFoundError:
            return None
        clave = (libro_id, int(ancho), int(alto), marca)
        with self._candado:
            if clave in self._cache:
                return self._cache[clave]
        with Image.open(imagen) as original:
            original.thumbnail((max(int(ancho), 1), max(int(alto), 1)), Image.Resampling.LANCZOS)
            salida = io.BytesIO()
            original.save(salida, "PNG")
        png = salida.getvalue()
        with self._candado:
            if len(self._cache) >= MAX_MINIATURAS_EN_CACHE:
                self._cache.pop(next(iter(self._cache)))
            self._cache[clave] = png
        return png

    def _olvidar(self, libro_id: str):
        with self._candado:
            for clave in [c for c in self._cache if c[0] == libro_id]:
                del self._cache[clave]


def _palabras(texto: str) -> set[str]:
    limpio = "".join(c if c.isalnum() else " " for c in normalizar_texto(texto))
    return {palabra for palabra in limpio.split() if len(palabra) >= 4}


def titulos_compatibles(encontrado: str, esperado: str) -> bool:
    """Evita aceptar la portada de otro libro: los títulos deben compartir una palabra significativa."""
    a, b = normalizar_texto(encontrado), normalizar_texto(esperado)
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    return bool(_palabras(a) & _palabras(b))


class ClienteOpenLibrary:
    """Busca portadas en Open Library. `abrir(url) -> bytes | None` se puede sustituir en pruebas."""

    def __init__(self, pausa: float = 1.0, tiempo_espera: float = 20, abrir=None):
        self.pausa = pausa
        self.tiempo_espera = tiempo_espera
        self._abrir = abrir or self._abrir_url
        self._ultima = 0.0
        self._candado = threading.Lock()

    def _abrir_url(self, url: str) -> bytes | None:
        peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE})
        try:
            with urllib.request.urlopen(peticion, timeout=self.tiempo_espera) as respuesta:
                return respuesta.read(TAMANO_MAXIMO_BYTES + 1)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            raise ErrorPortada(f"Open Library respondió con el código {error.code}.") from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise ErrorPortada("No hay conexión con Open Library. Revisa la red o el proxy.") from error

    def _pedir(self, url: str) -> bytes | None:
        """Una petición respetando la pausa; ante un fallo de red se reintenta una vez."""
        with self._candado:
            for intento in range(1 + REINTENTOS):
                espera = self._ultima + self.pausa * (1 + 2 * intento) - time.monotonic()
                if espera > 0:
                    time.sleep(espera)
                try:
                    return self._abrir(url)
                except ErrorPortada:
                    if intento == REINTENTOS:
                        raise
                    log.info("Reintentando una petición a Open Library")
                finally:
                    self._ultima = time.monotonic()
        return None

    def _json(self, url: str) -> dict | None:
        datos = self._pedir(url)
        if not datos:
            return None
        try:
            return json.loads(datos)
        except ValueError:
            return None

    def _portada_por_isbn(self, isbn: str, titulo: str) -> int | None:
        digitos = normalizar_isbn(isbn)
        if not digitos:
            return None
        edicion = self._json(f"{URL_OPEN_LIBRARY}/isbn/{urllib.parse.quote(digitos)}.json")
        if not edicion or not titulos_compatibles(edicion.get("title", ""), titulo):
            return None
        return next((c for c in edicion.get("covers", []) if isinstance(c, int) and c > 0), None)

    def _portada_por_titulo(self, titulo: str, autor: str) -> int | None:
        consulta = urllib.parse.urlencode({"title": titulo, "author": autor, "limit": 5,
                                           "fields": "title,cover_i"})
        resultado = self._json(f"{URL_OPEN_LIBRARY}/search.json?{consulta}") or {}
        for documento in resultado.get("docs", []):
            portada = documento.get("cover_i")
            if isinstance(portada, int) and portada > 0 and titulos_compatibles(documento.get("title", ""),
                                                                                  titulo):
                return portada
        return None

    def buscar(self, isbn: str, titulo: str, autor: str) -> tuple[bytes, str] | None:
        """Regresa (imagen, url de origen) o None si Open Library no tiene portada. Lanza ErrorPortada."""
        portada = self._portada_por_isbn(isbn, titulo) or self._portada_por_titulo(titulo, autor)
        if portada is None:
            return None
        url = URL_PORTADA.format(portada)
        imagen = self._pedir(url)
        if not imagen:
            return None
        return imagen, url.split("?")[0]
