import json

import pytest

from conftest import isbn_valido, libro_ejemplo
from db_libros import metadatos_de


def _metadatos_chroma(servicio, libro_id):
    return servicio.indice.obtener(libro_id)["metadatos"]


def test_alta_guarda_en_redis_y_en_chroma(servicio):
    servicio.alta_libro(libro_ejemplo(1))
    libro = servicio.catalogo.obtener("libro01")
    assert libro["anio"] == 2011 and libro["disponible"] is True and "sinopsis" not in libro
    documento = servicio.indice.obtener("libro01")
    assert documento["sinopsis"].startswith("Un astronauta")
    assert documento["metadatos"] == metadatos_de(libro)


def test_alta_rechaza_duplicados_de_id_e_isbn(servicio):
    servicio.alta_libro(libro_ejemplo(1))
    with pytest.raises(ValueError, match="id"):
        servicio.alta_libro(libro_ejemplo(1, isbn=isbn_valido(2)))
    with pytest.raises(ValueError, match="ISBN"):
        servicio.alta_libro(libro_ejemplo(2, isbn=isbn_valido(1)))
    assert servicio.catalogo.contar() == 1 and servicio.indice.contar() == 1


def test_alta_incompleta_no_escribe_nada(servicio):
    with pytest.raises(ValueError):
        servicio.alta_libro({"id": "libro09", "titulo": "Solo título"})
    assert servicio.catalogo.contar() == 0 and servicio.indice.contar() == 0


def test_lote_reporta_aceptados_y_rechazados(servicio, tmp_path):
    servicio.alta_libro(libro_ejemplo(1))
    filas = [libro_ejemplo(2), libro_ejemplo(3), libro_ejemplo(3, isbn=isbn_valido(30)),
             libro_ejemplo(4, isbn="978-0-00-000000-1"), libro_ejemplo(1, isbn=isbn_valido(11)),
             libro_ejemplo(5, isbn=isbn_valido(2)), {**libro_ejemplo(6), "titulo": ""}]
    ruta = tmp_path / "lote.json"
    ruta.write_text(json.dumps({"libros": filas}), encoding="utf-8")
    resultado = servicio.importar_archivo(ruta)
    assert resultado.total == 7
    assert resultado.agregados == ["libro02", "libro03"]
    motivos = {r["id"]: " ".join(r["motivos"]) for r in resultado.rechazados}
    assert "repetido" in motivos["libro03"]
    assert "ISBN" in motivos["libro04"]
    assert "existe" in motivos["libro01"]
    assert "ISBN" in motivos["libro05"]
    assert "titulo" in motivos["libro06"]
    assert servicio.catalogo.contar() == servicio.indice.contar() == 3


def test_lote_csv_con_punto_y_coma(servicio, tmp_path):
    libro = libro_ejemplo(7)
    ruta = tmp_path / "lote.csv"
    encabezado = ";".join(libro)
    fila = ";".join(str(v) for v in libro.values())
    ruta.write_text(encabezado + "\n" + fila + "\n", encoding="utf-8-sig")
    assert servicio.importar_archivo(ruta).agregados == ["libro07"]


def test_actualizar_sincroniza_ambas_bases(servicio):
    servicio.alta_libro(libro_ejemplo(1))
    llamadas = servicio.indice.modelo.llamadas
    servicio.actualizar_libro("libro01", libro_ejemplo(1, titulo="Nuevo título", calificacion=3.9))
    assert servicio.indice.modelo.llamadas == llamadas
    assert servicio.catalogo.obtener("libro01")["titulo"] == "Nuevo título"
    assert _metadatos_chroma(servicio, "libro01")["calificacion"] == 3.9
    servicio.actualizar_libro("libro01", libro_ejemplo(1, sinopsis="Un dragón custodia un castillo"))
    assert servicio.indice.modelo.llamadas == llamadas + 1
    assert servicio.buscar_libros("dragon castillo", 1)[0]["id"] == "libro01"


def test_actualizar_cambia_indice_de_isbn(servicio):
    servicio.alta_libro(libro_ejemplo(1))
    servicio.actualizar_libro("libro01", libro_ejemplo(1, isbn=isbn_valido(50)))
    servicio.alta_libro(libro_ejemplo(2, isbn=isbn_valido(1)))
    assert servicio.catalogo.dueno_isbn(isbn_valido(50)) == "libro01"


def test_eliminar_borra_de_ambas_bases(servicio):
    servicio.alta_libro(libro_ejemplo(1))
    servicio.eliminar_libro("libro01")
    assert servicio.catalogo.obtener("libro01") is None
    assert servicio.indice.obtener("libro01") is None
    assert servicio.catalogo.dueno_isbn(isbn_valido(1)) is None


def test_busqueda_semantica_devuelve_metadatos_y_similitud(servicio):
    servicio.alta_libro(libro_ejemplo(1, sinopsis="Un astronauta sobrevive en Marte"))
    servicio.alta_libro(libro_ejemplo(2, sinopsis="Una familia vive en un pueblo durante cien años",
                                      titulo="Cien años"))
    resultados = servicio.buscar_libros("familia pueblo", 2)
    assert resultados[0]["titulo"] == "Cien años"
    assert "sinopsis" in resultados[0] and 0 < resultados[0]["similitud"] <= 1
    assert resultados[0]["estado"] == "Disponible"


def test_filtrar_catalogo(servicio):
    servicio.alta_libro(libro_ejemplo(1, titulo="Dune", genero="ciencia ficcion"))
    servicio.alta_libro(libro_ejemplo(2, titulo="Drácula", genero="terror", idioma="en"))
    libros = servicio.catalogo_libros()
    assert [l["id"] for l in servicio.filtrar_catalogo(libros, texto="dracula")] == ["libro02"]
    assert [l["id"] for l in servicio.filtrar_catalogo(libros, genero="ciencia ficcion")] == ["libro01"]
    assert [l["id"] for l in servicio.filtrar_catalogo(libros, idioma="en")] == ["libro02"]


class FalloSimulado(RuntimeError):
    pass


def test_compensacion_si_redis_falla_en_el_alta(servicio, monkeypatch):
    def falla(*_a, **_k):
        raise FalloSimulado("Redis caído")
    monkeypatch.setattr(servicio.catalogo, "guardar", falla)
    with pytest.raises(FalloSimulado):
        servicio.alta_libro(libro_ejemplo(1))
    assert servicio.indice.contar() == 0


def test_compensacion_si_chroma_falla_en_el_alta(servicio, monkeypatch):
    def falla(*_a, **_k):
        raise FalloSimulado("Chroma caído")
    monkeypatch.setattr(servicio.indice, "agregar", falla)
    with pytest.raises(FalloSimulado):
        servicio.alta_libro(libro_ejemplo(1))
    assert servicio.catalogo.contar() == 0


def test_compensacion_en_actualizacion_restaura_chroma(servicio, monkeypatch):
    servicio.alta_libro(libro_ejemplo(1, sinopsis="Texto original del libro"))

    def falla(*_a, **_k):
        raise FalloSimulado("Redis caído")
    monkeypatch.setattr(servicio.catalogo, "guardar", falla)
    with pytest.raises(FalloSimulado):
        servicio.actualizar_libro("libro01", libro_ejemplo(1, sinopsis="Texto nuevo", titulo="Otro"))
    documento = servicio.indice.obtener("libro01")
    assert documento["sinopsis"] == "Texto original del libro"
    assert documento["metadatos"]["titulo"] == "Libro 1"


def test_compensacion_en_eliminacion_restaura_chroma(servicio, monkeypatch):
    servicio.alta_libro(libro_ejemplo(1))

    def falla(*_a, **_k):
        raise FalloSimulado("Redis caído")
    monkeypatch.setattr(servicio.catalogo, "eliminar", falla)
    with pytest.raises(FalloSimulado):
        servicio.eliminar_libro("libro01")
    assert servicio.indice.obtener("libro01") is not None
    assert servicio.catalogo.existe("libro01")


def test_revision_y_reparacion_de_sincronizacion(servicio):
    servicio.alta_libro(libro_ejemplo(1))
    servicio.alta_libro(libro_ejemplo(2))
    servicio.indice.actualizar_metadatos("libro01", {"titulo": "Desfasado"})
    servicio.indice.coleccion.delete(ids=["libro02"])
    huerfano = libro_ejemplo(3)
    servicio.indice.agregar([huerfano])
    informe = servicio.revisar_sincronizacion()
    assert informe.metadatos_distintos == ["libro01"]
    assert informe.faltan_en_chroma == ["libro02"]
    assert informe.huerfanos_en_chroma == ["libro03"]
    reparacion = servicio.reparar_sincronizacion()
    assert reparacion["corregidos"] == 1 and reparacion["sin_sinopsis"] == ["libro02"]
    assert _metadatos_chroma(servicio, "libro01")["titulo"] == "Libro 1"
    migrados = servicio.importar_huerfanos()
    assert migrados.agregados == ["libro03"] and servicio.catalogo.existe("libro03")


def test_cambio_de_modelo_reindexa_y_conserva_coleccion_anterior(servicio):
    servicio.alta_libro(libro_ejemplo(1))
    servicio.alta_libro(libro_ejemplo(2))
    anterior = servicio.indice.coleccion.name
    assert servicio.cambiar_modelo("multilingual-e5-small") == 2
    assert servicio.indice.clave_modelo == "multilingual-e5-small"
    assert servicio.indice.contar() == 2
    assert servicio.indice.cliente.get_collection(anterior).count() == 2


def test_cambio_de_modelo_fallido_no_conmuta(servicio, monkeypatch):
    servicio.alta_libro(libro_ejemplo(1))
    clave = servicio.indice.clave_modelo

    def fabrica_rota(_clave):
        raise FalloSimulado("sin modelo")
    monkeypatch.setattr(servicio.indice, "_fabrica_modelo", fabrica_rota)
    with pytest.raises(FalloSimulado):
        servicio.cambiar_modelo("multilingual-e5-small")
    assert servicio.indice.clave_modelo == clave and servicio.indice.contar() == 1
