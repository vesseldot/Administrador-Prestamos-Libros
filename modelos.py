"""Modelos de embeddings disponibles y su envoltura sobre sentence-transformers.

Reglas:
  - Indexar y consultar siempre con el mismo modelo.
  - Cada modelo tiene su propia colección y conserva lo que ya procesó: al cambiar de modelo solo se
    calculan los libros nuevos o con la sinopsis modificada.
"""
import re
import threading

import config

INSTRUCCION_LIBROS = ("Given a search query, retrieve relevant book descriptions "
                      "that match the query")
INSTRUCCION_GENERICA = "Given a web search query, retrieve relevant passages that answer the query"
INSTRUCCION_POR_DEFECTO = INSTRUCCION_GENERICA

ARCHIVOS_BASE = ["config.json", "modules.json", "model.safetensors", "1_Pooling/config.json"]

MODELOS = {
    "qwen3-embedding-0.6b": {
        "nombre_completo": "Qwen/Qwen3-Embedding-0.6B",
        "revision": "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3", "licencia": "Apache-2.0",
        "archivos": ARCHIVOS_BASE + ["tokenizer.json", "tokenizer_config.json", "config_sentence_transformers.json"],
        "dim": 1024, "max_tokens": 512, "estilo": "instruccion", "media_precision": True,
        "tamano": "~1.2 GB", "tamano_mb": 1210,
        "nota": "Multilingüe, contexto largo, instrucción en consultas. Float16 en GPU.",
    },
    "paraphrase-multilingual-MiniLM-L12-v2": {
        "nombre_completo": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "revision": "e8f8c211226b894fcb81acc59f3b34ba3efd5f42", "licencia": "Apache-2.0",
        "archivos": ARCHIVOS_BASE + ["tokenizer.json", "sentence_bert_config.json"],
        "dim": 384, "max_tokens": 128, "estilo": None, "media_precision": False,
        "tamano": "~500 MB", "tamano_mb": 505,
        "nota": "Rápido y ligero; corta las sinopsis después de 128 tokens.",
    },
    "multilingual-e5-small": {
        "nombre_completo": "intfloat/multilingual-e5-small",
        "revision": "614241f622f53c4eeff9890bdc4f31cfecc418b3", "licencia": "MIT",
        "archivos": ARCHIVOS_BASE + ["tokenizer.json", "sentence_bert_config.json"],
        "dim": 384, "max_tokens": 512, "estilo": "e5", "media_precision": False,
        "tamano": "~490 MB", "tamano_mb": 495, "nota": "Ligero, 512 tokens. Prefijos query:/passage:.",
    },
    "multilingual-e5-base": {
        "nombre_completo": "intfloat/multilingual-e5-base",
        "revision": "d128750597153bb5987e10b1c3493a34e5a4502a", "licencia": "MIT",
        "archivos": ARCHIVOS_BASE + ["tokenizer.json", "sentence_bert_config.json"],
        "dim": 768, "max_tokens": 512, "estilo": "e5", "media_precision": False,
        "tamano": "~1.1 GB", "tamano_mb": 1135, "nota": "Muy bueno en español, 512 tokens. Prefijos.",
    },
    "sentence_similarity_spanish_es": {
        "nombre_completo": "hiiamsid/sentence_similarity_spanish_es",
        "revision": "66ab46adac3910bb6ea6085b962a25e49513b981", "licencia": "Apache-2.0",
        "archivos": ARCHIVOS_BASE + ["tokenizer.json", "vocab.txt", "sentence_bert_config.json"],
        "dim": 768, "max_tokens": 512, "estilo": None, "media_precision": False,
        "tamano": "~440 MB", "tamano_mb": 441, "nota": "Solo español, 512 tokens.",
    },
}

MODELO_POR_DEFECTO = (config.MODELO_POR_DEFECTO if config.MODELO_POR_DEFECTO in MODELOS
                      else "qwen3-embedding-0.6b")


class ModeloNoDisponible(RuntimeError):
    """El modelo no está descargado en la ubicación local configurada."""


def nombre_coleccion(clave_modelo: str) -> str:
    limpio = re.sub(r"[^a-zA-Z0-9]+", "_", clave_modelo).strip("_").lower()
    return f"libros_{limpio}"[:60]


def esta_descargado(clave_modelo: str) -> bool:
    from gestor_modelos import esta_descargado as descargado
    return descargado(clave_modelo)


def resolver_dispositivo() -> str:
    if config.DISPOSITIVO in ("cpu", "cuda"):
        return config.DISPOSITIVO
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


class ModeloEmbeddings:
    """Carga perezosa de un modelo de sentence-transformers."""

    def __init__(self, clave_modelo: str, dispositivo: str | None = None,
                 instruccion: str = INSTRUCCION_POR_DEFECTO):
        if clave_modelo not in MODELOS:
            raise ValueError(f"Modelo desconocido: {clave_modelo}")
        self.clave = clave_modelo
        self.info = MODELOS[clave_modelo]
        self.dispositivo = dispositivo or resolver_dispositivo()
        self.instruccion = instruccion
        self._modelo = None
        self._candado = threading.Lock()

    @property
    def cargado(self) -> bool:
        return self._modelo is not None

    @property
    def modelo(self):
        with self._candado:
            if self._modelo is None:
                self._modelo = self._cargar()
            return self._modelo

    def _cargar(self):
        from gestor_modelos import ruta_local
        ruta = ruta_local(self.clave)
        if ruta is None:
            raise ModeloNoDisponible(
                f"El modelo {self.info['nombre_completo']} ({self.info['tamano']}) no está descargado. "
                "Descárgalo desde Configuración › Modelo semántico o con:  python gestionar_modelos.py descargar")
        from sentence_transformers import SentenceTransformer
        argumentos = {}
        if self.info["media_precision"] and self.dispositivo == "cuda":
            import torch
            argumentos["model_kwargs"] = {"dtype": torch.float16}
        modelo = SentenceTransformer(str(ruta), device=self.dispositivo, local_files_only=True, **argumentos)
        modelo.max_seq_length = self.info["max_tokens"]
        return modelo

    def liberar(self):
        with self._candado:
            self._modelo = None
        if self.dispositivo == "cuda":
            try:
                import torch
                torch.cuda.empty_cache()
            except ImportError:
                pass

    def _codificar(self, textos, prompt=None):
        vectores = self.modelo.encode(list(textos), prompt=prompt, normalize_embeddings=True,
                                      batch_size=config.TAMANO_LOTE_EMBEDDINGS,
                                      show_progress_bar=False)
        return vectores.astype("float32").tolist()

    def embeber_documentos(self, textos) -> list[list[float]]:
        if self.info["estilo"] == "e5":
            return self._codificar([f"passage: {t}" for t in textos])
        return self._codificar(textos)

    def embeber_consulta(self, texto: str) -> list[float]:
        estilo = self.info["estilo"]
        if estilo == "e5":
            return self._codificar([f"query: {texto}"])[0]
        if estilo == "instruccion":
            return self._codificar([texto], prompt=f"Instruct: {self.instruccion}\nQuery:")[0]
        return self._codificar([texto])[0]

    def contar_tokens(self, texto: str) -> int:
        if self.info["estilo"] == "e5":
            texto = "passage: " + texto
        return len(self.modelo.tokenizer(texto)["input_ids"])

    def descripcion_dispositivo(self) -> str:
        if not self.cargado:
            return f"{self.dispositivo} (sin cargar)"
        parametro = next(self._modelo.parameters())
        return f"{parametro.device} · {str(parametro.dtype).replace('torch.', '')}"
