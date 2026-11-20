"""Modelo de embeddings simulado para pruebas y para el modo de demostración.

Genera vectores deterministas a partir de las palabras del texto: no necesita GPU,
red ni descargas. Tiene la misma interfaz pública que `modelos.ModeloEmbeddings`.
"""
import hashlib
import math

from validaciones import normalizar_texto

DIMENSIONES = 64


class ModeloSimulado:
    def __init__(self, clave: str = "modelo-simulado"):
        self.clave = clave
        self.info = {"nombre_completo": clave, "dim": DIMENSIONES, "max_tokens": 512}
        self.cargado = True
        self.llamadas = 0

    def _vector(self, texto: str) -> list[float]:
        vector = [0.0] * DIMENSIONES
        for palabra in normalizar_texto(texto).split():
            indice = int(hashlib.md5(palabra.encode()).hexdigest(), 16) % DIMENSIONES
            vector[indice] += 1.0
        norma = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norma for v in vector]

    def embeber_documentos(self, textos) -> list[list[float]]:
        self.llamadas += 1
        return [self._vector(t) for t in textos]

    def embeber_consulta(self, texto: str) -> list[float]:
        return self._vector(texto)

    def contar_tokens(self, texto: str) -> int:
        return len(texto.split())

    def liberar(self):
        pass

    def descripcion_dispositivo(self) -> str:
        return "cpu · simulado"


def fabrica_simulada(clave: str) -> ModeloSimulado:
    return ModeloSimulado(clave)
