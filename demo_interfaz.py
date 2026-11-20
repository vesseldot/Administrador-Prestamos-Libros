"""Abre la interfaz con datos de demostración en memoria, sin tocar datos reales.

Pensado para trabajar en el frontend: Redis se sustituye por fakeredis, ChromaDB
por una base en memoria, y la llave de cifrado y la contraseña son temporales.
No se lee ni se escribe `.env`, `secrets/`, `chroma_db/` ni ningún Redis real, y
todo se pierde al cerrar la ventana.

Uso:
    python demo_interfaz.py                  modelo simulado (sin GPU ni descargas)
    python demo_interfaz.py --modelo-real    usa el modelo descargado, si existe
    python demo_interfaz.py --sin-datos      empieza con las bases vacías

Contraseña de la demostración: demo1234
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

CONTRASENA_DEMO = "demo1234"

PERSONAS_DEMO = [
    ("Ana", "López", "Ruiz", "2003-04-12", "Femenino", "ana.demo@ejemplo.com", "5500000001", "Puebla",
     "Puebla", "72000", "Estudiante", "Alumno"),
    ("Luis", "Hernández", "Soto", "1985-09-30", "Masculino", "luis.demo@ejemplo.com", "5500000002",
     "Ciudad de México", "Ciudad de México", "06700", "Docente", "Profesor"),
    ("Mariana", "Pérez", "", "1999-01-21", "Prefiero no decir", "mariana.demo@ejemplo.com", "5500000003",
     "Guadalajara", "Jalisco", "44100", "Empleado", "Externo"),
    ("Jorge", "Ramírez", "Núñez", "2004-07-08", "Masculino", "jorge.demo@ejemplo.com", "5500000004",
     "Tlaxcala", "Tlaxcala", "90000", "Estudiante", "Alumno"),
]


def crear_servicio_demo(modelo_real: bool = False, con_datos: bool = True, progreso=None):
    """Construye un ServicioBiblioteca aislado (fakeredis + Chroma en memoria)."""
    import chromadb
    import fakeredis
    from chromadb.config import Settings

    import config
    from db_libros import GestorLibros
    from db_redis import Llaves
    from modelo_simulado import fabrica_simulada
    from modelos import MODELO_POR_DEFECTO, ModeloEmbeddings
    from portadas import AlmacenPortadas
    from seguridad import Cifrador, ControlAcceso, hash_contrasena
    from servicios import ServicioBiblioteca

    temporal = Path(tempfile.mkdtemp(prefix="biblioteca_demo_"))
    config.ARCHIVO_MODELO_ACTIVO = temporal / "modelo_activo.txt"
    cliente = chromadb.EphemeralClient(settings=Settings(anonymized_telemetry=False))
    for coleccion in cliente.list_collections():
        cliente.delete_collection(getattr(coleccion, "name", coleccion))
    fabrica = ModeloEmbeddings if modelo_real else fabrica_simulada
    indice = GestorLibros(clave_modelo=MODELO_POR_DEFECTO, fabrica_modelo=fabrica, cliente=cliente)

    almacen = {"hash": hash_contrasena(CONTRASENA_DEMO)}

    def guardar(contrasena):
        if len(contrasena) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres.")
        almacen["hash"] = hash_contrasena(contrasena)

    acceso = ControlAcceso(leer_hash=lambda: almacen["hash"], guardar_hash=guardar)
    servicio = ServicioBiblioteca.crear(r=fakeredis.FakeRedis(decode_responses=True), indice=indice,
                                        cifrador=Cifrador(llave_maestra=os.urandom(32)),
                                        llaves=Llaves("demo:"), acceso=acceso,
                                        portadas=AlmacenPortadas(temporal / "portadas"))
    servicio.en_memoria = True
    if con_datos:
        cargar_datos_demo(servicio, progreso)
    return servicio


def cargar_datos_demo(servicio, progreso=None):
    servicio.importar_datos_ejemplo(progreso)
    ids = []
    for (nombre, paterno, materno, nacimiento, genero, correo, telefono, ciudad, estado, cp, ocupacion,
         tipo) in PERSONAS_DEMO:
        ids.append(servicio.registrar_persona({
            "nombre": nombre, "apellido_paterno": paterno, "apellido_materno": materno,
            "fecha_nacimiento": nacimiento, "genero": genero, "correo": correo, "telefono": telefono,
            "calle_numero": "Calle Demo 1", "colonia": "Centro", "ciudad": ciudad, "estado": estado,
            "codigo_postal": cp, "ocupacion": ocupacion, "tipo_usuario": tipo,
            "acepta_aviso_privacidad": True}))
    servicio.prestar(ids[0], ["libro09", "libro141", "libro172"])
    servicio.prestar(ids[1], ["libro186"])
    servicio.devolver(ids[1])
    servicio.prestar(ids[1], ["libro60"])
    prestamos = servicio.prestar(ids[3], ["libro07", "libro144"])
    servicio.r.hset(servicio.llaves.prestamo(prestamos[0]["id"]), "fecha_limite", "2020-01-01")
    return ids


def main(argumentos=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--modelo-real", action="store_true", help="usar el modelo de embeddings descargado")
    parser.add_argument("--sin-datos", action="store_true", help="empezar con las bases vacías")
    opciones = parser.parse_args(argumentos)

    from main import activar_alta_densidad
    activar_alta_densidad()
    if opciones.modelo_real:
        import gestor_modelos
        from modelos import MODELO_POR_DEFECTO
        if not gestor_modelos.esta_descargado(MODELO_POR_DEFECTO):
            print("El modelo real no está descargado; se usa el modelo simulado.")
            opciones.modelo_real = False
    print("Preparando datos de demostración en memoria…", flush=True)
    servicio = crear_servicio_demo(opciones.modelo_real, not opciones.sin_datos)

    from ui.app import AplicacionBiblioteca
    app = AplicacionBiblioteca(servicio)
    app.title(app.title() + " · DEMOSTRACIÓN (datos en memoria)")
    print(f"Interfaz lista. Contraseña de la demostración: {CONTRASENA_DEMO}", flush=True)
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
