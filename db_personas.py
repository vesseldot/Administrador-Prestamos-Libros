"""Personas en Redis, con datos personales cifrados por campo.

Llaves (bajo el prefijo configurado):
  persona:contador          STRING   generador de ids P0001, P0002…
  personas                  SET      ids de todas las personas
  persona:{id}              HASH     campos cifrados + tipo_usuario + metadatos de consentimiento
  idx:correo:{hmac}         STRING   id de la persona dueña del correo
"""
import redis

from db_redis import Llaves, RegistroActividad, marca_tiempo
from seguridad import Cifrador, ErrorCifrado
from validaciones import calcular_edad, normalizar_texto, validar_persona

CAMPOS_CIFRADOS = ["nombre", "apellido_paterno", "apellido_materno", "fecha_nacimiento",
                   "genero", "correo", "telefono", "calle_numero", "colonia", "ciudad",
                   "estado", "codigo_postal", "ocupacion"]
CAMPOS_CLAROS = ["tipo_usuario"]
CAMPOS_BUSQUEDA = ["id", "nombre_completo", "tipo_usuario", "ocupacion", "ciudad", "estado"]


class PersonaNoEncontrada(ValueError):
    pass


class GestorPersonas:
    def __init__(self, r: redis.Redis, cifrador: Cifrador | None = None,
                 llaves: Llaves | None = None, actividad: RegistroActividad | None = None):
        self.r = r
        self.cif = cifrador or Cifrador()
        self.llaves = llaves or Llaves()
        self.actividad = actividad or RegistroActividad(r, self.llaves)

    def _contexto(self, persona_id: str, campo: str) -> str:
        return f"persona:{persona_id}:{campo}"

    def _registro_cifrado(self, persona_id: str, datos: dict) -> dict:
        registro = {c: self.cif.cifrar(datos[c], self._contexto(persona_id, c))
                    for c in CAMPOS_CIFRADOS}
        registro.update({c: datos[c] for c in CAMPOS_CLAROS})
        return registro

    @staticmethod
    def _validar(datos: dict) -> dict:
        limpio, errores = validar_persona(datos)
        if errores:
            raise ValueError("\n".join(errores))
        return limpio

    def existe(self, persona_id: str) -> bool:
        return bool(self.r.exists(self.llaves.persona(persona_id)))

    def registrar(self, datos: dict) -> str:
        limpio = self._validar(datos)
        hash_correo = self.cif.hash_indice(limpio["correo"])
        llave_indice = self.llaves.idx_correo(hash_correo)
        if self.r.exists(llave_indice):
            raise ValueError("Ese correo ya está registrado.")
        persona_id = f"P{self.r.incr(self.llaves.persona_contador):04d}"
        if not self.r.set(llave_indice, persona_id, nx=True):
            raise ValueError("Ese correo ya está registrado.")
        ahora = marca_tiempo()
        registro = self._registro_cifrado(persona_id, limpio)
        registro.update({"id": persona_id, "correo_hash": hash_correo,
                         "acepta_aviso_privacidad": "1", "fecha_aviso": ahora,
                         "fecha_registro": ahora, "fecha_actualizacion": ahora})
        try:
            pipe = self.r.pipeline()
            pipe.hset(self.llaves.persona(persona_id), mapping=registro)
            pipe.sadd(self.llaves.personas, persona_id)
            pipe.execute()
        except redis.RedisError:
            self.r.delete(llave_indice)
            raise
        self.actividad.registrar("persona_alta", f"Alta de la persona {persona_id}",
                                 persona=persona_id)
        return persona_id

    def actualizar(self, persona_id: str, datos: dict):
        llave = self.llaves.persona(persona_id)
        if not self.r.exists(llave):
            raise PersonaNoEncontrada(f"No existe la persona {persona_id}.")
        limpio = self._validar(datos)
        hash_nuevo = self.cif.hash_indice(limpio["correo"])
        hash_anterior = self.r.hget(llave, "correo_hash")
        if hash_nuevo != hash_anterior:
            if not self.r.set(self.llaves.idx_correo(hash_nuevo), persona_id, nx=True):
                raise ValueError("Ese correo ya está registrado con otra persona.")
        registro = self._registro_cifrado(persona_id, limpio)
        registro.update({"correo_hash": hash_nuevo, "acepta_aviso_privacidad": "1",
                         "fecha_actualizacion": marca_tiempo()})
        pipe = self.r.pipeline()
        pipe.hset(llave, mapping=registro)
        pipe.hsetnx(llave, "fecha_aviso", registro["fecha_actualizacion"])
        if hash_anterior and hash_anterior != hash_nuevo:
            pipe.delete(self.llaves.idx_correo(hash_anterior))
        pipe.execute()
        self.actividad.registrar("persona_actualizada",
                                 f"Rectificación de datos de {persona_id}", persona=persona_id)

    def _descifrar(self, persona_id: str, crudo: dict) -> dict:
        persona = {"id": persona_id, "integridad_ok": True, "cifrado_heredado": False}
        for campo in CAMPOS_CIFRADOS:
            token = crudo.get(campo, "")
            try:
                persona[campo] = self.cif.descifrar(token, self._contexto(persona_id, campo))
                persona["cifrado_heredado"] |= self.cif.es_heredado(token)
            except ErrorCifrado:
                persona[campo] = ""
                persona["integridad_ok"] = False
        for campo in CAMPOS_CLAROS:
            persona[campo] = crudo.get(campo, "")
        persona["acepta_aviso_privacidad"] = crudo.get("acepta_aviso_privacidad") == "1"
        for campo in ("fecha_aviso", "fecha_registro", "fecha_actualizacion"):
            persona[campo] = crudo.get(campo, "")
        try:
            persona["edad"] = calcular_edad(persona["fecha_nacimiento"])
        except ValueError:
            persona["edad"] = ""
        persona["nombre_completo"] = " ".join(
            x for x in (persona["nombre"], persona["apellido_paterno"],
                        persona["apellido_materno"]) if x) or "(datos ilegibles)"
        persona["num_prestamos"] = 0
        return persona

    def obtener(self, persona_id: str) -> dict | None:
        crudo = self.r.hgetall(self.llaves.persona(persona_id))
        if not crudo:
            return None
        persona = self._descifrar(persona_id, crudo)
        persona["num_prestamos"] = self.r.scard(self.llaves.prestamos_activos_persona(persona_id))
        return persona

    def ids(self) -> list[str]:
        return sorted(self.r.smembers(self.llaves.personas))

    def contar(self) -> int:
        return self.r.scard(self.llaves.personas)

    def listar(self, ids: list[str] | None = None, solo_con_prestamos: bool = False) -> list[dict]:
        if ids is None:
            origen = self.llaves.personas_con_prestamo if solo_con_prestamos else self.llaves.personas
            ids = sorted(self.r.smembers(origen))
        if not ids:
            return []
        pipe = self.r.pipeline()
        for persona_id in ids:
            pipe.hgetall(self.llaves.persona(persona_id))
            pipe.scard(self.llaves.prestamos_activos_persona(persona_id))
        resultados = pipe.execute()
        personas = []
        for persona_id, crudo, activos in zip(ids, resultados[::2], resultados[1::2]):
            if crudo:
                persona = self._descifrar(persona_id, crudo)
                persona["num_prestamos"] = activos
                personas.append(persona)
        return personas

    def buscar(self, texto: str, tipo_usuario: str | None = None,
               solo_con_prestamos: bool = False) -> list[dict]:
        """Busca por id, nombre, apellidos, tipo de usuario, ocupación, ciudad o estado."""
        consulta = normalizar_texto(texto)
        personas = self.listar(solo_con_prestamos=solo_con_prestamos)
        resultado = []
        for persona in personas:
            if tipo_usuario and persona["tipo_usuario"] != tipo_usuario:
                continue
            if consulta:
                campos = " ".join(normalizar_texto(persona.get(c, "")) for c in CAMPOS_BUSQUEDA)
                if not all(palabra in campos for palabra in consulta.split()):
                    continue
            resultado.append(persona)
        return resultado

    def eliminar(self, persona_id: str):
        """Derecho ARCO de cancelación: elimina los datos personales.

        El historial de préstamos se conserva solo con el identificador.
        """
        llave = self.llaves.persona(persona_id)
        if not self.r.exists(llave):
            raise PersonaNoEncontrada(f"No existe la persona {persona_id}.")
        if self.r.scard(self.llaves.prestamos_activos_persona(persona_id)):
            raise ValueError("No se puede eliminar: la persona tiene libros prestados.")
        hash_correo = self.r.hget(llave, "correo_hash")
        pipe = self.r.pipeline()
        pipe.delete(llave)
        if hash_correo:
            pipe.delete(self.llaves.idx_correo(hash_correo))
        pipe.srem(self.llaves.personas, persona_id)
        pipe.srem(self.llaves.personas_con_prestamo, persona_id)
        pipe.execute()
        self.actividad.registrar("persona_eliminada",
                                 f"Cancelación de datos de {persona_id}", persona=persona_id)

    def migrar_cifrado_heredado(self) -> int:
        """Vuelve a cifrar con AES-256-GCM los registros que aún usan Fernet."""
        migradas = 0
        for persona in self.listar():
            if persona["cifrado_heredado"] and persona["integridad_ok"]:
                registro = self._registro_cifrado(persona["id"], persona)
                self.r.hset(self.llaves.persona(persona["id"]), mapping=registro)
                migradas += 1
        return migradas

    def exportar_datos(self, persona_id: str, prestamos: list[dict]) -> dict:
        """Derecho ARCO de acceso: datos de la persona en un formato portable."""
        persona = self.obtener(persona_id)
        if not persona:
            raise PersonaNoEncontrada(f"No existe la persona {persona_id}.")
        datos = {c: persona[c] for c in ["id"] + CAMPOS_CIFRADOS + CAMPOS_CLAROS}
        datos.update({"edad": persona["edad"],
                      "acepta_aviso_privacidad": persona["acepta_aviso_privacidad"],
                      "fecha_aviso": persona["fecha_aviso"],
                      "fecha_registro": persona["fecha_registro"],
                      "fecha_actualizacion": persona["fecha_actualizacion"],
                      "prestamos": prestamos, "exportado": marca_tiempo()})
        return datos
