"""Contrato de la API que consume la interfaz (ver INTEGRACION.md)."""
import pytest
import redis

from conftest import libro_ejemplo, persona_ejemplo
from servicios import describir_error


def test_estado_del_sistema_y_modelo(servicio):
    assert servicio.redis_disponible() is True
    info = servicio.info_sistema()
    for clave in ("redis_host", "redis_port", "redis_db", "redis_version", "prefijo", "llaves_propias", "esquema",
                  "chroma_path", "coleccion", "documentos", "modelo", "dispositivo", "dir_modelos",
                  "descarga_permitida", "gpu", "python", "torch"):
        assert clave in info, clave
    modelo = servicio.info_modelo()
    assert modelo["modelo"] == servicio.clave_modelo and modelo["dispositivo"] == "cpu · simulado"
    assert servicio.modelo_pendiente_de_descarga() is False
    assert servicio.precargar_modelo()["modelo"] == servicio.clave_modelo
    catalogo = servicio.catalogo_modelos()
    assert sum(m["activo"] for m in catalogo) == 1 and all("descargado" in m for m in catalogo)


def test_tokens_y_cortes(servicio):
    servicio.alta_libro(libro_ejemplo(1))
    resultado = servicio.contar_tokens("uno dos tres")
    assert resultado == {"clave": servicio.clave_modelo, "tokens": 3, "palabras": 3,
                         "maximo": resultado["maximo"], "cabe": True}
    cortes = servicio.revisar_cortes()
    assert cortes["resultados"][0][0] == "libro01" and cortes["cortadas"] == 0


def test_personas_prestamos_y_actividad(servicio):
    servicio.alta_libro(libro_ejemplo(1))
    pid = servicio.registrar_persona(persona_ejemplo())
    servicio.actualizar_persona(pid, persona_ejemplo(ciudad="Cholula"))
    assert servicio.obtener_persona(pid)["ciudad"] == "Cholula"
    assert [p["id"] for p in servicio.buscar_personas("lopez")] == [pid]
    assert servicio.contar_personas() == 1 and len(servicio.listar_personas()) == 1
    servicio.prestar(pid, ["libro01"])
    assert servicio.max_libros_por_persona == 3 and servicio.cupo_disponible(pid) == 2
    assert [p["libro_id"] for p in servicio.prestamos_activos(pid)] == ["libro01"]
    assert len(servicio.prestamos_activos()) == 1
    assert len(servicio.historial_prestamos(pid)) == 1
    assert servicio.actividad_reciente(1)[0]["tipo"] == "prestamo"
    assert servicio.contar_cifrado_heredado() == 0 and servicio.migrar_cifrado_heredado() == 0
    assert servicio.estado_seguridad()["cifrado_heredado"] == 0
    assert servicio.contar_libros() == 1


def test_datos_de_ejemplo(servicio):
    assert [a.name for a in servicio.archivos_ejemplo()] == [
        "libros_catalogo_ampliado.csv", "libros_lote.csv", "libros_lote_nuevos.csv"]
    resultado = servicio.importar_datos_ejemplo()
    assert len(resultado.agregados) == 200 and not resultado.rechazados


@pytest.mark.parametrize("error, categoria, tipo", [
    (ValueError("dato inválido"), "validacion", "aviso"),
    (redis.ConnectionError("x"), "redis", "error"),
    (redis.AuthenticationError("x"), "redis", "error"),
    (RuntimeError("x"), "inesperado", "error"),
])
def test_describir_error(error, categoria, tipo):
    descripcion = describir_error(error)
    assert descripcion["categoria"] == categoria and descripcion["tipo"] == tipo
    assert descripcion["titulo"] and descripcion["mensaje"]


def test_describir_errores_de_modelo_e_integridad():
    import gestor_modelos
    from modelos import ModeloNoDisponible
    from seguridad import ErrorCifrado
    assert describir_error(ModeloNoDisponible("falta"))["categoria"] == "modelo"
    assert describir_error(gestor_modelos.SinConexion("sin red"))["categoria"] == "modelo"
    assert describir_error(ErrorCifrado("x"))["categoria"] == "integridad"


def test_control_de_acceso_del_servicio(servicio):
    from seguridad import ControlAcceso, hash_contrasena
    almacen = {"hash": hash_contrasena("clave-inicial")}
    acceso = ControlAcceso(maximo_intentos=2, espera_segundos=60, leer_hash=lambda: almacen["hash"],
                           guardar_hash=lambda c: almacen.update(hash=hash_contrasena(c)))
    assert acceso.intentar("clave-inicial") == (True, "")
    assert acceso.intentar("mala")[0] is False
    correcto, mensaje = acceso.intentar("mala")
    assert not correcto and "Espera" in mensaje and acceso.segundos_restantes() > 0
    acceso.bloqueado_hasta = 0
    with pytest.raises(ValueError, match="no coinciden"):
        acceso.cambiar_contrasena("clave-inicial", "nueva-clave-1", "otra")
    acceso.cambiar_contrasena("clave-inicial", "nueva-clave-1", "nueva-clave-1")
    assert acceso.intentar("nueva-clave-1")[0]
    assert servicio.acceso is not None
