"""Clase base de las secciones del panel principal y utilidades compartidas."""
import tkinter as tk
from tkinter import ttk

from ui import tema
from ui.componentes import Boton
from ui.tema import COLOR


def fecha_corta(valor: str) -> str:
    return (valor or "").replace("T", " ")[:16]


def etiqueta_estado(estado: str) -> str:
    return {"Disponible": "●  Disponible", "Prestado": "●  Prestado", "No disponible": "●  No disponible",
            "Activo": "●  Activo", "Vencido": "●  Vencido", "Devuelto": "●  Devuelto"}.get(estado, estado)


class Vista(ttk.Frame):
    titulo = ""
    subtitulo = ""

    def __init__(self, padre, app):
        super().__init__(padre, padding=(28, 22, 28, 18))
        self.app = app
        self.servicio = app.servicio
        cabecera = ttk.Frame(self)
        cabecera.pack(fill="x", pady=(0, 16))
        self.acciones = tk.Frame(cabecera, bg=COLOR["fondo"])
        self.acciones.pack(side="right", anchor="s")
        textos = ttk.Frame(cabecera)
        textos.pack(side="left", fill="x", expand=True)
        ttk.Label(textos, text=self.titulo, style="TituloVista.TLabel").pack(anchor="w")
        if self.subtitulo:
            subtitulo = ttk.Label(textos, text=self.subtitulo, style="SubtituloVista.TLabel", justify="left")
            subtitulo.pack(anchor="w", pady=(2, 0), fill="x")
            textos.bind("<Configure>", lambda e: subtitulo.configure(wraplength=max(200, e.width - 8)), add="+")
        self.cuerpo = ttk.Frame(self)
        self.cuerpo.pack(fill="both", expand=True)
        self.construir()

    def accion(self, texto, icono, comando, variante="secundario", ayuda=None) -> Boton:
        boton = Boton(self.acciones, texto, icono=icono, comando=comando, variante=variante,
                      fondo=COLOR["fondo"], ayuda=ayuda)
        boton.pack(side="right", padx=(8, 0))
        return boton

    def construir(self):
        raise NotImplementedError

    def al_mostrar(self, **contexto):
        self.refrescar()

    def refrescar(self):
        pass

    def tarea(self, trabajo, al_terminar=None, mensaje="Procesando…", al_error=None):
        self.app.tareas.ejecutar(trabajo, al_terminar, al_error, mensaje)

    def exito(self, mensaje: str):
        self.app.notificador.mostrar(mensaje, "exito")

    def aviso(self, mensaje: str):
        self.app.notificador.mostrar(mensaje, "aviso")


def badge(padre, texto: str, estilo: str = "Info") -> ttk.Label:
    return ttk.Label(padre, text=texto, style=f"Badge{estilo}.TLabel")


ESTILO_ESTADO = {"Disponible": "Ok", "Prestado": "Aviso", "No disponible": "Mal", "Activo": "Info",
                 "Vencido": "Mal", "Devuelto": "Neutro"}


def ficha_libro(texto: tk.Text):
    texto.tag_configure("titulo", font=tema.ft(14), spacing3=2)
    texto.tag_configure("autor", foreground=COLOR["suave"], font=tema.f(11), spacing3=8)
    texto.tag_configure("etq", foreground=COLOR["suave"], font=tema.f(8, "bold"))
    texto.tag_configure("valor", font=tema.f(10), spacing3=6)
    texto.tag_configure("ok", foreground=COLOR["exito"], font=tema.f(10, "bold"))
    texto.tag_configure("mal", foreground=COLOR["peligro"], font=tema.f(10, "bold"))
    texto.tag_configure("aviso", foreground=COLOR["aviso"], font=tema.f(10, "bold"))
    texto.tag_configure("suave", foreground=COLOR["suave"])
    texto.tag_configure("sinopsis", font=tema.f(10), spacing1=4, lmargin1=0, spacing2=3)


def contenido_ficha(libro: dict | None, mensaje_vacio: str) -> list[tuple[str, str]]:
    if not libro:
        return [(mensaje_vacio, "suave")]
    estado = libro.get("estado", "")
    estilo = {"Disponible": "ok", "Prestado": "aviso", "No disponible": "mal"}.get(estado, "suave")
    partes = [(libro["titulo"] + "\n", "titulo"), (f"{libro['autor']} · {libro['anio']}\n", "autor"),
              (etiqueta_estado(estado), estilo)]
    prestamo = libro.get("prestamo")
    if prestamo:
        partes.append((f"   a {prestamo['persona_id']} desde {fecha_corta(prestamo['fecha_prestamo'])}"
                       f" · vence {prestamo['fecha_limite']}", "suave"))
    if "similitud" in libro:
        partes.append((f"      similitud {libro['similitud']:.1%}", "suave"))
    partes.append(("\n\n", ""))
    pares = [("ID", "id"), ("ISBN", "isbn"), ("EDITORIAL", "editorial"), ("GÉNERO", "genero"),
             ("TEMA", "tema"), ("IDIOMA", "idioma"), ("PASTA", "pasta"), ("PÁGINAS", "paginas"),
             ("CALIFICACIÓN", "calificacion")]
    for etiqueta, clave in pares:
        partes += [(f"{etiqueta}   ", "etq"), (f"{libro.get(clave, '')}\n", "valor")]
    partes += [("\nSINOPSIS\n", "etq"), (libro.get("sinopsis") or "(sin sinopsis en el índice)", "sinopsis")]
    return partes
