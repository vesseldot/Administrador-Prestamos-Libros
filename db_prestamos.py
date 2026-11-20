"""Préstamos y devoluciones en Redis, con historial permanente.

Llaves (bajo el prefijo configurado):
  prestamo:contador                    STRING  generador de ids PR000001…
  prestamo:{id}                        HASH    persona_id, libro_id, titulo, autor, fechas, estado
  libro:{id}:prestamo_activo           STRING  id del préstamo activo de ese libro (uno como máximo)
  persona:{id}:prestamos_activos       SET     préstamos activos de la persona
  persona:{id}:historial               ZSET    todos los préstamos de la persona (por fecha)
  prestamos:activos                    SET     préstamos activos de toda la biblioteca
  prestamos:todos                      ZSET    todos los préstamos (por fecha)
  personas_con_prestamo                SET     personas con al menos un préstamo activo

Préstamo y devolución usan transacciones optimistas (WATCH/MULTI/EXEC): o se
aplican todos los cambios o ninguno.
"""
from datetime import date, datetime, timedelta

import redis

import config
from db_redis import Llaves, RegistroActividad

ESTADO_ACTIVO = "activo"
ESTADO_DEVUELTO = "devuelto"


class GestorPrestamos:
    def __init__(self, r: redis.Redis, llaves: Llaves | None = None,
                 actividad: RegistroActividad | None = None,
                 maximo_por_persona: int = config.MAX_LIBROS_POR_PERSONA,
                 dias_prestamo: int = config.DIAS_PRESTAMO):
        self.r = r
        self.llaves = llaves or Llaves()
        self.actividad = actividad or RegistroActividad(r, self.llaves)
        self.maximo = maximo_por_persona
        self.dias = dias_prestamo

    @staticmethod
    def _enriquecer(registro: dict) -> dict:
        prestamo = dict(registro)
        vencido = (prestamo.get("estado") == ESTADO_ACTIVO and prestamo.get("fecha_limite", "")
                   and prestamo["fecha_limite"] < date.today().isoformat())
        prestamo["vencido"] = bool(vencido)
        if prestamo.get("estado") == ESTADO_DEVUELTO:
            prestamo["estado_visible"] = "Devuelto"
        else:
            prestamo["estado_visible"] = "Vencido" if vencido else "Activo"
        return prestamo

    def prestar(self, persona_id: str, libro_ids: list[str]) -> list[dict]:
        """Presta uno o varios libros a una persona en una sola operación atómica."""
        ids = list(dict.fromkeys(i for i in libro_ids if i))
        if not ids:
            raise ValueError("Selecciona al menos un libro.")
        if len(ids) > self.maximo:
            raise ValueError(f"Solo se pueden prestar {self.maximo} libros a la vez.")

        llave_persona = self.llaves.persona(persona_id)
        llave_activos = self.llaves.prestamos_activos_persona(persona_id)
        vigiladas = [llave_persona, llave_activos]
        vigiladas += [self.llaves.libro(i) for i in ids]
        vigiladas += [self.llaves.prestamo_activo_libro(i) for i in ids]

        ahora = datetime.now()
        fecha = ahora.isoformat(timespec="seconds")
        limite = (ahora + timedelta(days=self.dias)).date().isoformat()
        puntaje = ahora.timestamp()
        creados: list[dict] = []

        def transaccion(pipe):
            creados.clear()
            if not pipe.exists(llave_persona):
                raise ValueError("La persona no existe.")
            actuales = pipe.scard(llave_activos)
            if actuales + len(ids) > self.maximo:
                raise ValueError(f"La persona ya tiene {actuales} libro(s). Solo puede tener "
                                 f"{self.maximo} a la vez (le quedan {self.maximo - actuales}).")
            libros = []
            for libro_id in ids:
                libro = pipe.hgetall(self.llaves.libro(libro_id))
                if not libro:
                    raise ValueError(f"El libro {libro_id} no existe.")
                if pipe.exists(self.llaves.prestamo_activo_libro(libro_id)) \
                        or libro.get("disponible") != "1":
                    raise ValueError(f"El libro «{libro.get('titulo', libro_id)}» no está disponible.")
                libros.append(libro)
            primero = int(pipe.get(self.llaves.prestamo_contador) or 0) + 1
            pipe.multi()
            pipe.incrby(self.llaves.prestamo_contador, len(libros))
            for numero, libro in enumerate(libros, start=primero):
                prestamo_id = f"PR{numero:06d}"
                registro = {"id": prestamo_id, "persona_id": persona_id, "libro_id": libro["id"],
                            "titulo": libro.get("titulo", ""), "autor": libro.get("autor", ""),
                            "fecha_prestamo": fecha, "fecha_limite": limite,
                            "fecha_devolucion": "", "estado": ESTADO_ACTIVO}
                pipe.hset(self.llaves.prestamo(prestamo_id), mapping=registro)
                pipe.set(self.llaves.prestamo_activo_libro(libro["id"]), prestamo_id)
                pipe.hset(self.llaves.libro(libro["id"]), "disponible", "0")
                pipe.sadd(llave_activos, prestamo_id)
                pipe.zadd(self.llaves.historial_persona(persona_id), {prestamo_id: puntaje})
                pipe.sadd(self.llaves.prestamos_activos, prestamo_id)
                pipe.zadd(self.llaves.prestamos_todos, {prestamo_id: puntaje})
                creados.append(registro)
            pipe.sadd(self.llaves.personas_con_prestamo, persona_id)

        self.r.transaction(transaccion, *vigiladas, self.llaves.prestamo_contador)
        self.actividad.registrar("prestamo", f"Préstamo de {len(creados)} libro(s) a {persona_id}",
                                 persona=persona_id, libros=ids)
        return [self._enriquecer(c) for c in creados]

    def devolver(self, persona_id: str, prestamo_ids: list[str] | None = None) -> list[dict]:
        """Devuelve los préstamos indicados, o todos los activos de la persona si es None."""
        llave_activos = self.llaves.prestamos_activos_persona(persona_id)
        actuales = self.r.smembers(llave_activos)
        objetivo = set(actuales) if prestamo_ids is None else set(prestamo_ids)
        if not objetivo:
            raise ValueError("Selecciona al menos un libro para devolver.")
        ajenos = objetivo - actuales
        if ajenos:
            raise ValueError("Alguno de los préstamos seleccionados no está activo para esta persona.")

        fecha = datetime.now().isoformat(timespec="seconds")
        vigiladas = [llave_activos] + [self.llaves.prestamo(p) for p in objetivo]
        devueltos: list[dict] = []

        def transaccion(pipe):
            devueltos.clear()
            activos = pipe.smembers(llave_activos)
            if not objetivo <= activos:
                raise ValueError("Alguno de los préstamos ya fue devuelto.")
            registros = []
            for prestamo_id in sorted(objetivo):
                registro = pipe.hgetall(self.llaves.prestamo(prestamo_id))
                existe_libro = pipe.exists(self.llaves.libro(registro.get("libro_id", "")))
                registros.append((prestamo_id, registro, existe_libro))
            pipe.multi()
            for prestamo_id, registro, existe_libro in registros:
                pipe.hset(self.llaves.prestamo(prestamo_id),
                          mapping={"estado": ESTADO_DEVUELTO, "fecha_devolucion": fecha})
                libro_id = registro.get("libro_id", "")
                pipe.delete(self.llaves.prestamo_activo_libro(libro_id))
                if existe_libro:
                    pipe.hset(self.llaves.libro(libro_id), "disponible", "1")
                pipe.srem(llave_activos, prestamo_id)
                pipe.srem(self.llaves.prestamos_activos, prestamo_id)
                devueltos.append({**registro, "estado": ESTADO_DEVUELTO, "fecha_devolucion": fecha})
            if len(activos) == len(objetivo):
                pipe.srem(self.llaves.personas_con_prestamo, persona_id)

        self.r.transaction(transaccion, *vigiladas)
        self.actividad.registrar("devolucion", f"Devolución de {len(devueltos)} libro(s) de {persona_id}",
                                 persona=persona_id, libros=[d["libro_id"] for d in devueltos])
        return [self._enriquecer(d) for d in devueltos]

    def _obtener_varios(self, prestamo_ids) -> list[dict]:
        ids = list(prestamo_ids)
        if not ids:
            return []
        pipe = self.r.pipeline()
        for prestamo_id in ids:
            pipe.hgetall(self.llaves.prestamo(prestamo_id))
        return [self._enriquecer(r) for r in pipe.execute() if r]

    def obtener(self, prestamo_id: str) -> dict | None:
        registro = self.r.hgetall(self.llaves.prestamo(prestamo_id))
        return self._enriquecer(registro) if registro else None

    def activos_de(self, persona_id: str) -> list[dict]:
        prestamos = self._obtener_varios(self.r.smembers(self.llaves.prestamos_activos_persona(persona_id)))
        return sorted(prestamos, key=lambda p: (p["fecha_prestamo"], p["id"]))

    def historial_de(self, persona_id: str) -> list[dict]:
        return self._obtener_varios(self.r.zrevrange(self.llaves.historial_persona(persona_id), 0, -1))

    def activo_de_libro(self, libro_id: str) -> dict | None:
        prestamo_id = self.r.get(self.llaves.prestamo_activo_libro(libro_id))
        return self.obtener(prestamo_id) if prestamo_id else None

    def activos(self) -> list[dict]:
        prestamos = self._obtener_varios(self.r.smembers(self.llaves.prestamos_activos))
        return sorted(prestamos, key=lambda p: (p["persona_id"], p["fecha_prestamo"], p["id"]))

    def recientes(self, cantidad: int = 20) -> list[dict]:
        return self._obtener_varios(self.r.zrevrange(self.llaves.prestamos_todos, 0, cantidad - 1))

    def contar_activos(self) -> int:
        return self.r.scard(self.llaves.prestamos_activos)

    def contar_total(self) -> int:
        return self.r.zcard(self.llaves.prestamos_todos)

    def personas_con_prestamo(self) -> list[str]:
        return sorted(self.r.smembers(self.llaves.personas_con_prestamo))

    def cupo_disponible(self, persona_id: str) -> int:
        return self.maximo - self.r.scard(self.llaves.prestamos_activos_persona(persona_id))
