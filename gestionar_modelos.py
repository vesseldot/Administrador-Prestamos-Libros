"""Administra los modelos de embeddings desde la terminal.

Uso:
    python gestionar_modelos.py estado               muestra qué modelos están descargados
    python gestionar_modelos.py descargar [clave]    descarga la revisión fijada (por defecto, el modelo activo)
    python gestionar_modelos.py validar [clave]      carga el modelo y comprueba sus dimensiones
"""
import sys
import time

import config
import gestor_modelos
from modelos import MODELO_POR_DEFECTO, MODELOS


def mostrar_estado():
    print(f"Ubicación de los modelos: {gestor_modelos.directorio_modelos()}")
    print(f"Espacio libre: {gestor_modelos.espacio_libre(gestor_modelos.directorio_modelos()) / 1e9:.1f} GB\n")
    for clave in MODELOS:
        datos = gestor_modelos.estado(clave)
        marca = "descargado" if datos["disponible"] else "no descargado"
        activo = "  ← activo" if clave == MODELO_POR_DEFECTO else ""
        print(f"  [{marca:13}] {clave:40} {datos['tamano']:>8}  {datos['licencia']:10} "
              f"rev {datos['revision'][:10]}{activo}")


def barra(hechos: int, total: int, archivo: str, inicio: float):
    proporcion = hechos / total if total else 1
    llenos = int(proporcion * 30)
    velocidad = hechos / max(time.monotonic() - inicio, 0.001) / 1e6
    sys.stdout.write(f"\r  [{'#' * llenos}{'.' * (30 - llenos)}] {proporcion:6.1%}  "
                     f"{hechos / 1e6:7.1f}/{total / 1e6:.1f} MB  {velocidad:5.1f} MB/s  {archivo[-28:]:28}")
    sys.stdout.flush()


def descargar(clave: str) -> int:
    datos = gestor_modelos.estado(clave)
    print(f"{datos['repositorio']} · revisión {datos['revision']} · licencia {datos['licencia']}")
    if datos["disponible"]:
        print(f"Ya está descargado en {datos['ruta']}. No se descarga de nuevo.")
        return 0
    if not config.PERMITIR_DESCARGA_MODELOS:
        print("La descarga está desactivada (BIBLIOTECA_PERMITIR_DESCARGA=0).")
        return 1
    print(f"Tamaño aproximado: {datos['tamano']} · destino: {datos['directorio']} · "
          f"libre: {datos['espacio_libre'] / 1e9:.1f} GB")
    inicio = time.monotonic()
    try:
        ruta = gestor_modelos.descargar(clave, lambda h, t, a: barra(h, t, a, inicio))
    except gestor_modelos.ErrorDescarga as error:
        print(f"\nERROR: {error}")
        return 1
    print(f"\nDescarga completa en {time.monotonic() - inicio:.0f} s: {ruta}")
    return validar(clave)


def validar(clave: str) -> int:
    try:
        resultado = gestor_modelos.validar(clave)
    except gestor_modelos.ErrorDescarga as error:
        print(f"ERROR: {error}")
        return 1
    print(f"Modelo válido: {resultado['dimensiones']} dimensiones en {resultado['dispositivo']}.")
    return 0


def main(argumentos) -> int:
    accion = argumentos[0] if argumentos else "estado"
    clave = argumentos[1] if len(argumentos) > 1 else MODELO_POR_DEFECTO
    if clave not in MODELOS:
        print(f"Modelo desconocido: {clave}. Opciones: {', '.join(MODELOS)}")
        return 1
    if accion == "estado":
        mostrar_estado()
        return 0
    if accion == "descargar":
        return descargar(clave)
    if accion == "validar":
        return validar(clave)
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
