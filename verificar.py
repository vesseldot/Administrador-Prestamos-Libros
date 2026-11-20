"""Revisa que las dependencias, Redis, el modelo y los secretos estén listos.

Uso:  python verificar.py
"""
import importlib
import sys

DEPENDENCIAS = [("tkinter", "viene con Python (reinstala marcando 'tcl/tk')"),
                ("chromadb", "pip install -r requirements.txt"),
                ("redis", "pip install -r requirements.txt"),
                ("sentence_transformers", "pip install -r requirements.txt"),
                ("torch", "pip install -r requirements.txt"),
                ("cryptography", "pip install -r requirements.txt"),
                ("dotenv", "pip install -r requirements.txt"),
                ("numpy", "pip install -r requirements.txt"),
                ("PIL", "pip install -r requirements.txt")]


def linea(correcto: bool, texto: str, ayuda: str = ""):
    print(f"  [{'OK' if correcto else 'FALTA':5}] {texto}" + (f"\n          {ayuda}" if ayuda and not correcto else ""))
    return correcto


def main() -> int:
    todo_bien = linea(sys.version_info >= (3, 10), f"Python {sys.version.split()[0]}", "Se necesita 3.10 o superior.")
    print("\nDependencias")
    for modulo, ayuda in DEPENDENCIAS:
        try:
            importado = importlib.import_module(modulo)
            linea(True, f"{modulo} {getattr(importado, '__version__', '')}")
        except ImportError:
            todo_bien = linea(False, modulo, ayuda) and todo_bien
    if not todo_bien:
        print("\nInstala lo que falta y vuelve a ejecutar este archivo.")
        return 1

    import config
    import gestor_modelos
    import seguridad
    from db_redis import ErrorBaseOcupada, Llaves, conectar_redis, preparar_base
    from modelos import MODELO_POR_DEFECTO, resolver_dispositivo

    print("\nConfiguración")
    for aviso in config.advertencias():
        linea(True, f"aviso: {aviso}")
    errores = config.validar()
    for error in errores:
        linea(False, error)
    if not errores:
        linea(True, "variables válidas")
    todo_bien = todo_bien and not errores

    print("\nRedis")
    try:
        r = conectar_redis()
        linea(True, f"responde en {config.REDIS_HOST}:{config.REDIS_PORT}, base {config.REDIS_DB}")
        try:
            preparar_base(r, Llaves())
            linea(True, f"la base solo contiene llaves con el prefijo '{config.REDIS_PREFIJO}'")
        except ErrorBaseOcupada as error:
            todo_bien = linea(False, "base de datos ocupada", str(error))
    except Exception as error:  # noqa: BLE001
        linea(False, f"no responde en {config.REDIS_HOST}:{config.REDIS_PORT} ({type(error).__name__})",
              "Inicia tu servidor de Redis (servicio local, Memurai, WSL o docker compose up -d) y revisa "
              "REDIS_HOST, REDIS_PORT, REDIS_USUARIO y REDIS_PASSWORD en .env.")
        todo_bien = False

    print("\nModelo de embeddings")
    import torch
    dispositivo = resolver_dispositivo()
    nombre_gpu = f" ({torch.cuda.get_device_name(0)})" if dispositivo == "cuda" else ""
    linea(True, f"dispositivo: {dispositivo}{nombre_gpu}")
    estado = gestor_modelos.estado(MODELO_POR_DEFECTO)
    descargado = linea(estado["disponible"],
                       f"{estado['repositorio']} (rev {estado['revision'][:10]}, {estado['tamano']}) en "
                       f"{estado['directorio']}",
                       "Descárgalo con:  python gestionar_modelos.py descargar  (o al abrir la aplicación)")
    if not descargado:
        linea(True, f"aviso: espacio libre {estado['espacio_libre'] / 1e9:.1f} GB")

    print("\nSeguridad")
    try:
        seguridad.cargar_llave_maestra(crear_si_falta=False)
        linea(True, "llave AES-256 presente")
    except seguridad.ErrorLlave:
        linea(True, "llave AES-256: se generará en secrets/ al primer arranque")
    linea(seguridad.leer_hash_operador() is not None, "contraseña de operador configurada",
          "Se pedirá crearla al abrir la aplicación.")

    print("\nTodo listo, ejecuta:  python main.py" if todo_bien else "\nCorrige lo marcado y vuelve a ejecutar.")
    return 0 if todo_bien else 1


if __name__ == "__main__":
    sys.exit(main())
