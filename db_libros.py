"""Índice semántico de libros en ChromaDB.

  ids        -> id del libro
  documents  -> sinopsis (se convierte en embedding)
  metadatas  -> copia de los metadatos del libro para identificarlo y filtrarlo

Redis es la fuente de verdad de los metadatos; Chroma guarda una copia sincronizada.
"""
import chromadb
from chromadb.config import Settings

import config
from modelos import MODELOS, MODELO_POR_DEFECTO, ModeloEmbeddings, nombre_coleccion
from validaciones import CAMPOS_METADATOS_LIBRO


def leer_modelo_activo() -> str:
    try:
        clave = config.ARCHIVO_MODELO_ACTIVO.read_text(encoding="utf-8").strip()
        if clave in MODELOS:
            return clave
    except OSError:
        pass
    return MODELO_POR_DEFECTO


def guardar_modelo_activo(clave: str):
    config.ARCHIVO_MODELO_ACTIVO.write_text(clave, encoding="utf-8")


def metadatos_de(libro: dict) -> dict:
    return {campo: libro[campo] for campo in CAMPOS_METADATOS_LIBRO}


def _lista(valor):
    return valor.tolist() if hasattr(valor, "tolist") else list(valor)


class GestorLibros:
    def __init__(self, ruta_chroma: str = config.CHROMA_PATH, clave_modelo: str | None = None,
                 fabrica_modelo=ModeloEmbeddings, cliente=None):
        self.cliente = cliente or chromadb.PersistentClient(
            path=ruta_chroma, settings=Settings(anonymized_telemetry=False))
        self._fabrica_modelo = fabrica_modelo
        clave = clave_modelo or leer_modelo_activo()
        self.clave_modelo = clave
        self.modelo = fabrica_modelo(clave)
        self.coleccion = self._abrir_coleccion(clave)

    def _abrir_coleccion(self, clave: str):
        return self.cliente.get_or_create_collection(
            name=nombre_coleccion(clave),
            configuration={"hnsw": {"space": "cosine"}},
            metadata={"modelo": MODELOS[clave]["nombre_completo"], "dimensiones": MODELOS[clave]["dim"]},
            embedding_function=None)

    def _agregar_en_lotes(self, coleccion, modelo, libros: list[dict], progreso=None):
        lote = config.TAMANO_LOTE_EMBEDDINGS
        for inicio in range(0, len(libros), lote):
            grupo = libros[inicio:inicio + lote]
            sinopsis = [libro["sinopsis"] for libro in grupo]
            coleccion.upsert(ids=[libro["id"] for libro in grupo], documents=sinopsis,
                             metadatas=[metadatos_de(libro) for libro in grupo],
                             embeddings=modelo.embeber_documentos(sinopsis))
            if progreso:
                progreso(min(inicio + lote, len(libros)), len(libros))

    def agregar(self, libros: list[dict], progreso=None):
        self._agregar_en_lotes(self.coleccion, self.modelo, libros, progreso)

    def actualizar(self, libro: dict, recalcular_embedding: bool = True):
        if not recalcular_embedding:
            self.coleccion.update(ids=[libro["id"]], metadatas=[metadatos_de(libro)])
            return
        self.coleccion.update(ids=[libro["id"]], documents=[libro["sinopsis"]],
                              metadatas=[metadatos_de(libro)],
                              embeddings=self.modelo.embeber_documentos([libro["sinopsis"]]))

    def actualizar_metadatos(self, libro_id: str, cambios: dict):
        actual = self.coleccion.get(ids=[libro_id], include=["metadatas"])
        if not actual["ids"]:
            raise KeyError(libro_id)
        metadatos = {**actual["metadatas"][0], **cambios}
        self.coleccion.update(ids=[libro_id], metadatas=[metadatos])

    def eliminar(self, ids: list[str]):
        if ids:
            self.coleccion.delete(ids=list(ids))

    def obtener(self, libro_id: str, con_embedding: bool = False) -> dict | None:
        incluir = ["documents", "metadatas"] + (["embeddings"] if con_embedding else [])
        resultado = self.coleccion.get(ids=[libro_id], include=incluir)
        if not resultado["ids"]:
            return None
        registro = {"id": libro_id, "sinopsis": resultado["documents"][0],
                    "metadatos": resultado["metadatas"][0]}
        if con_embedding:
            registro["embedding"] = _lista(resultado["embeddings"][0])
        return registro

    def obtener_varios(self, ids: list[str]) -> dict[str, dict]:
        if not ids:
            return {}
        resultado = self.coleccion.get(ids=list(ids), include=["documents", "metadatas"])
        return {i: {"sinopsis": d, "metadatos": m}
                for i, d, m in zip(resultado["ids"], resultado["documents"], resultado["metadatas"])}

    def restaurar(self, registro: dict):
        """Reinserta un documento a partir de una copia tomada con `obtener(con_embedding=True)`."""
        argumentos = {"ids": [registro["id"]], "documents": [registro["sinopsis"]],
                      "metadatas": [registro["metadatos"]]}
        if registro.get("embedding") is not None:
            argumentos["embeddings"] = [registro["embedding"]]
        else:
            argumentos["embeddings"] = self.modelo.embeber_documentos([registro["sinopsis"]])
        self.coleccion.upsert(**argumentos)

    def ids(self) -> set[str]:
        return set(self.coleccion.get(include=[])["ids"])

    def todos(self) -> list[dict]:
        resultado = self.coleccion.get(include=["documents", "metadatas"])
        return [{"id": i, "sinopsis": d, "metadatos": m}
                for i, d, m in zip(resultado["ids"], resultado["documents"], resultado["metadatas"])]

    def contar(self) -> int:
        return self.coleccion.count()

    def buscar(self, texto: str, cantidad: int, filtro: dict | None = None) -> list[dict]:
        """Búsqueda semántica por sinopsis. Regresa id, sinopsis, metadatos y similitud."""
        total = self.contar()
        if total == 0 or not texto.strip():
            return []
        resultado = self.coleccion.query(
            query_embeddings=[self.modelo.embeber_consulta(texto)],
            n_results=min(cantidad, total), where=filtro or None,
            include=["documents", "metadatas", "distances"])
        return [{"id": i, "sinopsis": d, "metadatos": m, "similitud": round(1 - dist, 4)}
                for i, d, m, dist in zip(resultado["ids"][0], resultado["documents"][0],
                                         resultado["metadatas"][0], resultado["distances"][0])]

    def cambiar_modelo(self, nueva_clave: str, libros: list[dict], progreso=None) -> int:
        """Reindexa `libros` con otro modelo y solo conmuta si todo salió bien."""
        if nueva_clave not in MODELOS:
            raise ValueError(f"Modelo desconocido: {nueva_clave}")
        if nueva_clave == self.clave_modelo:
            return self.contar()
        nuevo_modelo = self._fabrica_modelo(nueva_clave)
        nueva_coleccion = self._abrir_coleccion(nueva_clave)
        existentes = nueva_coleccion.get(include=[])["ids"]
        if existentes:
            nueva_coleccion.delete(ids=existentes)
        try:
            self._agregar_en_lotes(nueva_coleccion, nuevo_modelo, libros, progreso)
        except Exception:
            nuevo_modelo.liberar()
            raise
        anterior = self.modelo
        self.modelo, self.coleccion, self.clave_modelo = nuevo_modelo, nueva_coleccion, nueva_clave
        guardar_modelo_activo(nueva_clave)
        if hasattr(anterior, "liberar"):
            anterior.liberar()
        return len(libros)
