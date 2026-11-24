"""Memoria de los modelos: cada modelo conserva lo que ya procesó y solo calcula lo que le falta."""
import pytest

import config
from conftest import libro_ejemplo

QWEN = "paraphrase-multilingual-MiniLM-L12-v2"  # modelo con el que arrancan las pruebas (modelo A)
E5 = "multilingual-e5-small"


class FalloSimulado(RuntimeError):
    pass


def _espiar_calculos(servicio, monkeypatch):
    """Registra los textos que cualquier modelo creado a partir de ahora convierte en vectores."""
    calculados: list[str] = []
    fabrica = servicio.indice._fabrica_modelo

    def fabrica_espia(clave):
        modelo = fabrica(clave)
        original = modelo.embeber_documentos

        def embeber(textos):
            calculados.extend(textos)
            return original(textos)
        modelo.embeber_documentos = embeber
        return modelo
    monkeypatch.setattr(servicio.indice, "_fabrica_modelo", fabrica_espia)
    return calculados


def _preparar(servicio, cantidad=4):
    assert servicio.indice.clave_modelo == QWEN
    for n in range(1, cantidad + 1):
        servicio.alta_libro(libro_ejemplo(n, sinopsis=f"Historia numero {n} sobre el mar"))


def test_volver_a_un_modelo_solo_calcula_lo_nuevo(servicio, monkeypatch):
    _preparar(servicio, 4)
    calculados = _espiar_calculos(servicio, monkeypatch)
    servicio.cambiar_modelo(E5)
    assert len(calculados) == 4
    servicio.alta_libro(libro_ejemplo(5, sinopsis="Historia numero 5 sobre el mar"))
    servicio.alta_libro(libro_ejemplo(6, sinopsis="Historia numero 6 sobre el mar"))
    calculados.clear()

    assert servicio.cambiar_modelo(QWEN) == 6

    assert sorted(calculados) == ["Historia numero 5 sobre el mar", "Historia numero 6 sobre el mar"]
    assert servicio.indice.contar() == 6
    assert servicio.resumen_ultimo_cambio == {"reutilizados": 4, "calculados": 2, "eliminados": 0}


def test_sinopsis_editada_se_recalcula_y_el_resto_se_reutiliza(servicio, monkeypatch):
    _preparar(servicio, 3)
    calculados = _espiar_calculos(servicio, monkeypatch)
    servicio.cambiar_modelo(E5)
    libro = servicio.obtener_libro("libro02")
    servicio.actualizar_libro("libro02", {**libro, "sinopsis": "Una sinopsis totalmente distinta"})
    calculados.clear()

    servicio.cambiar_modelo(QWEN)

    assert calculados == ["Una sinopsis totalmente distinta"]
    assert servicio.indice.obtener("libro02")["sinopsis"] == "Una sinopsis totalmente distinta"
    assert servicio.resumen_ultimo_cambio == {"reutilizados": 2, "calculados": 1, "eliminados": 0}


def test_libro_eliminado_desaparece_del_modelo_al_que_se_vuelve(servicio, monkeypatch):
    _preparar(servicio, 3)
    servicio.cambiar_modelo(E5)
    servicio.eliminar_libro("libro02")

    servicio.cambiar_modelo(QWEN)

    assert servicio.indice.obtener("libro02") is None
    assert servicio.indice.ids() == {"libro01", "libro03"}
    assert servicio.resumen_ultimo_cambio == {"reutilizados": 2, "calculados": 0, "eliminados": 1}


def test_datos_del_libro_se_actualizan_sin_recalcular_vectores(servicio, monkeypatch):
    _preparar(servicio, 2)
    calculados = _espiar_calculos(servicio, monkeypatch)
    servicio.cambiar_modelo(E5)
    libro = servicio.obtener_libro("libro01")
    servicio.actualizar_libro("libro01", {**libro, "titulo": "Titulo corregido"})
    calculados.clear()

    servicio.cambiar_modelo(QWEN)

    assert calculados == []
    assert servicio.indice.obtener("libro01")["metadatos"]["titulo"] == "Titulo corregido"


def test_interrupcion_conserva_lo_avanzado_y_la_siguiente_continua(servicio, monkeypatch):
    _preparar(servicio, 5)
    monkeypatch.setattr(config, "TAMANO_LOTE_EMBEDDINGS", 2)
    fabrica = servicio.indice._fabrica_modelo
    lotes = {"hechos": 0}

    def fabrica_con_fallo(clave):
        modelo = fabrica(clave)
        original = modelo.embeber_documentos

        def embeber(textos):
            if lotes["hechos"] == 1:
                raise FalloSimulado("corte a mitad del proceso")
            lotes["hechos"] += 1
            return original(textos)
        modelo.embeber_documentos = embeber
        return modelo
    monkeypatch.setattr(servicio.indice, "_fabrica_modelo", fabrica_con_fallo)

    with pytest.raises(FalloSimulado):
        servicio.cambiar_modelo(E5)
    assert servicio.indice.clave_modelo == QWEN and servicio.indice.contar() == 5
    assert servicio.indice.cliente.get_collection("libros_multilingual_e5_small").count() == 2

    monkeypatch.setattr(servicio.indice, "_fabrica_modelo", fabrica)
    calculados = _espiar_calculos(servicio, monkeypatch)
    servicio.cambiar_modelo(E5)

    assert len(calculados) == 3
    assert servicio.indice.contar() == 5
    assert servicio.resumen_ultimo_cambio == {"reutilizados": 2, "calculados": 3, "eliminados": 0}


def test_cambio_al_mismo_modelo_no_hace_nada(servicio, monkeypatch):
    _preparar(servicio, 2)
    calculados = _espiar_calculos(servicio, monkeypatch)
    assert servicio.cambiar_modelo(QWEN) == 2
    assert calculados == []
