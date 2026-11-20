import pytest

from conftest import libro_ejemplo, persona_ejemplo
from db_redis import ErrorBaseOcupada, Llaves, preparar_base


def test_registro_cifra_datos_en_redis(servicio):
    pid = servicio.personas.registrar(persona_ejemplo())
    crudo = servicio.r.hgetall(servicio.llaves.persona(pid))
    assert pid == "P0001"
    for campo, valor in (("nombre", "Ana"), ("correo", "ana.lopez@mail.com"), ("telefono", "5512345678")):
        assert valor not in crudo[campo] and crudo[campo].startswith("v2:")
    assert "edad" not in crudo
    persona = servicio.personas.obtener(pid)
    assert persona["nombre_completo"] == "Ana López Ruiz" and persona["integridad_ok"]
    assert isinstance(persona["edad"], int)


def test_no_se_guarda_sin_aviso_de_privacidad(servicio):
    with pytest.raises(ValueError, match="aviso de privacidad"):
        servicio.personas.registrar(persona_ejemplo(acepta_aviso_privacidad=False))
    assert servicio.personas.contar() == 0


def test_correo_duplicado(servicio):
    servicio.personas.registrar(persona_ejemplo())
    with pytest.raises(ValueError, match="correo"):
        servicio.personas.registrar(persona_ejemplo(correo="ANA.LOPEZ@mail.com", nombre="Otra"))


def test_actualizar_conserva_fecha_de_aviso_y_reindexa_correo(servicio):
    pid = servicio.personas.registrar(persona_ejemplo())
    antes = servicio.personas.obtener(pid)
    servicio.personas.actualizar(pid, persona_ejemplo(correo="nuevo@mail.com", ciudad="Cholula"))
    despues = servicio.personas.obtener(pid)
    assert despues["fecha_aviso"] == antes["fecha_aviso"]
    assert despues["correo"] == "nuevo@mail.com" and despues["ciudad"] == "Cholula"
    otra = servicio.personas.registrar(persona_ejemplo(nombre="Luis"))
    assert otra == "P0002"


def test_buscar_por_nombre_y_campos_no_sensibles(servicio):
    servicio.personas.registrar(persona_ejemplo())
    servicio.personas.registrar(persona_ejemplo(nombre="Luis", apellido_paterno="Pérez",
                                                correo="luis@mail.com", tipo_usuario="Profesor",
                                                ocupacion="Docente", ciudad="Tlaxcala"))
    assert [p["id"] for p in servicio.personas.buscar("lopez")] == ["P0001"]
    assert [p["id"] for p in servicio.personas.buscar("luis perez")] == ["P0002"]
    assert [p["id"] for p in servicio.personas.buscar("", tipo_usuario="Profesor")] == ["P0002"]
    assert servicio.personas.buscar("5512345678") == []


def test_eliminar_bloqueado_con_prestamos_y_permitido_despues(servicio):
    pid = servicio.personas.registrar(persona_ejemplo())
    servicio.alta_libro(libro_ejemplo(1))
    servicio.prestar(pid, ["libro01"])
    with pytest.raises(ValueError, match="prestados"):
        servicio.eliminar_persona(pid)
    servicio.devolver(pid)
    servicio.eliminar_persona(pid)
    assert servicio.personas.obtener(pid) is None
    assert len(servicio.prestamos.historial_de(pid)) == 1
    servicio.personas.registrar(persona_ejemplo())


def test_dato_alterado_se_marca_sin_romper_la_lectura(servicio):
    pid = servicio.personas.registrar(persona_ejemplo())
    servicio.r.hset(servicio.llaves.persona(pid), "telefono",
                    servicio.r.hget(servicio.llaves.persona(pid), "nombre"))
    persona = servicio.personas.obtener(pid)
    assert persona["integridad_ok"] is False and persona["telefono"] == ""


def test_exportar_datos_arco(servicio):
    pid = servicio.personas.registrar(persona_ejemplo())
    datos = servicio.exportar_persona(pid)
    assert datos["correo"] == "ana.lopez@mail.com" and datos["prestamos"] == []


def test_base_con_llaves_ajenas_se_rechaza(redis_falso):
    redis_falso.set("usuario:1", "x")
    with pytest.raises(ErrorBaseOcupada):
        preparar_base(redis_falso, Llaves("bib:"))


def test_base_vacia_se_prepara(redis_falso):
    preparar_base(redis_falso, Llaves("bib:"))
    assert redis_falso.get("bib:meta:esquema") == "2"
