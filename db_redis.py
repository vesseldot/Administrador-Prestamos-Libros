"""Conexión a Redis, espacio de nombres de llaves y registro de actividad."""
import json
from datetime import datetime

import redis

import config

VERSION_ESQUEMA = "2"


class ErrorBaseOcupada(Exception):
    """La base de Redis contiene llaves ajenas a la aplicación."""


def marca_tiempo() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Llaves:
    """Construye todas las llaves de Redis bajo un prefijo común."""

    def __init__(self, prefijo: str = config.REDIS_PREFIJO):
        self.prefijo = prefijo

    def _k(self, *partes) -> str:
        return self.prefijo + ":".join(str(p) for p in partes)

    @property
    def patron(self) -> str:
        return self.prefijo + "*"

    @property
    def esquema(self):
        return self._k("meta", "esquema")

    @property
    def libros(self):
        return self._k("libros")

    def libro(self, libro_id):
        return self._k("libro", libro_id)

    def idx_isbn(self, isbn):
        return self._k("idx", "isbn", isbn)

    def prestamo_activo_libro(self, libro_id):
        return self._k("libro", libro_id, "prestamo_activo")

    @property
    def persona_contador(self):
        return self._k("persona", "contador")

    @property
    def personas(self):
        return self._k("personas")

    def persona(self, persona_id):
        return self._k("persona", persona_id)

    def idx_correo(self, hash_correo):
        return self._k("idx", "correo", hash_correo)

    def prestamos_activos_persona(self, persona_id):
        return self._k("persona", persona_id, "prestamos_activos")

    def historial_persona(self, persona_id):
        return self._k("persona", persona_id, "historial")

    @property
    def prestamo_contador(self):
        return self._k("prestamo", "contador")

    def prestamo(self, prestamo_id):
        return self._k("prestamo", prestamo_id)

    @property
    def prestamos_activos(self):
        return self._k("prestamos", "activos")

    @property
    def prestamos_todos(self):
        return self._k("prestamos", "todos")

    @property
    def personas_con_prestamo(self):
        return self._k("personas_con_prestamo")

    @property
    def actividad(self):
        return self._k("actividad")

    @property
    def sync_pendientes(self):
        return self._k("sync", "pendientes")


def conectar_redis(host=None, port=None, db=None, password=None) -> redis.Redis:
    cliente = redis.Redis(
        host=host or config.REDIS_HOST, port=port or config.REDIS_PORT,
        db=config.REDIS_DB if db is None else db,
        password=password if password is not None else config.REDIS_PASSWORD,
        username=config.REDIS_USUARIO, ssl=config.REDIS_SSL,
        decode_responses=True, socket_connect_timeout=config.REDIS_TIMEOUT_SEGUNDOS,
        socket_timeout=config.REDIS_TIMEOUT_SEGUNDOS * 3, health_check_interval=30)
    cliente.ping()
    return cliente


def preparar_base(r: redis.Redis, llaves: Llaves):
    """Verifica que la base esté vacía o solo contenga llaves propias y marca el esquema."""
    ajenas = any(not llave.startswith(llaves.prefijo) for llave in r.scan_iter(count=1000))
    if ajenas:
        info = r.connection_pool.connection_kwargs
        raise ErrorBaseOcupada(
            f"La base {info.get('db')} de Redis contiene llaves que no pertenecen a la "
            f"aplicación (prefijo '{llaves.prefijo}'). Configura REDIS_DB con una base vacía.")
    r.setnx(llaves.esquema, VERSION_ESQUEMA)


class RegistroActividad:
    """Bitácora de eventos recientes. Solo guarda identificadores, nunca datos personales."""

    def __init__(self, r: redis.Redis, llaves: Llaves, maximo: int = config.MAX_EVENTOS_ACTIVIDAD):
        self.r = r
        self.llaves = llaves
        self.maximo = maximo

    def registrar(self, tipo: str, descripcion: str, **referencias):
        evento = {"fecha": marca_tiempo(), "tipo": tipo, "descripcion": descripcion,
                  "refs": referencias}
        try:
            pipe = self.r.pipeline()
            pipe.lpush(self.llaves.actividad, json.dumps(evento, ensure_ascii=False))
            pipe.ltrim(self.llaves.actividad, 0, self.maximo - 1)
            pipe.execute()
        except redis.RedisError:
            pass

    def recientes(self, cantidad: int = 20) -> list[dict]:
        eventos = []
        for crudo in self.r.lrange(self.llaves.actividad, 0, cantidad - 1):
            try:
                eventos.append(json.loads(crudo))
            except json.JSONDecodeError:
                continue
        return eventos
