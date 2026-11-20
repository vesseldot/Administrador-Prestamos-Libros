"""Paleta, tipografía y estilos ttk de la aplicación."""
import os
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

# Las animaciones son breves y se ejecutan con `after`, sin bloquear la interfaz ni las tareas en curso.
# Pueden desactivarse con BIBLIOTECA_SIN_ANIMACIONES=1 (accesibilidad, equipos lentos o pruebas).
ANIMACIONES = os.environ.get("BIBLIOTECA_SIN_ANIMACIONES", "").strip().lower() not in ("1", "true", "si", "sí")

COLOR = {
    "fondo": "#F3F5FA",
    "tarjeta": "#FFFFFF",
    "banda": "#E8ECFA",
    "banda_trazo": "#D3D9F3",
    "dorado": "#D9B26A",
    "borde": "#E3E7F1",
    "borde_fuerte": "#CBD5E1",
    "texto": "#1E293B",
    "suave": "#64748B",
    "tenue": "#94A3B8",
    "primario": "#4F46E5",
    "primario_hover": "#4338CA",
    "primario_claro": "#EEF2FF",
    "lateral": "#1E1B4B",
    "lateral_hover": "#2A2668",
    "lateral_activo": "#3730A3",
    "lateral_texto": "#C7D2FE",
    "lateral_tenue": "#8B88C9",
    "exito": "#047857",
    "exito_claro": "#D1FAE5",
    "peligro": "#DC2626",
    "peligro_claro": "#FEE2E2",
    "aviso": "#B45309",
    "aviso_claro": "#FEF3C7",
    "info": "#0369A1",
    "info_claro": "#E0F2FE",
    "fila_alterna": "#F7F8FC",
    "seleccion": "#E3E8FF",
    "cabecera_tabla": "#F5F6FB",
}

FUENTE = "Segoe UI"
FUENTE_TITULO = "Segoe UI Semibold"
FUENTE_SERIF = "Georgia"
MONO = "Consolas"
ESCALA = 1.0


def px(valor: float) -> int:
    """Convierte píxeles de diseño (pantalla de 96 ppp) a píxeles reales."""
    return int(round(valor * ESCALA))


def f(tamano: int = 10, *estilo):
    return (FUENTE, tamano, *estilo)


def ft(tamano: int = 12):
    return (FUENTE_TITULO, tamano)


def fm(tamano: int = 10):
    return (MONO, tamano)


def fs(tamano: int = 14, *estilo):
    """Tipografía con serifa para títulos y portadas; los números y la lectura corrida usan la sans."""
    return (FUENTE_SERIF, tamano, *estilo)


def elegir_fuentes(raiz):
    global FUENTE, FUENTE_TITULO, FUENTE_SERIF, MONO
    familias = set(tkfont.families(raiz))
    FUENTE = next((f for f in ("Segoe UI Variable Text", "Segoe UI", "SF Pro Text", "Inter", "Helvetica Neue",
                               "Helvetica") if f in familias), "TkDefaultFont")
    FUENTE_SERIF = next((f for f in ("Cambria", "Georgia", "Palatino Linotype", "Iowan Old Style",
                                     "Bitstream Charter", "Charter", "DejaVu Serif", "Times New Roman")
                         if f in familias), FUENTE)
    FUENTE_TITULO = next((f for f in ("Segoe UI Variable Display Semib", "Segoe UI Semibold", FUENTE)
                          if f in familias), FUENTE)
    MONO = next((f for f in ("Cascadia Code", "Consolas", "Courier New") if f in familias), "TkFixedFont")


def aplicar_tema(raiz: tk.Tk):
    global ESCALA
    ESCALA = max(1.0, raiz.winfo_fpixels("1i") / 96)
    elegir_fuentes(raiz)
    C = COLOR
    raiz.configure(background=C["fondo"])
    raiz.option_add("*TCombobox*Listbox.font", (FUENTE, 10))
    raiz.option_add("*TCombobox*Listbox.background", C["tarjeta"])
    raiz.option_add("*TCombobox*Listbox.selectBackground", C["primario"])
    raiz.option_add("*TCombobox*Listbox.selectForeground", "white")

    e = ttk.Style(raiz)
    if "clam" in e.theme_names():
        e.theme_use("clam")

    e.configure(".", background=C["fondo"], foreground=C["texto"], font=(FUENTE, 10),
                bordercolor=C["borde"], lightcolor=C["borde"], darkcolor=C["borde"],
                troughcolor=C["fondo"], focuscolor=C["primario"],
                selectbackground=C["seleccion"], selectforeground=C["texto"])

    e.configure("TFrame", background=C["fondo"])
    e.configure("Tarjeta.TFrame", background=C["tarjeta"])
    e.configure("TLabel", background=C["fondo"], foreground=C["texto"])
    e.configure("Tarjeta.TLabel", background=C["tarjeta"])
    e.configure("Campo.TLabel", background=C["tarjeta"], foreground=C["texto"])
    e.configure("Suave.TLabel", background=C["tarjeta"], foreground=C["suave"], font=(FUENTE, 9))
    e.configure("SuaveFondo.TLabel", background=C["fondo"], foreground=C["suave"], font=(FUENTE, 10))
    e.configure("Obligatorio.TLabel", background=C["tarjeta"], foreground=C["peligro"],
                font=(FUENTE, 10, "bold"))
    e.configure("TituloVista.TLabel", background=C["fondo"], foreground=C["texto"],
                font=(FUENTE_TITULO, 19))
    e.configure("SubtituloVista.TLabel", background=C["fondo"], foreground=C["suave"], font=(FUENTE, 10))
    e.configure("Titulo.TLabel", background=C["tarjeta"], foreground=C["texto"], font=(FUENTE_SERIF, 13))
    e.configure("Subtitulo.TLabel", background=C["tarjeta"], foreground=C["suave"])
    e.configure("Seccion.TLabel", background=C["tarjeta"], foreground=C["suave"], font=(FUENTE, 9, "bold"))
    for nombre, (fg, bg) in {"Info": (C["primario"], C["primario_claro"]),
                             "Ok": (C["exito"], C["exito_claro"]),
                             "Mal": (C["peligro"], C["peligro_claro"]),
                             "Aviso": (C["aviso"], C["aviso_claro"]),
                             "Neutro": (C["suave"], C["fondo"])}.items():
        e.configure(f"Badge{nombre}.TLabel", foreground=fg, background=bg,
                    font=(FUENTE, 9, "bold"), padding=(10, 4))

    e.configure("TButton", background=C["tarjeta"], foreground=C["texto"], padding=(14, 7),
                bordercolor=C["borde_fuerte"], lightcolor=C["tarjeta"], darkcolor=C["tarjeta"],
                focuscolor=C["tarjeta"], relief="flat", font=(FUENTE, 10))
    e.map("TButton",
          background=[("disabled", C["fondo"]), ("pressed", C["borde"]), ("active", C["fila_alterna"])],
          lightcolor=[("pressed", C["borde"]), ("active", C["fila_alterna"])],
          darkcolor=[("pressed", C["borde"]), ("active", C["fila_alterna"])],
          bordercolor=[("active", C["primario"])],
          foreground=[("disabled", C["tenue"])])

    e.configure("Primario.TButton", background=C["primario"], foreground="white",
                bordercolor=C["primario"], lightcolor=C["primario"], darkcolor=C["primario"],
                focuscolor=C["primario"], font=(FUENTE, 10, "bold"))
    e.map("Primario.TButton",
          background=[("disabled", C["borde_fuerte"]), ("pressed", C["lateral"]), ("active", C["primario_hover"])],
          lightcolor=[("pressed", C["lateral"]), ("active", C["primario_hover"])],
          darkcolor=[("pressed", C["lateral"]), ("active", C["primario_hover"])],
          bordercolor=[("disabled", C["borde_fuerte"]), ("pressed", C["lateral"]), ("active", C["primario_hover"])],
          foreground=[("disabled", "white")])

    e.configure("Peligro.TButton", foreground=C["peligro"])
    e.map("Peligro.TButton",
          background=[("pressed", "#FECACA"), ("active", C["peligro_claro"])],
          lightcolor=[("pressed", "#FECACA"), ("active", C["peligro_claro"])],
          darkcolor=[("pressed", "#FECACA"), ("active", C["peligro_claro"])],
          bordercolor=[("active", C["peligro"])],
          foreground=[("disabled", C["tenue"])])

    e.configure("Enlace.TButton", foreground=C["primario"], bordercolor=C["tarjeta"], padding=(8, 5))
    e.map("Enlace.TButton",
          background=[("active", C["primario_claro"])], lightcolor=[("active", C["primario_claro"])],
          darkcolor=[("active", C["primario_claro"])], bordercolor=[("active", C["primario_claro"])])

    e.configure("Chip.TButton", foreground=C["primario"], background=C["primario_claro"],
                bordercolor=C["primario_claro"], lightcolor=C["primario_claro"],
                darkcolor=C["primario_claro"], padding=(10, 4), font=(FUENTE, 9))
    e.map("Chip.TButton", background=[("active", C["seleccion"])], bordercolor=[("active", C["primario"])])

    for w in ("TEntry", "TCombobox", "TSpinbox"):
        e.configure(w, fieldbackground="white", foreground=C["texto"], padding=(8, 6),
                    bordercolor=C["borde_fuerte"], lightcolor=C["borde"], darkcolor=C["borde"],
                    insertcolor=C["texto"], arrowcolor=C["suave"], background=C["tarjeta"])
        e.map(w,
              bordercolor=[("focus", C["primario"])], lightcolor=[("focus", C["primario"])],
              darkcolor=[("focus", C["primario"])],
              fieldbackground=[("disabled", C["fondo"]), ("readonly", "white")],
              foreground=[("disabled", C["suave"])])
    e.configure("Invalido.TEntry", bordercolor=C["peligro"], lightcolor=C["peligro"], darkcolor=C["peligro"])
    e.map("TCombobox", selectbackground=[("readonly", "white")],
          selectforeground=[("readonly", C["texto"])])

    for estilo, fondo in (("TCheckbutton", C["tarjeta"]), ("Fondo.TCheckbutton", C["fondo"])):
        e.configure(estilo, background=fondo, foreground=C["texto"], indicatorbackground="white",
                    indicatorforeground="white", focuscolor=fondo, indicatormargin=(0, 0, 6, 0))
        e.map(estilo, background=[("active", fondo)],
              indicatorbackground=[("disabled", C["fondo"]), ("selected", C["primario"])])

    e.configure("TNotebook", background=C["fondo"], borderwidth=0, tabmargins=(0, 0, 0, 0))
    e.configure("TNotebook.Tab", background=C["fondo"], foreground=C["suave"], padding=(18, 9),
                font=(FUENTE, 10), borderwidth=0, bordercolor=C["fondo"], lightcolor=C["fondo"])
    e.map("TNotebook.Tab", background=[("selected", C["tarjeta"]), ("active", C["primario_claro"])],
          foreground=[("selected", C["primario"]), ("active", C["texto"])],
          lightcolor=[("selected", C["tarjeta"])], bordercolor=[("selected", C["borde"])])

    e.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    e.configure("Treeview", background=C["tarjeta"], fieldbackground=C["tarjeta"],
                foreground=C["texto"], rowheight=px(32), borderwidth=0, font=(FUENTE, 10))
    e.map("Treeview", background=[("selected", C["seleccion"])],
          foreground=[("selected", C["lateral"])])
    e.configure("Treeview.Heading", background=C["cabecera_tabla"], foreground=C["suave"],
                font=(FUENTE, 9, "bold"), relief="flat", padding=(8, 9),
                bordercolor=C["borde"], lightcolor=C["cabecera_tabla"], darkcolor=C["cabecera_tabla"])
    e.map("Treeview.Heading", background=[("active", C["borde"])])

    e.configure("Vertical.TScrollbar", background=C["borde"], troughcolor=C["tarjeta"],
                bordercolor=C["tarjeta"], lightcolor=C["borde"], darkcolor=C["borde"],
                arrowcolor=C["suave"], gripcount=0, arrowsize=12)
    e.map("Vertical.TScrollbar", background=[("active", C["borde_fuerte"])])

    e.configure("Horizontal.TProgressbar", troughcolor=C["borde"], background=C["primario"],
                bordercolor=C["borde"], lightcolor=C["primario"], darkcolor=C["primario"], thickness=4)
    for nombre, color in (("CupoOk", C["exito"]), ("CupoLleno", C["peligro"])):
        e.configure(f"{nombre}.Horizontal.TProgressbar", troughcolor=C["borde"], background=color,
                    bordercolor=C["borde"], lightcolor=color, darkcolor=color, thickness=10)
