"""Administrador de Préstamos de Libros.

Python + Tkinter + Redis (catálogo, personas y préstamos) + ChromaDB (búsqueda semántica).
Ejecutar:  python main.py
"""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

DEPENDENCIAS = ("chromadb", "redis", "sentence_transformers", "cryptography", "dotenv")


def _entornos_virtuales():
    carpeta = Path(__file__).resolve().parent
    for base in (carpeta / ".venv", carpeta.parent / ".venv"):
        for interprete in (base / "Scripts" / "python.exe", base / "bin" / "python"):
            if interprete.exists():
                yield interprete


def asegurar_entorno():
    """Si faltan dependencias, vuelve a lanzar el programa con el Python del entorno virtual."""
    faltantes = [m for m in DEPENDENCIAS if importlib.util.find_spec(m) is None]
    if not faltantes:
        return
    actual = Path(sys.executable).resolve()
    for interprete in _entornos_virtuales():
        if interprete.resolve() != actual and not os.environ.get("BIBLIOTECA_RELANZADO"):
            print(f"Faltan {', '.join(faltantes)} en {actual}.\nUsando el entorno virtual {interprete}…", flush=True)
            entorno = {**os.environ, "BIBLIOTECA_RELANZADO": "1"}
            sys.exit(subprocess.call([str(interprete), str(Path(__file__).resolve()), *sys.argv[1:]], env=entorno))
    sys.exit(f"Faltan dependencias en {actual}: {', '.join(faltantes)}.\n"
             "Activa el entorno virtual del proyecto o instala con:  pip install -r requirements.txt")


if __name__ == "__main__":
    asegurar_entorno()

import logging  # noqa: E402
import tkinter as tk  # noqa: E402
from logging.handlers import RotatingFileHandler  # noqa: E402
from tkinter import messagebox  # noqa: E402

import config  # noqa: E402


def configurar_registro():
    manejador = RotatingFileHandler(config.BASE_DIR / "biblioteca.log", maxBytes=1_000_000, backupCount=2,
                                    encoding="utf-8")
    manejador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    registro = logging.getLogger("biblioteca")
    registro.setLevel(logging.INFO)
    registro.addHandler(manejador)
    return registro


def activar_alta_densidad():
    """Evita que Windows escale la ventana como mapa de bits en pantallas de alta densidad."""
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def error_de_arranque(titulo: str, mensaje: str):
    raiz = tk.Tk()
    raiz.withdraw()
    messagebox.showerror(titulo, mensaje)
    raiz.destroy()


def main():
    registro = configurar_registro()
    activar_alta_densidad()
    errores = config.validar()
    if errores:
        registro.error("Configuración inválida: %d problema(s)", len(errores))
        return error_de_arranque("Configuración inválida",
                                 "Corrige estos valores en el archivo .env (ver .env.example):\n\n• "
                                 + "\n• ".join(errores))
    for aviso in config.advertencias():
        registro.warning(aviso)
    import redis

    from db_redis import ErrorBaseOcupada
    from seguridad import ErrorLlave
    from servicios import ServicioBiblioteca
    try:
        servicio = ServicioBiblioteca.crear()
    except redis.AuthenticationError:
        return error_de_arranque("Redis rechazó la conexión",
                                 "El usuario o la contraseña de Redis (REDIS_USUARIO / REDIS_PASSWORD) no son correctos.")
    except (redis.ConnectionError, redis.TimeoutError) as error:
        registro.error("Redis no disponible: %s", type(error).__name__)
        return error_de_arranque(
            "No se pudo conectar a Redis",
            f"No se encontró Redis en {config.REDIS_HOST}:{config.REDIS_PORT}.\n\n"
            "Inicia tu servidor de Redis antes de abrir el programa, por ejemplo:\n"
            "   Linux/WSL:  sudo service redis-server start\n"
            "   macOS:      brew services start redis\n"
            "   Windows:    inicia el servicio de Redis o Memurai\n"
            "   Docker:     docker compose up -d\n\n"
            "Comprueba con  redis-cli -h HOST -p PUERTO ping  y ajusta REDIS_HOST / REDIS_PORT en .env.")
    except ErrorBaseOcupada as error:
        return error_de_arranque("Base de Redis ocupada", str(error))
    except ErrorLlave as error:
        return error_de_arranque("Llave de cifrado inválida", str(error))

    from ui.app import AplicacionBiblioteca
    registro.info("Aplicación iniciada (Redis db %s, modelo %s)", config.REDIS_DB, servicio.indice.clave_modelo)
    AplicacionBiblioteca(servicio).mainloop()
    registro.info("Aplicación cerrada")


if __name__ == "__main__":
    main()
