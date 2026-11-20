"""Portadas: validación de imágenes, almacenamiento, búsqueda en Open Library (simulada) y API."""
import io
import json

import pytest
from PIL import Image

import config
from conftest import libro_ejemplo
from portadas import (ORIGEN_OPEN_LIBRARY, ORIGEN_OPERADOR, AlmacenPortadas, ClienteOpenLibrary, ErrorPortada,
                      normalizar_imagen, titulos_compatibles)
from servicios import describir_error


def imagen(ancho=300, alto=450, formato="PNG", modo="RGB", color=(200, 30, 30)) -> bytes:
    salida = io.BytesIO()
    Image.new(modo, (ancho, alto), color if modo == "RGB" else (200, 30, 30, 128)).save(salida, formato)
    return salida.getvalue()


def dimensiones(datos: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(datos)) as abierta:
        return abierta.size


class OpenLibraryFalso:
    """Simula las respuestas de Open Library a partir de un diccionario url → bytes | None | Exception."""

    def __init__(self, respuestas: dict):
        self.respuestas = respuestas
        self.urls: list[str] = []

    def __call__(self, url):
        self.urls.append(url)
        for prefijo, respuesta in self.respuestas.items():
            if url.startswith(prefijo):
                if isinstance(respuesta, Exception):
                    raise respuesta
                return respuesta
        return None


def cliente(respuestas: dict) -> tuple[ClienteOpenLibrary, OpenLibraryFalso]:
    falso = OpenLibraryFalso(respuestas)
    return ClienteOpenLibrary(pausa=0, abrir=falso), falso


def edicion(titulo: str, portadas: list[int]) -> bytes:
    return json.dumps({"title": titulo, "covers": portadas}).encode()


# --- Imágenes -------------------------------------------------------------------------------------------

def test_normaliza_a_jpeg_dentro_del_tamano_maximo():
    resultado = normalizar_imagen(imagen(1200, 1800))
    with Image.open(io.BytesIO(resultado)) as abierta:
        assert abierta.format == "JPEG" and abierta.mode == "RGB"
        assert abierta.size[0] <= 600 and abierta.size[1] <= 900


def test_convierte_transparencia_sobre_fondo_blanco():
    with Image.open(io.BytesIO(normalizar_imagen(imagen(modo="RGBA")))) as abierta:
        assert abierta.mode == "RGB"


@pytest.mark.parametrize("datos", [b"no es una imagen", b"", imagen(20, 20)])
def test_rechaza_archivos_no_validos_o_diminutos(datos):
    with pytest.raises(ValueError):
        normalizar_imagen(datos)


def test_rechaza_imagenes_demasiado_grandes(monkeypatch):
    import portadas
    monkeypatch.setattr(portadas, "TAMANO_MAXIMO_BYTES", 100)
    with pytest.raises(ValueError, match="15 MB"):
        normalizar_imagen(imagen())


# --- Almacén --------------------------------------------------------------------------------------------

def test_guarda_informa_y_quita(tmp_path):
    almacen = AlmacenPortadas(tmp_path)
    assert almacen.info("libro01") is None and almacen.miniatura_png("libro01", 100, 150) is None
    almacen.guardar("libro01", imagen(), ORIGEN_OPERADOR)
    assert almacen.existe("libro01") and almacen.ids() == {"libro01"}
    assert almacen.info("libro01")["origen"] == ORIGEN_OPERADOR
    ancho, alto = dimensiones(almacen.miniatura_png("libro01", 100, 120))
    assert ancho <= 100 and alto <= 120
    assert almacen.quitar("libro01") is True
    assert not almacen.existe("libro01") and almacen.quitar("libro01") is False


def test_la_miniatura_cambia_al_reemplazar_la_imagen(tmp_path):
    almacen = AlmacenPortadas(tmp_path)
    almacen.guardar("libro01", imagen(color=(255, 0, 0)), ORIGEN_OPERADOR)
    primera = almacen.miniatura_png("libro01", 60, 90)
    almacen.guardar("libro01", imagen(color=(0, 0, 255)), ORIGEN_OPERADOR)
    assert almacen.miniatura_png("libro01", 60, 90) != primera


@pytest.mark.parametrize("identificador", ["../fuera", "libro 1", "a/b", ""])
def test_rechaza_identificadores_que_no_son_de_libro(tmp_path, identificador):
    with pytest.raises(ValueError):
        AlmacenPortadas(tmp_path).guardar(identificador, imagen(), ORIGEN_OPERADOR)


# --- Open Library ---------------------------------------------------------------------------------------

def test_titulos_compatibles():
    assert titulos_compatibles("El marciano", "El Marciano")
    assert titulos_compatibles("Cien años de soledad (edición conmemorativa)", "Cien años de soledad")
    assert not titulos_compatibles("Manual de jardinería", "Cien años de soledad")


def test_busca_por_isbn_si_el_titulo_coincide():
    cli, falso = cliente({"https://openlibrary.org/isbn/9788466655132": edicion("El marciano", [123]),
                          "https://covers.openlibrary.org/b/id/123-L.jpg": imagen()})
    datos, url = cli.buscar("978-84-666-5513-2", "El marciano", "Andy Weir")
    assert url == "https://covers.openlibrary.org/b/id/123-L.jpg" and datos
    assert not any("search.json" in u for u in falso.urls)


def test_descarta_la_edicion_de_otro_libro_y_busca_por_titulo():
    cli, falso = cliente({"https://openlibrary.org/isbn/": edicion("Manual de jardinería", [1]),
                          "https://openlibrary.org/search.json": json.dumps(
                              {"docs": [{"title": "Otro libro", "cover_i": 2},
                                        {"title": "El marciano", "cover_i": 3}]}).encode(),
                          "https://covers.openlibrary.org/b/id/3-L.jpg": imagen()})
    assert cli.buscar("9780000000001", "El marciano", "Andy Weir")[1].endswith("/3-L.jpg")
    assert not any("/b/id/1-" in u for u in falso.urls)


def test_sin_portada_en_open_library():
    cli, _ = cliente({"https://openlibrary.org/search.json": b'{"docs": []}'})
    assert cli.buscar("9780000000001", "Título inexistente", "Nadie") is None


def test_error_de_red():
    cli, _ = cliente({"https://openlibrary.org/": ErrorPortada("sin red")})
    with pytest.raises(ErrorPortada):
        cli.buscar("9780000000001", "El marciano", "Andy Weir")


# --- Servicio -------------------------------------------------------------------------------------------

@pytest.fixture
def con_portadas(servicio, tmp_path):
    servicio.portadas = AlmacenPortadas(tmp_path / "portadas_servicio")
    return servicio


def test_asignar_portada_desde_un_archivo(con_portadas, tmp_path):
    libro_id = con_portadas.alta_libro(libro_ejemplo(1))
    archivo = tmp_path / "portada.png"
    archivo.write_bytes(imagen())
    con_portadas.asignar_portada(libro_id, archivo)
    assert con_portadas.obtener_libro(libro_id)["portada"]["origen"] == ORIGEN_OPERADOR
    assert con_portadas.portada_libro(libro_id, 90, 135)
    assert con_portadas.estado_portadas()["con_portada"] == 1
    assert con_portadas.quitar_portada(libro_id) is True
    assert con_portadas.obtener_libro(libro_id)["portada"] is None


def test_asignar_portada_valida_libro_y_archivo(con_portadas, tmp_path):
    archivo = tmp_path / "texto.png"
    archivo.write_bytes(b"no es imagen")
    with pytest.raises(ValueError, match="No existe el libro"):
        con_portadas.asignar_portada("libro99", archivo)
    libro_id = con_portadas.alta_libro(libro_ejemplo(1))
    with pytest.raises(ValueError, match="imagen válida"):
        con_portadas.asignar_portada(libro_id, archivo)
    with pytest.raises(ValueError, match="No se pudo leer"):
        con_portadas.asignar_portada(libro_id, tmp_path / "no_existe.png")


def test_eliminar_libro_borra_su_portada(con_portadas, tmp_path):
    libro_id = con_portadas.alta_libro(libro_ejemplo(1))
    con_portadas.portadas.guardar(libro_id, imagen(), ORIGEN_OPERADOR)
    con_portadas.eliminar_libro(libro_id)
    assert not con_portadas.portadas.existe(libro_id)


def test_buscar_portada_de_un_libro(con_portadas):
    con_portadas.cliente_portadas, _ = cliente({"https://openlibrary.org/search.json": json.dumps(
        {"docs": [{"title": "Libro 1", "cover_i": 7}]}).encode(),
        "https://covers.openlibrary.org/b/id/7-L.jpg": imagen()})
    libro_id = con_portadas.alta_libro(libro_ejemplo(1))
    resultado = con_portadas.buscar_portada(libro_id)
    assert resultado["encontrada"] and resultado["nueva"]
    assert resultado["portada"]["origen"] == ORIGEN_OPEN_LIBRARY
    assert con_portadas.buscar_portada(libro_id)["nueva"] is False


def test_buscar_portada_desactivada(con_portadas, monkeypatch):
    monkeypatch.setattr(config, "DESCARGAR_PORTADAS", False)
    libro_id = con_portadas.alta_libro(libro_ejemplo(1))
    with pytest.raises(ValueError, match="desactivada"):
        con_portadas.buscar_portada(libro_id)
    with pytest.raises(ValueError, match="desactivada"):
        con_portadas.descargar_portadas()


def test_descargar_solo_las_que_faltan(con_portadas):
    for numero in (1, 2, 3):
        con_portadas.alta_libro(libro_ejemplo(numero))
    con_portadas.portadas.guardar("libro01", imagen(), ORIGEN_OPERADOR)
    con_portadas.cliente_portadas, falso = cliente({
        "https://openlibrary.org/search.json?title=Libro+2": json.dumps(
            {"docs": [{"title": "Libro 2", "cover_i": 8}]}).encode(),
        "https://covers.openlibrary.org/b/id/8-L.jpg": imagen()})
    avances = []
    resultado = con_portadas.descargar_portadas(lambda hechos, total, titulo: avances.append((hechos, total)))
    assert resultado.total == 2 and avances == [(1, 2), (2, 2)]
    assert [l["id"] for l in resultado.descargadas] == ["libro02"]
    assert [l["id"] for l in resultado.sin_portada] == ["libro03"]
    assert not any("Libro+1" in u for u in falso.urls)
    assert con_portadas.estado_portadas() == {**con_portadas.estado_portadas(), "total": 3, "con_portada": 2}


def test_descarga_se_detiene_a_peticion(con_portadas):
    for numero in (1, 2, 3):
        con_portadas.alta_libro(libro_ejemplo(numero))
    con_portadas.cliente_portadas, _ = cliente({})
    resultado = con_portadas.descargar_portadas(lambda *a: con_portadas.detener_descarga_portadas())
    assert resultado.cancelado and len(resultado.sin_portada) == 1


def test_descarga_sin_red_se_interrumpe_con_un_error_claro(con_portadas):
    for numero in range(1, 6):
        con_portadas.alta_libro(libro_ejemplo(numero))
    con_portadas.cliente_portadas, falso = cliente({"https://openlibrary.org/": ErrorPortada("Sin conexión")})
    with pytest.raises(ErrorPortada):
        con_portadas.descargar_portadas()
    assert len(falso.urls) == 6  # 3 libros, cada petición se reintenta una vez
    assert describir_error(ErrorPortada("Sin conexión"))["categoria"] == "red"


def test_un_fallo_de_red_puntual_se_reintenta():
    respuestas = iter([ErrorPortada("corte"), edicion("El marciano", [5]), imagen()])

    def abrir(url):
        respuesta = next(respuestas)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    assert ClienteOpenLibrary(pausa=0, abrir=abrir).buscar("9788466655132", "El marciano", "Andy Weir")
