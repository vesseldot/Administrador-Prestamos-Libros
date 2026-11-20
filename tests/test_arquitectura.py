"""Protege la separación entre la interfaz (ui/) y el backend.

Si una de estas pruebas falla, un cambio en ui/ está accediendo a las bases de
datos o a módulos internos. Usa los métodos públicos de ServicioBiblioteca
documentados en INTEGRACION.md (o coordina con backend para añadir uno nuevo).
"""
import ast
from pathlib import Path

import pytest

from servicios import ServicioBiblioteca

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVOS_UI = sorted((RAIZ / "ui").rglob("*.py"))

MODULOS_PROHIBIDOS = {"redis", "chromadb", "fakeredis", "sentence_transformers", "torch", "transformers",
                      "huggingface_hub", "cryptography", "db_redis", "db_catalogo", "db_personas",
                      "db_prestamos", "db_libros", "modelos", "gestor_modelos", "modelo_simulado",
                      "portadas", "PIL"}
NOMBRES_PERMITIDOS = {
    "servicios": {"describir_error"},
    "seguridad": {"AVISO_PRIVACIDAD", "enmascarar_correo", "enmascarar_telefono"},
    "validaciones": {"ESTADOS_MEXICO", "GENEROS_PERSONA", "OCUPACIONES", "TIPOS_USUARIO", "TIPOS_PASTA",
                     "normalizar_texto", "clave_natural"},
}
ATRIBUTOS_INTERNOS = {"r", "llaves", "catalogo", "indice", "personas", "prestamos", "actividad", "portadas",
                      "cliente_portadas"}
API_PUBLICA = {n for n in dir(ServicioBiblioteca) if not n.startswith("_")} | {"acceso"}


def _arbol(archivo):
    return ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))


def _usos_de_servicio(arbol):
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Attribute):
            base = nodo.value
            if (isinstance(base, ast.Name) and base.id == "servicio") or \
                    (isinstance(base, ast.Attribute) and base.attr == "servicio"):
                yield nodo.lineno, nodo.attr


@pytest.mark.parametrize("archivo", ARCHIVOS_UI, ids=lambda a: str(a.relative_to(RAIZ)))
def test_ui_no_importa_bases_de_datos_ni_modulos_internos(archivo):
    problemas = []
    for nodo in ast.walk(_arbol(archivo)):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                raiz = alias.name.split(".")[0]
                if raiz in MODULOS_PROHIBIDOS or raiz in NOMBRES_PERMITIDOS:
                    problemas.append(f"línea {nodo.lineno}: import {alias.name}")
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
            raiz = nodo.module.split(".")[0]
            if raiz in MODULOS_PROHIBIDOS:
                problemas.append(f"línea {nodo.lineno}: from {nodo.module} import …")
            elif raiz in NOMBRES_PERMITIDOS:
                extra = {a.name for a in nodo.names} - NOMBRES_PERMITIDOS[raiz]
                if extra:
                    problemas.append(f"línea {nodo.lineno}: from {raiz} import {', '.join(sorted(extra))}")
    assert not problemas, "La interfaz no debe usar estos módulos/nombres:\n" + "\n".join(problemas)


@pytest.mark.parametrize("archivo", ARCHIVOS_UI, ids=lambda a: str(a.relative_to(RAIZ)))
def test_ui_solo_usa_la_api_publica_del_servicio(archivo):
    internos = [f"línea {n}: servicio.{a}" for n, a in _usos_de_servicio(_arbol(archivo)) if a in ATRIBUTOS_INTERNOS]
    desconocidos = [f"línea {n}: servicio.{a}" for n, a in _usos_de_servicio(_arbol(archivo))
                    if a not in API_PUBLICA and a not in ATRIBUTOS_INTERNOS]
    assert not internos, "Acceso directo a capas internas (Redis/Chroma):\n" + "\n".join(internos)
    assert not desconocidos, "Métodos que no existen en ServicioBiblioteca:\n" + "\n".join(desconocidos)


def test_el_backend_no_depende_de_la_interfaz():
    problemas = []
    for archivo in sorted(RAIZ.glob("*.py")):
        if archivo.name in ("main.py", "demo_interfaz.py"):
            continue
        for nodo in ast.walk(_arbol(archivo)):
            modulos = [a.name for a in nodo.names] if isinstance(nodo, ast.Import) else \
                [nodo.module] if isinstance(nodo, ast.ImportFrom) and nodo.module else []
            for modulo in modulos:
                if modulo.split(".")[0] in ("ui", "tkinter"):
                    problemas.append(f"{archivo.name}:{nodo.lineno} importa {modulo}")
    assert not problemas, "\n".join(problemas)
