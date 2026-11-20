"""Coordinación entre Redis (fuente de verdad) y ChromaDB (índice semántico).

No existe una transacción distribuida entre ambas bases, así que cada operación
sigue el patrón: validar → escribir en Chroma → confirmar en Redis, y ante un
fallo compensa el paso anterior con una copia previa. Si la compensación también
falla, el libro queda en `sync:pendientes` para repararse desde Configuración.

`ServicioBiblioteca` es el ÚNICO punto de entrada que usa la interfaz gráfica.
Los métodos de la sección «API para la interfaz» son el contrato con el frontend
(ver INTEGRACION.md); los atributos internos (`r`, `catalogo`, `indice`,
`personas`, `prestamos`, `actividad`, `llaves`) no deben usarse desde `ui/`.
"""
import csv
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import redis

import config
from db_catalogo import CatalogoRedis
from db_libros import GestorLibros, metadatos_de
from db_personas import GestorPersonas
from db_prestamos import GestorPrestamos
from db_redis import Llaves, RegistroActividad, conectar_redis, preparar_base
from modelos import MODELOS, ModeloEmbeddings, ModeloNoDisponible
from seguridad import Cifrador, ControlAcceso, ErrorCifrado, ErrorLlave, cargar_llave_legada
from validaciones import CAMPOS_METADATOS_LIBRO, normalizar_isbn, normalizar_texto, validar_libro

log = logging.getLogger("biblioteca")


@dataclass
class ResultadoLote:
    total: int = 0
    agregados: list[str] = field(default_factory=list)
    rechazados: list[dict] = field(default_factory=list)


@dataclass
class InformeSincronizacion:
    faltan_en_chroma: list[str] = field(default_factory=list)
    huerfanos_en_chroma: list[str] = field(default_factory=list)
    metadatos_distintos: list[str] = field(default_factory=list)
    pendientes: list[str] = field(default_factory=list)

    @property
    def consistente(self) -> bool:
        return not (self.faltan_en_chroma or self.huerfanos_en_chroma
                    or self.metadatos_distintos or self.pendientes)


def leer_archivo_libros(ruta: str | Path) -> list[dict]:
    """Lee libros desde CSV (coma o punto y coma, UTF-8 con o sin BOM) o JSON."""
    ruta = Path(ruta)
    if ruta.suffix.lower() == ".json":
        with ruta.open(encoding="utf-8") as archivo:
            datos = json.load(archivo)
        if isinstance(datos, dict):
            datos = datos.get("libros", [])
        if not isinstance(datos, list):
            raise ValueError("El JSON debe ser una lista de libros o un objeto con la clave 'libros'.")
        return [d for d in datos if isinstance(d, dict)]
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        muestra = archivo.read(4096)
        archivo.seek(0)
        delimitador = ";" if muestra.count(";") > muestra.count(",") else ","
        return list(csv.DictReader(archivo, delimiter=delimitador))


def _iguales(a, b) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) < 1e-6
        except (TypeError, ValueError):
            return False
    return a == b


class ServicioBiblioteca:
    def __init__(self, r: redis.Redis, llaves: Llaves, catalogo: CatalogoRedis,
                 indice: GestorLibros, personas: GestorPersonas, prestamos: GestorPrestamos,
                 actividad: RegistroActividad, acceso: ControlAcceso | None = None):
        self.r = r
        self.llaves = llaves
        self.catalogo = catalogo
        self.indice = indice
        self.personas = personas
        self.prestamos = prestamos
        self.actividad = actividad
        self.acceso = acceso or ControlAcceso()

    @classmethod
    def crear(cls, r: redis.Redis | None = None, indice: GestorLibros | None = None,
              cifrador: Cifrador | None = None, llaves: Llaves | None = None,
              acceso: ControlAcceso | None = None):
        r = r or conectar_redis()
        llaves = llaves or Llaves()
        preparar_base(r, llaves)
        actividad = RegistroActividad(r, llaves)
        cifrador = cifrador or Cifrador(llave_legada=cargar_llave_legada())
        return cls(r, llaves, CatalogoRedis(r, llaves), indice or GestorLibros(),
                   GestorPersonas(r, cifrador, llaves, actividad),
                   GestorPrestamos(r, llaves, actividad), actividad, acceso)

    def _marcar_pendiente(self, libro_id: str):
        try:
            self.r.sadd(self.llaves.sync_pendientes, libro_id)
        except redis.RedisError:
            log.error("No se pudo registrar la sincronización pendiente de %s", libro_id)

    @staticmethod
    def _validar(datos: dict) -> dict:
        limpio, errores = validar_libro(datos)
        if errores:
            raise ValueError("\n".join(errores))
        return limpio

    def _comprobar_unicidad(self, libro: dict):
        if self.catalogo.existe(libro["id"]):
            raise ValueError(f"Ya existe un libro con id '{libro['id']}'.")
        dueno = self.catalogo.dueno_isbn(libro["isbn"])
        if dueno:
            raise ValueError(f"El ISBN {libro['isbn']} ya pertenece al libro '{dueno}'.")

    def validar_alta(self, datos: dict) -> dict:
        limpio = self._validar(datos)
        self._comprobar_unicidad(limpio)
        return limpio

    def alta_libro(self, datos: dict) -> str:
        libro = self.validar_alta(datos)
        self.indice.agregar([libro])
        try:
            self.catalogo.guardar(libro, nuevo=True)
        except Exception:
            try:
                self.indice.eliminar([libro["id"]])
            except Exception:
                self._marcar_pendiente(libro["id"])
            raise
        self.actividad.registrar("libro_alta", f"Alta del libro «{libro['titulo']}»", libro=libro["id"])
        return libro["id"]

    def importar_lote(self, registros: list[dict], progreso=None) -> ResultadoLote:
        resultado = ResultadoLote(total=len(registros))
        validos, ids_vistos, isbn_vistos = [], set(), set()
        for fila, datos in enumerate(registros, start=1):
            limpio, errores = validar_libro(datos)
            identificador = limpio.get("id") or "(sin id)"
            if not errores:
                isbn = normalizar_isbn(limpio["isbn"])
                if limpio["id"] in ids_vistos:
                    errores.append("id repetido dentro del archivo")
                elif self.catalogo.existe(limpio["id"]):
                    errores.append("ya existe un libro con ese id")
                if isbn in isbn_vistos:
                    errores.append("ISBN repetido dentro del archivo")
                elif self.catalogo.dueno_isbn(isbn):
                    errores.append(f"el ISBN ya pertenece al libro '{self.catalogo.dueno_isbn(isbn)}'")
            if errores:
                resultado.rechazados.append({"fila": fila, "id": identificador, "motivos": errores})
                continue
            ids_vistos.add(limpio["id"])
            isbn_vistos.add(normalizar_isbn(limpio["isbn"]))
            validos.append(limpio)

        if validos:
            ids = [libro["id"] for libro in validos]
            self.indice.agregar(validos, progreso)
            try:
                self.catalogo.guardar_lote(validos)
            except Exception:
                try:
                    self.indice.eliminar(ids)
                except Exception:
                    for libro_id in ids:
                        self._marcar_pendiente(libro_id)
                raise
            resultado.agregados = ids
            self.actividad.registrar("lote_importado", f"Importación por lote: {len(ids)} libro(s)",
                                     cantidad=len(ids), rechazados=len(resultado.rechazados))
        return resultado

    def importar_archivo(self, ruta: str | Path, progreso=None) -> ResultadoLote:
        return self.importar_lote(leer_archivo_libros(ruta), progreso)

    def actualizar_libro(self, libro_id: str, datos: dict):
        if not self.catalogo.existe(libro_id):
            raise ValueError(f"No existe el libro '{libro_id}'.")
        datos = {**datos, "id": libro_id}
        if self.prestamos.activo_de_libro(libro_id):
            datos["disponible"] = False
        libro = self._validar(datos)
        dueno = self.catalogo.dueno_isbn(libro["isbn"])
        if dueno and dueno != libro_id:
            raise ValueError(f"El ISBN {libro['isbn']} ya pertenece al libro '{dueno}'.")

        copia = self.indice.obtener(libro_id, con_embedding=True)
        if copia is None:
            self.indice.agregar([libro])
        else:
            self.indice.actualizar(libro, recalcular_embedding=copia["sinopsis"] != libro["sinopsis"])
        try:
            self.catalogo.guardar(libro, nuevo=False)
        except Exception:
            try:
                if copia:
                    self.indice.restaurar(copia)
                else:
                    self.indice.eliminar([libro_id])
            except Exception:
                self._marcar_pendiente(libro_id)
            raise
        self.actividad.registrar("libro_actualizado", f"Actualización de «{libro['titulo']}»",
                                 libro=libro_id)

    def eliminar_libro(self, libro_id: str):
        libro = self.catalogo.obtener(libro_id)
        if not libro:
            raise ValueError(f"No existe el libro '{libro_id}'.")
        prestamo = self.prestamos.activo_de_libro(libro_id)
        if prestamo:
            raise ValueError(f"El libro está prestado a {prestamo['persona_id']}. "
                             "Primero registra la devolución.")
        copia = self.indice.obtener(libro_id, con_embedding=True)
        self.indice.eliminar([libro_id])
        try:
            self.catalogo.eliminar(libro_id)
        except Exception:
            try:
                if copia:
                    self.indice.restaurar(copia)
            except Exception:
                self._marcar_pendiente(libro_id)
            raise
        self.r.srem(self.llaves.sync_pendientes, libro_id)
        self.actividad.registrar("libro_eliminado", f"Eliminación de «{libro['titulo']}»",
                                 libro=libro_id)

    def _estado_libro(self, libro: dict, prestados: dict[str, str]) -> str:
        if libro["id"] in prestados:
            return "Prestado"
        return "Disponible" if libro.get("disponible") else "No disponible"

    def _prestados(self) -> dict[str, str]:
        return {p["libro_id"]: p["persona_id"] for p in self.prestamos.activos()}

    def catalogo_libros(self) -> list[dict]:
        prestados = self._prestados()
        libros = self.catalogo.listar()
        for libro in libros:
            libro["estado"] = self._estado_libro(libro, prestados)
            libro["prestado_a"] = prestados.get(libro["id"], "")
        return libros

    def obtener_libro(self, libro_id: str) -> dict | None:
        libro = self.catalogo.obtener(libro_id)
        if not libro:
            return None
        documento = self.indice.obtener(libro_id)
        libro["sinopsis"] = documento["sinopsis"] if documento else ""
        libro["indexado"] = documento is not None
        prestamo = self.prestamos.activo_de_libro(libro_id)
        libro["prestamo"] = prestamo
        libro["estado"] = "Prestado" if prestamo else ("Disponible" if libro["disponible"] else "No disponible")
        return libro

    def buscar_libros(self, texto: str, cantidad: int, solo_disponibles: bool = False) -> list[dict]:
        if not texto.strip():
            return []
        candidatos = self.indice.buscar(texto, cantidad * 3 if solo_disponibles else cantidad)
        libros = self.catalogo.obtener_varios([c["id"] for c in candidatos])
        prestados = self._prestados()
        resultado = []
        for candidato in candidatos:
            libro = libros.get(candidato["id"])
            if not libro:
                continue
            libro = {**libro, "sinopsis": candidato["sinopsis"], "similitud": candidato["similitud"]}
            libro["estado"] = self._estado_libro(libro, prestados)
            if solo_disponibles and libro["estado"] != "Disponible":
                continue
            resultado.append(libro)
            if len(resultado) >= cantidad:
                break
        return resultado

    def filtrar_catalogo(self, libros: list[dict], texto: str = "", genero: str = "",
                         idioma: str = "", estado: str = "") -> list[dict]:
        consulta = normalizar_texto(texto)
        filtrados = []
        for libro in libros:
            if genero and libro.get("genero") != genero:
                continue
            if idioma and libro.get("idioma") != idioma:
                continue
            if estado and libro.get("estado") != estado:
                continue
            if consulta:
                campos = normalizar_texto(" ".join(str(libro.get(c, "")) for c in
                                                   ("id", "titulo", "autor", "isbn", "editorial", "tema")))
                if not all(p in campos for p in consulta.split()):
                    continue
            filtrados.append(libro)
        return filtrados

    def _sincronizar_disponibilidad(self, libro_ids: list[str], disponible: bool):
        for libro_id in libro_ids:
            try:
                self.indice.actualizar_metadatos(libro_id, {"disponible": disponible})
            except Exception:
                log.warning("Disponibilidad de %s pendiente de sincronizar en Chroma", libro_id)
                self._marcar_pendiente(libro_id)

    def prestar(self, persona_id: str, libro_ids: list[str]) -> list[dict]:
        prestamos = self.prestamos.prestar(persona_id, libro_ids)
        self._sincronizar_disponibilidad([p["libro_id"] for p in prestamos], False)
        return prestamos

    def devolver(self, persona_id: str, prestamo_ids: list[str] | None = None) -> list[dict]:
        devueltos = self.prestamos.devolver(persona_id, prestamo_ids)
        ids = [d["libro_id"] for d in devueltos if self.catalogo.existe(d["libro_id"])]
        self._sincronizar_disponibilidad(ids, True)
        return devueltos

    def personas_con_prestamos(self) -> list[dict]:
        prestamos_por_persona: dict[str, list[dict]] = {}
        for prestamo in self.prestamos.activos():
            prestamos_por_persona.setdefault(prestamo["persona_id"], []).append(prestamo)
        personas = self.personas.listar(ids=sorted(prestamos_por_persona))
        for persona in personas:
            persona["prestamos"] = prestamos_por_persona.get(persona["id"], [])
        return personas

    def eliminar_persona(self, persona_id: str):
        self.personas.eliminar(persona_id)

    def exportar_persona(self, persona_id: str) -> dict:
        return self.personas.exportar_datos(persona_id, self.prestamos.historial_de(persona_id))

    def estadisticas(self) -> dict:
        total = self.catalogo.contar()
        disponibles = self.catalogo.contar_disponibles()
        activos = self.prestamos.activos()
        return {
            "libros": total,
            "disponibles": disponibles,
            "prestados": len(activos),
            "no_disponibles": max(total - disponibles - len(activos), 0),
            "personas": self.personas.contar(),
            "prestamos_activos": len(activos),
            "prestamos_vencidos": sum(1 for p in activos if p["vencido"]),
            "prestamos_historicos": self.prestamos.contar_total(),
            "personas_con_prestamo": len(self.prestamos.personas_con_prestamo()),
            "sync_pendientes": self.r.scard(self.llaves.sync_pendientes),
            "documentos_indice": self.indice.contar(),
        }

    def revisar_sincronizacion(self) -> InformeSincronizacion:
        ids_redis = set(self.catalogo.ids())
        documentos = {d["id"]: d for d in self.indice.todos()}
        informe = InformeSincronizacion(
            faltan_en_chroma=sorted(ids_redis - set(documentos)),
            huerfanos_en_chroma=sorted(set(documentos) - ids_redis),
            pendientes=sorted(self.r.smembers(self.llaves.sync_pendientes)))
        libros = self.catalogo.obtener_varios(sorted(ids_redis & set(documentos)))
        for libro_id, libro in libros.items():
            metadatos = documentos[libro_id]["metadatos"]
            if any(not _iguales(libro.get(c), metadatos.get(c)) for c in CAMPOS_METADATOS_LIBRO):
                informe.metadatos_distintos.append(libro_id)
        informe.metadatos_distintos.sort()
        return informe

    def reparar_sincronizacion(self, progreso=None) -> dict:
        """Copia a Chroma los metadatos de Redis y elimina pendientes resueltos.

        Los libros de Redis sin documento en Chroma no pueden reindexarse porque la
        sinopsis solo vive en Chroma; se informan para darlos de alta de nuevo.
        Los documentos huérfanos de Chroma no se borran: se importan con
        `importar_huerfanos` o se dejan para revisión.
        """
        informe = self.revisar_sincronizacion()
        corregidos = 0
        por_revisar = sorted(set(informe.metadatos_distintos) | (set(informe.pendientes)
                                                               - set(informe.faltan_en_chroma)
                                                               - set(informe.huerfanos_en_chroma)))
        libros = self.catalogo.obtener_varios(por_revisar)
        for libro_id in por_revisar:
            libro = libros.get(libro_id)
            if libro is None:
                if libro_id not in self.indice.ids():
                    self.r.srem(self.llaves.sync_pendientes, libro_id)
                continue
            self.indice.actualizar_metadatos(libro_id, metadatos_de(libro))
            self.r.srem(self.llaves.sync_pendientes, libro_id)
            corregidos += 1
        return {"corregidos": corregidos, "sin_sinopsis": informe.faltan_en_chroma,
                "huerfanos": informe.huerfanos_en_chroma}

    def importar_huerfanos(self) -> ResultadoLote:
        """Da de alta en Redis los documentos que solo existen en Chroma (migración)."""
        huerfanos = set(self.revisar_sincronizacion().huerfanos_en_chroma)
        resultado = ResultadoLote(total=len(huerfanos))
        for documento in self.indice.todos():
            if documento["id"] not in huerfanos:
                continue
            datos = {"id": documento["id"], "sinopsis": documento["sinopsis"], **documento["metadatos"]}
            limpio, errores = validar_libro(datos)
            if not errores and self.catalogo.dueno_isbn(limpio["isbn"]):
                errores.append("ISBN ya registrado en otro libro")
            if errores:
                resultado.rechazados.append({"fila": 0, "id": documento["id"], "motivos": errores})
                continue
            self.catalogo.guardar(limpio, nuevo=True)
            resultado.agregados.append(limpio["id"])
        if resultado.agregados:
            self.actividad.registrar("migracion", f"Importados {len(resultado.agregados)} libro(s) desde Chroma",
                                     cantidad=len(resultado.agregados))
        return resultado

    def cambiar_modelo(self, clave: str, progreso=None) -> int:
        libros = self.catalogo.listar()
        documentos = self.indice.obtener_varios([l["id"] for l in libros])
        sin_sinopsis = [l["id"] for l in libros if l["id"] not in documentos]
        if sin_sinopsis:
            raise ValueError("No se puede reindexar: faltan sinopsis en el índice para "
                             f"{len(sin_sinopsis)} libro(s). Revisa la sincronización.")
        fuente = [{**libro, "sinopsis": documentos[libro["id"]]["sinopsis"]} for libro in libros]
        cantidad = self.indice.cambiar_modelo(clave, fuente, progreso)
        self.actividad.registrar("modelo_cambiado", f"Modelo de embeddings: {clave}",
                                 modelo=clave, libros=cantidad)
        return cantidad

    en_memoria = False

    def descripcion_conexion(self) -> str:
        if self.en_memoria:
            return f"Demostración · datos en memoria · prefijo {self.llaves.prefijo}"
        return f"Redis {config.REDIS_HOST}:{config.REDIS_PORT} · db {config.REDIS_DB} · prefijo {self.llaves.prefijo}"

    def redis_disponible(self) -> bool:
        try:
            return bool(self.r.ping())
        except redis.RedisError:
            return False

    def info_sistema(self) -> dict:
        import gestor_modelos
        propias = sum(1 for _ in self.r.scan_iter(match=self.llaves.patron, count=1000))
        try:
            version = self.r.info("server").get("redis_version", "desconocida")
        except redis.ResponseError:
            version = "desconocida"
        memoria = self.en_memoria
        return {"redis_host": "fakeredis (en memoria)" if memoria else config.REDIS_HOST,
                "redis_port": "—" if memoria else config.REDIS_PORT, "redis_db": "—" if memoria else config.REDIS_DB,
                "redis_version": version,
                "prefijo": self.llaves.prefijo, "llaves_propias": propias,
                "esquema": self.r.get(self.llaves.esquema) or "?",
                "chroma_path": "en memoria (se borra al cerrar)" if memoria else config.CHROMA_PATH,
                "coleccion": self.indice.coleccion.name,
                "documentos": self.indice.contar(), **self.info_modelo(),
                "dir_modelos": str(gestor_modelos.directorio_modelos()),
                "descarga_permitida": config.PERMITIR_DESCARGA_MODELOS, **_info_entorno()}

    def estado_seguridad(self) -> dict:
        import os

        from seguridad import cargar_llave_legada
        if os.environ.get("BIBLIOTECA_AES_KEY"):
            origen = "variable de entorno BIBLIOTECA_AES_KEY"
        else:
            origen = f"archivo {config.ARCHIVO_LLAVE_AES.name} en {config.DIR_SECRETOS.name}/ (excluido de git)"
        return {"origen_llave": origen, "cifrado_heredado": self.contar_cifrado_heredado(),
                "llave_legada": cargar_llave_legada() is not None}

    @property
    def clave_modelo(self) -> str:
        return self.indice.clave_modelo

    def info_modelo(self) -> dict:
        modelo = self.indice.modelo
        info = MODELOS.get(self.indice.clave_modelo, {})
        return {"modelo": self.indice.clave_modelo, "modelo_repositorio": info.get("nombre_completo", ""),
                "dimensiones": info.get("dim"), "max_tokens": info.get("max_tokens"),
                "modelo_cargado": bool(getattr(modelo, "cargado", False)),
                "dispositivo": modelo.descripcion_dispositivo()}

    def modelo_pendiente_de_descarga(self) -> bool:
        if not isinstance(self.indice.modelo, ModeloEmbeddings):
            return False
        import gestor_modelos
        return not gestor_modelos.esta_descargado(self.indice.clave_modelo)

    def precargar_modelo(self) -> dict:
        self.indice.modelo.embeber_consulta("calentamiento")
        return self.info_modelo()

    def catalogo_modelos(self) -> list[dict]:
        import gestor_modelos
        return [{"clave": clave, **datos, "descargado": gestor_modelos.esta_descargado(clave),
                 "activo": clave == self.indice.clave_modelo} for clave, datos in MODELOS.items()]

    def estado_modelo(self, clave: str | None = None) -> dict:
        import gestor_modelos
        return gestor_modelos.estado(clave or self.indice.clave_modelo)

    def descargar_modelo(self, clave: str | None = None, progreso=None) -> dict:
        """Descarga la revisión fijada y la valida. Lanza gestor_modelos.ErrorDescarga."""
        import gestor_modelos
        clave = clave or self.indice.clave_modelo
        gestor_modelos.descargar(clave, progreso)
        return gestor_modelos.validar(clave)

    def _modelo_para(self, clave: str | None):
        if clave in (None, self.indice.clave_modelo):
            return self.indice.modelo, False
        return ModeloEmbeddings(clave), True

    def contar_tokens(self, texto: str, clave: str | None = None) -> dict:
        clave = clave or self.indice.clave_modelo
        modelo, temporal = self._modelo_para(clave)
        try:
            tokens = modelo.contar_tokens(texto)
        finally:
            if temporal:
                modelo.liberar()
        maximo = MODELOS[clave]["max_tokens"]
        return {"clave": clave, "tokens": tokens, "palabras": len(texto.split()), "maximo": maximo,
                "cabe": tokens <= maximo}

    def revisar_cortes(self, clave: str | None = None) -> dict:
        clave = clave or self.indice.clave_modelo
        modelo, temporal = self._modelo_para(clave)
        try:
            resultados = [(d["id"], d["metadatos"].get("titulo", ""), modelo.contar_tokens(d["sinopsis"]))
                          for d in self.indice.todos()]
        finally:
            if temporal:
                modelo.liberar()
        maximo = MODELOS[clave]["max_tokens"]
        return {"clave": clave, "maximo": maximo, "resultados": sorted(resultados, key=lambda r: -r[2]),
                "cortadas": sum(1 for r in resultados if r[2] > maximo)}

    def contar_libros(self) -> int:
        return self.catalogo.contar()

    def registrar_persona(self, datos: dict) -> str:
        return self.personas.registrar(datos)

    def actualizar_persona(self, persona_id: str, datos: dict):
        self.personas.actualizar(persona_id, datos)

    def obtener_persona(self, persona_id: str) -> dict | None:
        return self.personas.obtener(persona_id)

    def buscar_personas(self, texto: str = "", tipo_usuario: str | None = None,
                        solo_con_prestamos: bool = False) -> list[dict]:
        return self.personas.buscar(texto, tipo_usuario, solo_con_prestamos)

    def listar_personas(self) -> list[dict]:
        return self.personas.listar()

    def contar_personas(self) -> int:
        return self.personas.contar()

    def contar_cifrado_heredado(self) -> int:
        return sum(1 for persona in self.personas.listar() if persona["cifrado_heredado"])

    def migrar_cifrado_heredado(self) -> int:
        return self.personas.migrar_cifrado_heredado()

    @property
    def max_libros_por_persona(self) -> int:
        return self.prestamos.maximo

    def prestamos_activos(self, persona_id: str | None = None) -> list[dict]:
        return self.prestamos.activos_de(persona_id) if persona_id else self.prestamos.activos()

    def historial_prestamos(self, persona_id: str) -> list[dict]:
        return self.prestamos.historial_de(persona_id)

    def cupo_disponible(self, persona_id: str) -> int:
        return self.prestamos.cupo_disponible(persona_id)

    def actividad_reciente(self, cantidad: int = 20) -> list[dict]:
        return self.actividad.recientes(cantidad)

    @staticmethod
    def archivos_ejemplo() -> list[Path]:
        return sorted(config.DIR_DATOS.glob("libros_*.csv"))

    def importar_datos_ejemplo(self, progreso=None) -> ResultadoLote:
        registros = [fila for archivo in self.archivos_ejemplo() for fila in leer_archivo_libros(archivo)]
        return self.importar_lote(registros, progreso)


def _info_entorno() -> dict:
    import platform
    try:
        import torch
        gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "no disponible"
        version_torch = torch.__version__
    except ImportError:
        gpu, version_torch = "no disponible", "no instalado"
    return {"gpu": gpu, "python": platform.python_version(), "torch": version_torch}


def describir_error(error: Exception) -> dict:
    """Traduce una excepción del backend a {titulo, mensaje, tipo} para mostrarla al usuario.

    `tipo` es "aviso" (el usuario puede corregirlo) o "error"; `categoria` es validacion, modelo,
    redis, integridad o inesperado. El mensaje nunca incluye datos personales.
    """
    import gestor_modelos
    if isinstance(error, ValueError):
        return {"titulo": "Revisa los datos", "mensaje": str(error), "tipo": "aviso", "categoria": "validacion"}
    if isinstance(error, ModeloNoDisponible):
        return {"titulo": "Modelo no disponible", "mensaje": str(error), "tipo": "error", "categoria": "modelo"}
    if isinstance(error, gestor_modelos.ErrorDescarga):
        return {"titulo": "Descarga del modelo", "mensaje": str(error), "tipo": "error", "categoria": "modelo"}
    if isinstance(error, redis.AuthenticationError):
        return {"titulo": "Redis rechazó la conexión",
                "mensaje": "El usuario o la contraseña de Redis (REDIS_USUARIO / REDIS_PASSWORD) no son correctos.",
                "tipo": "error", "categoria": "redis"}
    if isinstance(error, (redis.ConnectionError, redis.TimeoutError)):
        return {"titulo": "Sin conexión con Redis",
                "mensaje": f"No se pudo comunicar con Redis en {config.REDIS_HOST}:{config.REDIS_PORT}. "
                           "Verifica que el servidor esté encendido y vuelve a intentarlo.", "tipo": "error", "categoria": "redis"}
    if isinstance(error, ErrorCifrado):
        return {"titulo": "Error de integridad",
                "mensaje": "Un dato cifrado no pudo verificarse. Puede haber sido alterado o la llave no es la "
                           "correcta.", "tipo": "error", "categoria": "integridad"}
    if isinstance(error, ErrorLlave):
        return {"titulo": "Llave de cifrado inválida", "mensaje": str(error), "tipo": "error", "categoria": "integridad"}
    return {"titulo": "Error inesperado",
            "mensaje": f"La operación no se completó ({type(error).__name__}). El detalle técnico quedó en el "
                       "registro biblioteca.log.", "tipo": "error", "categoria": "inesperado"}
