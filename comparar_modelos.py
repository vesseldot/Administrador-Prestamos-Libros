"""Compara dos modelos de embeddings sobre las sinopsis de datos/*.csv.

Muestra cuántos tokens ocupa cada sinopsis y si el modelo la corta, y después
hace las mismas búsquedas con ambos modelos. Para métricas completas usa
evaluar_busqueda.py.

Uso:  python comparar_modelos.py [modelo_a] [modelo_b]
"""
import sys

import numpy as np

from evaluar_busqueda import cargar_libros
from modelos import MODELOS, ModeloEmbeddings, esta_descargado

MODELO_CLASE = "paraphrase-multilingual-MiniLM-L12-v2"
MODELO_NUEVO = "qwen3-embedding-0.6b"
CONSULTAS = [
    "un hombre sobrevive solo en otro planeta",
    "historia de una familia durante muchas generaciones",
    "gobierno que vigila todo lo que piensas",
    "aprender a programar",
    "niño que descubre que es mago",
]


def comparar(clave: str, libros: list[dict]):
    modelo = ModeloEmbeddings(clave)
    maximo = MODELOS[clave]["max_tokens"]
    sinopsis = [libro["sinopsis"] for libro in libros]
    print("\n" + "=" * 80)
    print(f"MODELO: {clave}   (máx. {maximo} tokens, {MODELOS[clave]['dim']} dimensiones)")
    print("=" * 80)
    tokens = [modelo.contar_tokens(texto) for texto in sinopsis]
    print(f"Sinopsis que se cortan: {sum(t > maximo for t in tokens)} de {len(sinopsis)}")
    for libro, cantidad in sorted(zip(libros, tokens), key=lambda x: -x[1])[:5]:
        print(f"   {cantidad:4} tokens {'(SE CORTA)' if cantidad > maximo else '':11} {libro['titulo']}")
    vectores = np.array(modelo.embeber_documentos(sinopsis))
    print("\nBúsquedas (top 3):")
    for consulta in CONSULTAS:
        similitudes = vectores @ np.array(modelo.embeber_consulta(consulta))
        mejores = np.argsort(-similitudes)[:3]
        texto = ", ".join(f"{libros[i]['titulo']} ({similitudes[i]:.2f})" for i in mejores)
        print(f"  «{consulta}»\n      -> {texto}")
    modelo.liberar()


def main(argumentos):
    claves = argumentos[:2] or [MODELO_CLASE, MODELO_NUEVO]
    libros = cargar_libros()
    if not libros:
        print("No hay libros en datos/*.csv.")
        return 1
    for clave in claves:
        if clave not in MODELOS:
            print(f"Modelo desconocido: {clave}")
        elif not esta_descargado(clave):
            print(f"\n{clave}: no está descargado; se omite.")
        else:
            comparar(clave, libros)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
