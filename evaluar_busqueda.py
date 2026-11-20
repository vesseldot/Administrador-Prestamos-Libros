"""Evaluación de la búsqueda semántica con un conjunto de consultas etiquetadas.

Indexa todos los libros de datos/*.csv en una ChromaDB en memoria (no toca la base
de la aplicación) y mide, para cada modelo descargado, los aciertos en las
primeras k posiciones (Hit@k), el MRR y los tiempos.

Uso:
    python evaluar_busqueda.py
    python evaluar_busqueda.py --modelos qwen3-embedding-0.6b --salida resultados.md
"""
import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

import chromadb
from chromadb.config import Settings

import config
from db_libros import GestorLibros
from modelos import (INSTRUCCION_GENERICA, INSTRUCCION_LIBROS, MODELOS, ModeloEmbeddings,
                     esta_descargado)
from servicios import leer_archivo_libros
from validaciones import validar_libro

CORTES = (1, 3, 5, 10)


def cargar_libros() -> list[dict]:
    libros = []
    for ruta in sorted(config.DIR_DATOS.glob("libros_*.csv")):
        for fila in leer_archivo_libros(ruta):
            limpio, errores = validar_libro(fila)
            if not errores:
                libros.append(limpio)
    return libros


def variantes(claves: list[str]) -> list[tuple[str, str, str]]:
    resultado = []
    for clave in claves:
        if MODELOS[clave]["estilo"] == "instruccion":
            resultado.append((f"{clave} (instrucción libros)", clave, INSTRUCCION_LIBROS))
            resultado.append((f"{clave} (instrucción genérica)", clave, INSTRUCCION_GENERICA))
        else:
            resultado.append((clave, clave, ""))
    return resultado


def memoria_gpu() -> float | None:
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.max_memory_allocated() / 1024 ** 3
    except ImportError:
        pass
    return None


def evaluar(nombre, clave, instruccion, libros, consultas) -> dict:
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
    except ImportError:
        pass
    modelo = ModeloEmbeddings(clave, instruccion=instruccion or INSTRUCCION_GENERICA)
    inicio = time.perf_counter()
    modelo.embeber_consulta("calentamiento")
    carga = time.perf_counter() - inicio
    cliente = chromadb.EphemeralClient(settings=Settings(anonymized_telemetry=False))
    indice = GestorLibros(clave_modelo=clave, fabrica_modelo=lambda _c: modelo, cliente=cliente)
    try:
        inicio = time.perf_counter()
        indice.agregar(libros)
        indexado = time.perf_counter() - inicio

        aciertos = {k: 0 for k in CORTES}
        reciproco = 0.0
        por_categoria = defaultdict(lambda: {"n": 0, "hit1": 0, "hit5": 0})
        fallos = []
        tiempos = []
        for consulta in consultas:
            inicio = time.perf_counter()
            resultados = indice.buscar(consulta["texto"], max(CORTES))
            tiempos.append(time.perf_counter() - inicio)
            ids = [r["id"] for r in resultados]
            relevantes = set(consulta["relevantes"])
            posicion = next((i + 1 for i, libro_id in enumerate(ids) if libro_id in relevantes), None)
            for k in CORTES:
                aciertos[k] += bool(posicion and posicion <= k)
            reciproco += 1 / posicion if posicion else 0
            categoria = por_categoria[consulta["categoria"]]
            categoria["n"] += 1
            categoria["hit1"] += posicion == 1
            categoria["hit5"] += bool(posicion and posicion <= 5)
            if posicion != 1:
                fallos.append({"id": consulta["id"], "texto": consulta["texto"], "posicion": posicion,
                               "primero": resultados[0]["metadatos"]["titulo"] if resultados else "",
                               "similitud": resultados[0]["similitud"] if resultados else 0})
    finally:
        cliente.delete_collection(indice.coleccion.name)
    total = len(consultas)
    gpu = memoria_gpu()
    descripcion = modelo.descripcion_dispositivo()
    modelo.liberar()
    return {"nombre": nombre, "dispositivo": descripcion, "carga_s": carga, "indexado_s": indexado,
            "consulta_ms": 1000 * sum(tiempos) / len(tiempos), "vram_gb": gpu,
            "hit": {k: aciertos[k] / total for k in CORTES}, "mrr": reciproco / total,
            "categorias": dict(por_categoria), "fallos": fallos, "libros": len(libros), "consultas": total}


def informe_markdown(resultados: list[dict]) -> str:
    lineas = ["| Modelo | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR | Indexar | Consulta | VRAM pico |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in resultados:
        vram = f"{r['vram_gb']:.2f} GB" if r["vram_gb"] is not None else "—"
        lineas.append(f"| {r['nombre']} | {r['hit'][1]:.0%} | {r['hit'][3]:.0%} | {r['hit'][5]:.0%} | "
                      f"{r['hit'][10]:.0%} | {r['mrr']:.3f} | {r['indexado_s']:.1f} s | "
                      f"{r['consulta_ms']:.0f} ms | {vram} |")
    categorias = sorted({c for r in resultados for c in r["categorias"]})
    lineas += ["", "Hit@1 por categoría:", "",
               "| Modelo | " + " | ".join(f"{c} (n={resultados[0]['categorias'][c]['n']})" for c in categorias) + " |",
               "|---|" + "---:|" * len(categorias)]
    for r in resultados:
        celdas = [f"{r['categorias'][c]['hit1'] / r['categorias'][c]['n']:.0%}" for c in categorias]
        lineas.append(f"| {r['nombre']} | " + " | ".join(celdas) + " |")
    for r in resultados:
        lineas += ["", f"Consultas sin acierto en primera posición — {r['nombre']} ({len(r['fallos'])}):", ""]
        for f in r["fallos"]:
            posicion = f"posición {f['posicion']}" if f["posicion"] else "fuera del top 10"
            lineas.append(f"- {f['id']} «{f['texto']}»: {posicion}; primero: {f['primero']} ({f['similitud']:.2f})")
    return "\n".join(lineas)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--modelos", nargs="*", help="claves de modelos (por defecto, todos los descargados)")
    parser.add_argument("--salida", help="archivo Markdown donde guardar el informe")
    argumentos = parser.parse_args()

    claves = argumentos.modelos or [c for c in MODELOS if esta_descargado(c)]
    libros = cargar_libros()
    ruta_consultas = Path(config.DIR_DATOS / "consultas_evaluacion.json")
    consultas = json.loads(ruta_consultas.read_text(encoding="utf-8"))["consultas"]
    print(f"{len(libros)} libros, {len(consultas)} consultas, modelos: {', '.join(claves)}\n")
    resultados = []
    for nombre, clave, instruccion in variantes(claves):
        print(f"Evaluando {nombre}...", flush=True)
        resultados.append(evaluar(nombre, clave, instruccion, libros, consultas))
        r = resultados[-1]
        print(f"  {r['dispositivo']} | carga {r['carga_s']:.1f} s | Hit@1 {r['hit'][1]:.0%} | MRR {r['mrr']:.3f}")
    texto = informe_markdown(resultados)
    print("\n" + texto)
    if argumentos.salida:
        Path(argumentos.salida).write_text(texto + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
