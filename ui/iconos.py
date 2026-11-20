"""Iconografía basada en la fuente Segoe Fluent Icons (o Segoe MDL2 Assets)."""
import tkinter.font as tkfont

GLIFOS = {
    "dashboard": "", "libros": "", "buscar": "", "personas": "",
    "prestamos": "", "con_prestamo": "", "configuracion": "",
    "agregar": "", "editar": "", "eliminar": "", "importar": "",
    "exportar": "", "refrescar": "", "candado": "", "ver": "",
    "ocultar": "", "aceptar": "", "cerrar": "", "info": "",
    "aviso": "", "error": "", "devolver": "", "prestar": "",
    "escudo": "", "calendario": "", "filtro": "", "sincronizar": "",
    "reloj": "", "documento": "", "guardar": "", "contacto": "", "imagen": "",
}
RESPALDO = {
    "dashboard": "▦", "libros": "▤", "buscar": "⌕", "personas": "☺", "prestamos": "⇄",
    "con_prestamo": "☷", "configuracion": "⚙", "agregar": "+", "editar": "✎", "eliminar": "✕",
    "importar": "⇪", "exportar": "⇩", "refrescar": "↻", "candado": "🔒", "ver": "◉",
    "ocultar": "◌", "aceptar": "✓", "cerrar": "✕", "info": "ⓘ", "aviso": "⚠", "error": "⊗",
    "devolver": "↶", "prestar": "✓", "escudo": "⛨", "calendario": "▣", "filtro": "⏷",
    "sincronizar": "⟳", "reloj": "◷", "documento": "▭", "guardar": "▣", "contacto": "☏", "imagen": "▨",
}

_familia = None


def familia_iconos(raiz) -> str | None:
    global _familia
    if _familia is None:
        disponibles = set(tkfont.families(raiz))
        _familia = next((f for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets") if f in disponibles), "")
    return _familia or None


def glifo(nombre: str, raiz) -> str:
    return GLIFOS[nombre] if familia_iconos(raiz) else RESPALDO.get(nombre, "•")


def fuente(raiz, tamano: int = 12):
    familia = familia_iconos(raiz)
    return (familia, tamano) if familia else ("Segoe UI Symbol", tamano)
