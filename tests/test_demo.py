import fakeredis

import config
from demo_interfaz import CONTRASENA_DEMO, PERSONAS_DEMO, crear_servicio_demo


def test_demo_aislada_con_datos(monkeypatch):
    original = config.ARCHIVO_MODELO_ACTIVO
    monkeypatch.setattr(config, "ARCHIVO_MODELO_ACTIVO", original)
    servicio = crear_servicio_demo()
    assert isinstance(servicio.r, fakeredis.FakeRedis)
    assert servicio.llaves.prefijo == "demo:"
    assert servicio.contar_libros() == 200 and servicio.contar_personas() == len(PERSONAS_DEMO)
    assert any(p["vencido"] for p in servicio.prestamos_activos())
    assert servicio.acceso.intentar(CONTRASENA_DEMO)[0]
    assert config.ARCHIVO_MODELO_ACTIVO != original
    assert servicio.buscar_libros("bomberos queman libros", 3)


def test_demo_sin_datos():
    servicio = crear_servicio_demo(con_datos=False)
    assert servicio.contar_libros() == 0 and servicio.contar_personas() == 0
