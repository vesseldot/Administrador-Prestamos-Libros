"""Gestión de secretos de la aplicación.

Uso:
    python gestionar_secretos.py estado
    python gestionar_secretos.py contrasena      cambia la contraseña del operador
    python gestionar_secretos.py nueva-llave     imprime una llave AES-256 nueva (base64)
"""
import getpass
import sys

import config
import seguridad


def mostrar_estado():
    try:
        seguridad.cargar_llave_maestra(crear_si_falta=False)
        origen = "variable BIBLIOTECA_AES_KEY" if seguridad.os.environ.get("BIBLIOTECA_AES_KEY") \
            else str(config.ARCHIVO_LLAVE_AES)
        print(f"Llave AES-256: presente ({origen})")
    except seguridad.ErrorLlave as error:
        print(f"Llave AES-256: {error}")
    print("Contraseña de operador:", "configurada" if seguridad.leer_hash_operador() else "NO configurada")
    print("Llave heredada (Fernet):", "presente" if seguridad.cargar_llave_legada() else "no existe")


def cambiar_contrasena():
    nueva = getpass.getpass("Nueva contraseña del operador (mín. 8 caracteres): ")
    if nueva != getpass.getpass("Repite la contraseña: "):
        print("Las contraseñas no coinciden.")
        return 1
    try:
        seguridad.guardar_hash_operador(nueva)
    except ValueError as error:
        print(error)
        return 1
    print(f"Contraseña actualizada en {config.ARCHIVO_HASH_OPERADOR}")
    return 0


def main(argumentos):
    accion = argumentos[0] if argumentos else "estado"
    if accion == "estado":
        mostrar_estado()
        return 0
    if accion == "contrasena":
        return cambiar_contrasena()
    if accion == "nueva-llave":
        print(seguridad.generar_llave_maestra())
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
