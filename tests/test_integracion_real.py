"""Prueba de integración con Redis real, ChromaDB persistente y el modelo de embeddings real.

Se ejecuta solo si BIBLIOTECA_PRUEBAS_REALES=1. Usa un prefijo propio en la base configurada
(REDIS_DB) y al terminar elimina únicamente las llaves con ese prefijo.
"""
import os
import time

import chromadb
import pytest
from chromadb.config import Settings

import config
from conftest import persona_ejemplo
from db_catalogo import CatalogoRedis
from db_libros import GestorLibros
from db_personas import GestorPersonas
from db_prestamos import GestorPrestamos
from db_redis import Llaves, RegistroActividad, conectar_redis
from evaluar_busqueda import cargar_libros
from modelos import MODELO_POR_DEFECTO, esta_descargado
from seguridad import Cifrador
from servicios import ServicioBiblioteca

PREFIJO = "prueba_integracion:"

pytestmark = pytest.mark.skipif(os.environ.get("BIBLIOTECA_PRUEBAS_REALES") != "1",
                                reason="define BIBLIOTECA_PRUEBAS_REALES=1 para usar Redis y el modelo reales")


@pytest.fixture(scope="module")
def servicio_real(tmp_path_factory):
    if not esta_descargado(MODELO_POR_DEFECTO):
        pytest.skip("El modelo por defecto no está descargado")
    r = conectar_redis()
    llaves = Llaves(PREFIJO)
    sobrantes = list(r.scan_iter(match=llaves.patron))
    if sobrantes:
        r.delete(*sobrantes)
    cliente = chromadb.PersistentClient(path=str(tmp_path_factory.mktemp("chroma_real")),
                                        settings=Settings(anonymized_telemetry=False))
    original = config.ARCHIVO_MODELO_ACTIVO
    config.ARCHIVO_MODELO_ACTIVO = tmp_path_factory.mktemp("modelo") / "modelo_activo.txt"
    indice = GestorLibros(clave_modelo=MODELO_POR_DEFECTO, cliente=cliente)
    actividad = RegistroActividad(r, llaves)
    servicio = ServicioBiblioteca(r, llaves, CatalogoRedis(r, llaves), indice,
                                  GestorPersonas(r, Cifrador(llave_maestra=os.urandom(32)), llaves, actividad),
                                  GestorPrestamos(r, llaves, actividad), actividad)
    yield servicio
    restantes = list(r.scan_iter(match=llaves.patron))
    if restantes:
        r.delete(*restantes)
    config.ARCHIVO_MODELO_ACTIVO = original
    indice.modelo.liberar()


def test_redis_y_chroma_reales(servicio_real):
    s = servicio_real
    assert s.r.ping()
    assert s.indice.modelo.dispositivo in ("cuda", "cpu")

    inicio = time.perf_counter()
    resultado = s.importar_lote(cargar_libros())
    duracion = time.perf_counter() - inicio
    print(f"\nimportación de {len(resultado.agregados)} libros en {duracion:.1f} s "
          f"({s.indice.modelo.descripcion_dispositivo()})")
    assert len(resultado.agregados) == 200 and not resultado.rechazados
    assert s.catalogo.contar() == s.indice.contar() == 200

    duplicado = s.importar_lote(cargar_libros()[:3])
    assert not duplicado.agregados and len(duplicado.rechazados) == 3

    consultas = {"sociedad en la que los bomberos queman libros": "libro06",
                 "niño huérfano que descubre que es mago": "libro09",
                 "un capitán obsesionado con una ballena blanca": "libro79",
                 "a girl grows up alone in the marsh": "libro149"}
    for consulta, esperado in consultas.items():
        resultados = s.buscar_libros(consulta, 3)
        assert esperado in [r["id"] for r in resultados], consulta

    persona_id = s.personas.registrar(persona_ejemplo())
    crudo = s.r.hgetall(s.llaves.persona(persona_id))
    assert "Ana" not in crudo["nombre"] and crudo["telefono"].startswith("v2:")
    assert s.personas.obtener(persona_id)["telefono"] == "5512345678"

    prestamos = s.prestar(persona_id, ["libro06", "libro09"])
    assert s.indice.obtener("libro06")["metadatos"]["disponible"] is False
    assert "libro06" not in [r["id"] for r in s.buscar_libros("bomberos queman libros", 5, True)]
    with pytest.raises(ValueError):
        s.prestar(persona_id, ["libro06"])
    s.devolver(persona_id, [prestamos[0]["id"]])
    assert s.catalogo.obtener("libro06")["disponible"] is True
    assert s.indice.obtener("libro06")["metadatos"]["disponible"] is True
    s.devolver(persona_id)
    assert len(s.prestamos.historial_de(persona_id)) == 2

    s.actualizar_libro("libro01", {**s.obtener_libro("libro01"), "calificacion": 4.9})
    assert s.indice.obtener("libro01")["metadatos"]["calificacion"] == 4.9
    s.eliminar_libro("libro02")
    assert not s.catalogo.existe("libro02") and s.indice.obtener("libro02") is None
    assert s.revisar_sincronizacion().consistente
