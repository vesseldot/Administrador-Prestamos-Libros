import pytest

from conftest import libro_ejemplo, persona_ejemplo


@pytest.fixture
def con_datos(servicio):
    for n in range(1, 6):
        servicio.alta_libro(libro_ejemplo(n))
    ana = servicio.personas.registrar(persona_ejemplo())
    luis = servicio.personas.registrar(persona_ejemplo(nombre="Luis", correo="luis@mail.com"))
    return servicio, ana, luis


def _disponible(servicio, libro_id):
    redis_ = servicio.catalogo.obtener(libro_id)["disponible"]
    chroma = servicio.indice.obtener(libro_id)["metadatos"]["disponible"]
    assert redis_ == chroma
    return redis_


def test_prestamo_multiple_en_una_operacion(con_datos):
    servicio, ana, _ = con_datos
    prestamos = servicio.prestar(ana, ["libro01", "libro02", "libro03"])
    assert [p["libro_id"] for p in prestamos] == ["libro01", "libro02", "libro03"]
    assert all(p["estado"] == "activo" and p["fecha_prestamo"] for p in prestamos)
    assert all(not _disponible(servicio, f"libro0{n}") for n in (1, 2, 3))
    assert servicio.prestamos.activo_de_libro("libro02")["persona_id"] == ana
    assert servicio.prestamos.personas_con_prestamo() == [ana]


def test_prestamos_en_operaciones_separadas_hasta_el_limite(con_datos):
    servicio, ana, _ = con_datos
    servicio.prestar(ana, ["libro01"])
    servicio.prestar(ana, ["libro02", "libro03"])
    with pytest.raises(ValueError, match="le quedan 0"):
        servicio.prestar(ana, ["libro04"])
    assert _disponible(servicio, "libro04")


def test_mas_de_tres_en_una_sola_operacion(con_datos):
    servicio, ana, _ = con_datos
    with pytest.raises(ValueError, match="3"):
        servicio.prestar(ana, ["libro01", "libro02", "libro03", "libro04"])
    assert servicio.prestamos.contar_activos() == 0


def test_un_libro_no_puede_tener_dos_prestamos_activos(con_datos):
    servicio, ana, luis = con_datos
    servicio.prestar(ana, ["libro01"])
    with pytest.raises(ValueError, match="no está disponible"):
        servicio.prestar(luis, ["libro01"])


def test_operacion_todo_o_nada(con_datos):
    servicio, ana, luis = con_datos
    servicio.prestar(ana, ["libro02"])
    with pytest.raises(ValueError):
        servicio.prestar(luis, ["libro01", "libro02"])
    assert _disponible(servicio, "libro01")
    assert servicio.prestamos.activos_de(luis) == []


def test_libro_marcado_no_disponible_no_se_presta(con_datos):
    servicio, ana, _ = con_datos
    servicio.actualizar_libro("libro05", libro_ejemplo(5, disponible=False))
    with pytest.raises(ValueError, match="no está disponible"):
        servicio.prestar(ana, ["libro05"])


def test_persona_o_libro_inexistente(con_datos):
    servicio, ana, _ = con_datos
    with pytest.raises(ValueError, match="persona no existe"):
        servicio.prestar("P9999", ["libro01"])
    with pytest.raises(ValueError, match="no existe"):
        servicio.prestar(ana, ["libro99"])


def test_devolver_uno_dos_y_todos_conserva_historial(con_datos):
    servicio, ana, _ = con_datos
    prestamos = servicio.prestar(ana, ["libro01", "libro02", "libro03"])
    ids = [p["id"] for p in prestamos]
    devuelto = servicio.devolver(ana, [ids[0]])
    assert devuelto[0]["estado"] == "devuelto" and devuelto[0]["fecha_devolucion"]
    assert _disponible(servicio, "libro01") and not _disponible(servicio, "libro02")
    servicio.devolver(ana, ids[1:])
    assert servicio.prestamos.activos_de(ana) == []
    historial = servicio.prestamos.historial_de(ana)
    assert len(historial) == 3 and all(p["estado"] == "devuelto" for p in historial)
    assert servicio.prestamos.personas_con_prestamo() == []
    servicio.prestar(ana, ["libro04", "libro05"])
    servicio.devolver(ana)
    assert len(servicio.prestamos.historial_de(ana)) == 5
    assert servicio.prestamos.contar_activos() == 0


def test_no_se_devuelve_un_prestamo_ajeno_o_ya_devuelto(con_datos):
    servicio, ana, luis = con_datos
    prestamo = servicio.prestar(ana, ["libro01"])[0]
    with pytest.raises(ValueError):
        servicio.devolver(luis, [prestamo["id"]])
    servicio.devolver(ana, [prestamo["id"]])
    with pytest.raises(ValueError):
        servicio.devolver(ana, [prestamo["id"]])


def test_libro_prestado_no_se_elimina_ni_se_marca_disponible(con_datos):
    servicio, ana, _ = con_datos
    servicio.prestar(ana, ["libro01"])
    with pytest.raises(ValueError, match="prestado"):
        servicio.eliminar_libro("libro01")
    servicio.actualizar_libro("libro01", libro_ejemplo(1, disponible=True, titulo="Editado"))
    assert not _disponible(servicio, "libro01")


def test_personas_con_prestamos_y_estadisticas(con_datos):
    servicio, ana, luis = con_datos
    servicio.prestar(ana, ["libro01", "libro02"])
    servicio.prestar(luis, ["libro03"])
    resumen = {p["id"]: [x["titulo"] for x in p["prestamos"]] for p in servicio.personas_con_prestamos()}
    assert resumen == {ana: ["Libro 1", "Libro 2"], luis: ["Libro 3"]}
    estadisticas = servicio.estadisticas()
    assert estadisticas["libros"] == 5 and estadisticas["prestados"] == 3
    assert estadisticas["disponibles"] == 2 and estadisticas["personas"] == 2
    assert estadisticas["personas_con_prestamo"] == 2
    tipos = [e["tipo"] for e in servicio.actividad.recientes(5)]
    assert tipos[0] == "prestamo"


def test_vencimiento_derivado(con_datos):
    servicio, ana, _ = con_datos
    prestamo = servicio.prestar(ana, ["libro01"])[0]
    servicio.r.hset(servicio.llaves.prestamo(prestamo["id"]), "fecha_limite", "2000-01-01")
    activo = servicio.prestamos.activos_de(ana)[0]
    assert activo["vencido"] and activo["estado_visible"] == "Vencido"


def test_buscar_solo_disponibles_excluye_prestados(con_datos):
    servicio, ana, _ = con_datos
    servicio.prestar(ana, ["libro01"])
    ids = [l["id"] for l in servicio.buscar_libros("astronauta marte", 5, solo_disponibles=True)]
    assert "libro01" not in ids and len(ids) == 4
