"""Catálogo de libros en Redis: identificadores, metadatos y disponibilidad.

Llaves (bajo el prefijo configurado):
  libros                       SET      ids de todos los libros
  libro:{id}                   HASH     metadatos del libro (sin sinopsis)
  idx:isbn:{isbn_normalizado}  STRING   id del libro que usa ese ISBN
"""
import redis

from db_redis import Llaves, marca_tiempo
from validaciones import CAMPOS_METADATOS_LIBRO, clave_natural, normalizar_isbn

CAMPOS_ENTEROS = {"anio", "paginas"}
CAMPOS_REALES = {"calificacion"}
CAMPOS_BOOLEANOS = {"disponible"}


def _a_redis(valor):
    if isinstance(valor, bool):
        return "1" if valor else "0"
    return str(valor)


def _desde_redis(crudo: dict) -> dict:
    libro = {}
    for campo, valor in crudo.items():
        if campo in CAMPOS_ENTEROS:
            libro[campo] = int(valor)
        elif campo in CAMPOS_REALES:
            libro[campo] = float(valor)
        elif campo in CAMPOS_BOOLEANOS:
            libro[campo] = valor == "1"
        else:
            libro[campo] = valor
    return libro


class CatalogoRedis:
    def __init__(self, r: redis.Redis, llaves: Llaves | None = None):
        self.r = r
        self.llaves = llaves or Llaves()

    def existe(self, libro_id: str) -> bool:
        return bool(self.r.exists(self.llaves.libro(libro_id)))

    def dueno_isbn(self, isbn: str) -> str | None:
        return self.r.get(self.llaves.idx_isbn(normalizar_isbn(isbn)))

    def obtener(self, libro_id: str) -> dict | None:
        crudo = self.r.hgetall(self.llaves.libro(libro_id))
        return _desde_redis(crudo) if crudo else None

    def obtener_varios(self, ids: list[str]) -> dict[str, dict]:
        if not ids:
            return {}
        pipe = self.r.pipeline()
        for libro_id in ids:
            pipe.hgetall(self.llaves.libro(libro_id))
        return {i: _desde_redis(c) for i, c in zip(ids, pipe.execute()) if c}

    def ids(self) -> list[str]:
        return sorted(self.r.smembers(self.llaves.libros), key=clave_natural)

    def listar(self) -> list[dict]:
        libros = self.obtener_varios(self.ids())
        return [libros[i] for i in sorted(libros, key=clave_natural)]

    def contar(self) -> int:
        return self.r.scard(self.llaves.libros)

    def guardar(self, libro: dict, nuevo: bool):
        """Escribe el libro con una transacción optimista (WATCH) sobre su ISBN e id."""
        libro_id = libro["id"]
        isbn = normalizar_isbn(libro["isbn"])
        llave_libro = self.llaves.libro(libro_id)
        llave_isbn = self.llaves.idx_isbn(isbn)
        registro = {c: _a_redis(libro[c]) for c in CAMPOS_METADATOS_LIBRO}
        registro["id"] = libro_id
        registro["fecha_actualizacion"] = marca_tiempo()

        def transaccion(pipe):
            existe = pipe.exists(llave_libro)
            if nuevo and existe:
                raise ValueError(f"Ya existe un libro con id '{libro_id}'.")
            if not nuevo and not existe:
                raise ValueError(f"No existe el libro '{libro_id}'.")
            dueno = pipe.get(llave_isbn)
            if dueno and dueno != libro_id:
                raise ValueError(f"El ISBN {libro['isbn']} ya pertenece al libro '{dueno}'.")
            isbn_anterior = None if nuevo else pipe.hget(llave_libro, "isbn")
            pipe.multi()
            if nuevo:
                registro["fecha_alta"] = registro["fecha_actualizacion"]
            pipe.hset(llave_libro, mapping=registro)
            pipe.sadd(self.llaves.libros, libro_id)
            pipe.set(llave_isbn, libro_id)
            if isbn_anterior and normalizar_isbn(isbn_anterior) != isbn:
                pipe.delete(self.llaves.idx_isbn(normalizar_isbn(isbn_anterior)))

        self.r.transaction(transaccion, llave_libro, llave_isbn)

    def guardar_lote(self, libros: list[dict]):
        """Alta masiva de libros ya validados y sin duplicados."""
        ahora = marca_tiempo()
        pipe = self.r.pipeline(transaction=True)
        for libro in libros:
            registro = {c: _a_redis(libro[c]) for c in CAMPOS_METADATOS_LIBRO}
            registro.update({"id": libro["id"], "fecha_alta": ahora, "fecha_actualizacion": ahora})
            pipe.hset(self.llaves.libro(libro["id"]), mapping=registro)
            pipe.sadd(self.llaves.libros, libro["id"])
            pipe.set(self.llaves.idx_isbn(normalizar_isbn(libro["isbn"])), libro["id"])
        pipe.execute()

    def restaurar(self, libro: dict):
        """Reescribe un libro tal como estaba (usado para compensar fallos)."""
        registro = {c: _a_redis(v) for c, v in libro.items()}
        pipe = self.r.pipeline(transaction=True)
        pipe.delete(self.llaves.libro(libro["id"]))
        pipe.hset(self.llaves.libro(libro["id"]), mapping=registro)
        pipe.sadd(self.llaves.libros, libro["id"])
        pipe.set(self.llaves.idx_isbn(normalizar_isbn(libro["isbn"])), libro["id"])
        pipe.execute()

    def eliminar(self, libro_id: str):
        libro = self.obtener(libro_id)
        if not libro:
            return
        pipe = self.r.pipeline(transaction=True)
        pipe.delete(self.llaves.libro(libro_id))
        pipe.srem(self.llaves.libros, libro_id)
        llave_isbn = self.llaves.idx_isbn(normalizar_isbn(libro.get("isbn", "")))
        pipe.delete(llave_isbn)
        pipe.execute()

    def eliminar_lote(self, ids: list[str]):
        for libro_id in ids:
            self.eliminar(libro_id)

    def contar_disponibles(self) -> int:
        pipe = self.r.pipeline()
        for libro_id in self.ids():
            pipe.hget(self.llaves.libro(libro_id), "disponible")
        return sum(1 for valor in pipe.execute() if valor == "1")
