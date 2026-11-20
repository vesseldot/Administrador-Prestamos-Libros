import importlib
import subprocess
import sys
from pathlib import Path

import pytest

import config
from conftest import libro_ejemplo

VARIABLES = ["REDIS_PORT", "REDIS_DB", "REDIS_PREFIJO", "BIBLIOTECA_DISPOSITIVO", "BIBLIOTECA_MODELO",
             "BIBLIOTECA_PERMITIR_DESCARGA", "BIBLIOTECA_AES_KEY", "BIBLIOTECA_CHROMA_PATH"]


@pytest.fixture
def recargar(monkeypatch):
    def aplicar(**valores):
        for nombre in VARIABLES:
            monkeypatch.delenv(nombre, raising=False)
        for nombre, valor in valores.items():
            monkeypatch.setenv(nombre, valor)
        monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None, raising=False)
        return importlib.reload(config)
    yield aplicar
    monkeypatch.undo()
    importlib.reload(config)


def test_valores_por_defecto_validos(recargar):
    modulo = recargar()
    assert modulo.validar() == []
    assert modulo.REDIS_DB == 2 and modulo.REDIS_PREFIJO == "bib:"


def test_errores_claros(recargar):
    modulo = recargar(REDIS_PORT="abc", REDIS_DB="20", REDIS_PREFIJO="bib", BIBLIOTECA_DISPOSITIVO="tpu",
                      BIBLIOTECA_MODELO="no-existe", BIBLIOTECA_PERMITIR_DESCARGA="quizas",
                      BIBLIOTECA_AES_KEY="corta")
    errores = " | ".join(modulo.validar())
    for fragmento in ("REDIS_PORT", "REDIS_DB", "REDIS_PREFIJO", "BIBLIOTECA_DISPOSITIVO", "BIBLIOTECA_MODELO",
                      "BIBLIOTECA_PERMITIR_DESCARGA", "BIBLIOTECA_AES_KEY"):
        assert fragmento in errores, fragmento


def test_ruta_relativa_de_chroma(recargar):
    modulo = recargar(BIBLIOTECA_CHROMA_PATH="otra_carpeta/indice")
    assert Path(modulo.CHROMA_PATH) == modulo.BASE_DIR / "otra_carpeta" / "indice"
    assert modulo.ARCHIVO_MODELO_ACTIVO == modulo.BASE_DIR / "otra_carpeta" / "modelo_activo.txt"


def test_chroma_conserva_los_datos_en_disco(servicio, indice, tmp_path):
    servicio.alta_libro(libro_ejemplo(1))
    ruta = indice.cliente.get_settings().persist_directory
    codigo = (f"import chromadb; c = chromadb.PersistentClient(path={ruta!r}); "
              f"col = c.get_collection({indice.coleccion.name!r}); "
              "print(col.count(), col.get(ids=['libro01'])['documents'][0][:13])")
    salida = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, timeout=120)
    assert salida.stdout.strip().endswith("1 Un astronauta"), salida.stderr[-500:]
