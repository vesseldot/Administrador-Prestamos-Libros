from types import SimpleNamespace

import pytest

import config
import gestor_modelos
from modelos import MODELOS

CLAVE = "qwen3-embedding-0.6b"
INFO = MODELOS[CLAVE]
ARCHIVOS_REMOTOS = {
    "model.safetensors": 5000, "tokenizer.json": 300, "tokenizer_config.json": 20, "config.json": 10,
    "modules.json": 5, "config_sentence_transformers.json": 5, "1_Pooling/config.json": 5, "merges.txt": 50,
    "vocab.json": 60, "README.md": 40, ".gitattributes": 1, "onnx/model.onnx": 9000, "pytorch_model.bin": 5000,
}


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DIR_MODELOS", tmp_path / "modelos")
    return tmp_path / "modelos"


def carpeta_snapshot(cache):
    repo = "models--" + INFO["nombre_completo"].replace("/", "--")
    return cache / repo / "snapshots" / INFO["revision"]


def instalar_hub_simulado(monkeypatch, cache, llamadas):
    import huggingface_hub

    def model_info(self, repo, revision=None, files_metadata=False):
        assert repo == INFO["nombre_completo"] and revision == INFO["revision"]
        return SimpleNamespace(siblings=[SimpleNamespace(rfilename=n, size=s) for n, s in ARCHIVOS_REMOTOS.items()])

    def hf_hub_download(repo, archivo, revision=None, cache_dir=None, tqdm_class=None):
        assert revision == INFO["revision"] and cache_dir == str(cache)
        llamadas.append(archivo)
        destino = carpeta_snapshot(cache) / archivo
        destino.parent.mkdir(parents=True, exist_ok=True)
        tamano = ARCHIVOS_REMOTOS[archivo]
        barra = tqdm_class(total=tamano, unit="B", name="huggingface_hub.http_get")
        barra.update(tamano // 2)
        barra.update(tamano - tamano // 2)
        barra.close()
        destino.write_bytes(b"x" * tamano)
        return str(destino)

    monkeypatch.setattr(huggingface_hub.HfApi, "model_info", model_info)
    monkeypatch.setattr(huggingface_hub, "hf_hub_download", hf_hub_download)


def test_filtro_de_archivos():
    assert gestor_modelos._incluido("model.safetensors")
    assert gestor_modelos._incluido("1_Pooling/config.json")
    assert gestor_modelos._incluido("merges.txt")
    for archivo in ("onnx/model.onnx", "pytorch_model.bin", "openvino/openvino_model.bin", "README.md",
                    ".gitattributes", "tf_model.h5"):
        assert not gestor_modelos._incluido(archivo), archivo


def test_revisiones_fijadas_y_metadatos_completos():
    for clave, info in MODELOS.items():
        assert len(info["revision"]) == 40, clave
        assert info["licencia"] and info["tamano_mb"] > 0 and "model.safetensors" in info["archivos"]


def test_modelo_ausente(cache):
    assert not gestor_modelos.esta_descargado(CLAVE)
    assert gestor_modelos.ruta_local(CLAVE) is None
    assert set(gestor_modelos.archivos_faltantes(CLAVE)) == set(INFO["archivos"])


def test_descarga_con_progreso_y_reutilizacion(cache, monkeypatch):
    llamadas = []
    instalar_hub_simulado(monkeypatch, cache, llamadas)
    avances = []
    ruta = gestor_modelos.descargar(CLAVE, lambda h, t, a: avances.append((h, t, a)))
    total = sum(s for n, s in ARCHIVOS_REMOTOS.items() if gestor_modelos._incluido(n))
    assert ruta == carpeta_snapshot(cache)
    assert gestor_modelos.esta_descargado(CLAVE)
    assert "onnx/model.onnx" not in llamadas and "pytorch_model.bin" not in llamadas
    assert avances[-1][0] == avances[-1][1] == total
    assert [h for h, *_ in avances] == sorted(h for h, *_ in avances)
    llamadas.clear()
    gestor_modelos.descargar(CLAVE)
    assert llamadas == []


def test_descarga_parcial_retoma_solo_lo_faltante(cache, monkeypatch):
    llamadas = []
    instalar_hub_simulado(monkeypatch, cache, llamadas)
    gestor_modelos.descargar(CLAVE)
    (carpeta_snapshot(cache) / "tokenizer.json").unlink()
    llamadas.clear()
    gestor_modelos.descargar(CLAVE)
    assert llamadas == ["tokenizer.json"]


def test_sin_conexion(cache, monkeypatch):
    import huggingface_hub

    def sin_red(*_a, **_k):
        raise ConnectionError("Failed to establish a new connection")
    monkeypatch.setattr(huggingface_hub.HfApi, "model_info", sin_red)
    with pytest.raises(gestor_modelos.SinConexion, match="conexión"):
        gestor_modelos.descargar(CLAVE)


def test_espacio_insuficiente(cache, monkeypatch):
    instalar_hub_simulado(monkeypatch, cache, [])
    monkeypatch.setattr(gestor_modelos, "espacio_libre", lambda _r: 10)
    with pytest.raises(gestor_modelos.EspacioInsuficiente, match="GB"):
        gestor_modelos.descargar(CLAVE)


def test_revision_sin_archivos_necesarios(cache, monkeypatch):
    import huggingface_hub
    monkeypatch.setattr(huggingface_hub.HfApi, "model_info",
                        lambda *_a, **_k: SimpleNamespace(siblings=[SimpleNamespace(rfilename="config.json", size=1)]))
    with pytest.raises(gestor_modelos.ErrorDescarga, match="no contiene"):
        gestor_modelos.plan_descarga(CLAVE)


def test_cargar_modelo_ausente_da_mensaje_claro(cache):
    from modelos import ModeloEmbeddings, ModeloNoDisponible
    with pytest.raises(ModeloNoDisponible, match="gestionar_modelos.py descargar"):
        ModeloEmbeddings(CLAVE).embeber_consulta("hola")
