"""Pantalla de acceso y bloqueo de sesión del operador."""
import math
import tkinter as tk
from tkinter import ttk

import config
from ui import tema
from ui.componentes import Boton, cabecera_dialogo, centrar, tarjeta
from ui.fondos import Animacion, EscenaNocturna
from ui.tema import COLOR


def dibujar_logo(lienzo: tk.Canvas, x: int = 0, y: int = 0, fondo: str = COLOR["primario"]):
    puntos = [x + 14, y + 2, x + 32, y + 2, x + 44, y + 2, x + 44, y + 14, x + 44, y + 32, x + 44, y + 44,
              x + 32, y + 44, x + 14, y + 44, x + 2, y + 44, x + 2, y + 32, x + 2, y + 14, x + 2, y + 2]
    lienzo.create_polygon(puntos, smooth=True, fill=fondo, outline="")
    lienzo.create_polygon(x + 10, y + 14, x + 22, y + 17, x + 22, y + 34, x + 10, y + 31, fill="white", outline="")
    lienzo.create_polygon(x + 24, y + 17, x + 36, y + 14, x + 36, y + 31, x + 24, y + 34,
                          fill=COLOR["lateral_texto"], outline="")
    for dy in (0, 5, 10):
        lienzo.create_line(x + 13, y + 19 + dy, x + 20, y + 21 + dy, fill=COLOR["lateral_texto"], width=1)


class PantallaAcceso(tk.Frame):
    """Cubre toda la ventana hasta que el operador se identifica.

    A la izquierda, la sala de lectura (ilustración animada); a la derecha, el formulario.
    """

    ANCHO_PANEL = 440

    def __init__(self, raiz, control, al_entrar, motivo: str = ""):
        super().__init__(raiz, bg=COLOR["lateral"])
        self.control = control
        self.al_entrar = al_entrar
        self.modo_crear = not control.configurado()
        self._temporizador = None
        self._sacudida = None

        panel = tk.Frame(self, bg=COLOR["tarjeta"], width=tema.px(self.ANCHO_PANEL))
        panel.pack(side="right", fill="y")
        panel.pack_propagate(False)
        escena = EscenaNocturna(self, "Biblioteca", ["Acervo, personas y préstamos en un solo lugar.",
                                                      "Busca libros por lo que cuentan, no solo por su título."])
        escena.pack(side="left", fill="both", expand=True)

        caja = tk.Frame(panel, bg=COLOR["tarjeta"], padx=tema.px(48))
        caja.place(relx=0.5, rely=0.5, anchor="center", relwidth=1.0)
        logo = tk.Canvas(caja, width=48, height=48, bg=COLOR["tarjeta"], highlightthickness=0)
        logo.pack(anchor="w")
        dibujar_logo(logo)
        titulo = "Crea tu contraseña" if self.modo_crear else "Bienvenido de nuevo"
        tk.Label(caja, text=titulo, font=tema.fs(24), fg=COLOR["texto"], bg=COLOR["tarjeta"],
                 anchor="w").pack(fill="x", pady=(18, 0))
        subtitulo = ("Será la llave del operador. Mínimo 8 caracteres." if self.modo_crear
                     else motivo or "Ingresa la contraseña del operador para continuar.")
        tk.Label(caja, text=subtitulo, font=tema.f(10), fg=COLOR["suave"], bg=COLOR["tarjeta"], anchor="w",
                 justify="left", wraplength=tema.px(self.ANCHO_PANEL - 100)).pack(fill="x", pady=(6, 22))

        self._campos = tk.Frame(caja, bg=COLOR["tarjeta"])
        self._campos.pack(fill="x")
        ttk.Label(self._campos, text="Contraseña", style="Campo.TLabel").pack(anchor="w")
        self.entrada = ttk.Entry(self._campos, show="•", font=tema.f(11))
        self.entrada.pack(fill="x", pady=(5, 12))
        self.confirmacion = None
        if self.modo_crear:
            ttk.Label(self._campos, text="Repite la contraseña", style="Campo.TLabel").pack(anchor="w")
            self.confirmacion = ttk.Entry(self._campos, show="•", font=tema.f(11))
            self.confirmacion.pack(fill="x", pady=(5, 12))
        self.mensaje = tk.Label(caja, text="", font=tema.f(9), fg=COLOR["peligro"], bg=COLOR["tarjeta"],
                                wraplength=tema.px(self.ANCHO_PANEL - 100), justify="left", anchor="w")
        self.mensaje.pack(fill="x")
        self.boton = Boton(caja, "Crear y entrar" if self.modo_crear else "Entrar", icono="candado",
                           variante="primario", comando=self._enviar, pady=10)
        self.boton.pack(fill="x", pady=(10, 0))
        tk.Label(caja, text=f"La sesión se bloquea tras {config.MINUTOS_BLOQUEO_INACTIVIDAD} minutos sin actividad.",
                 font=tema.f(9), fg=COLOR["tenue"], bg=COLOR["tarjeta"], anchor="w").pack(fill="x", pady=(18, 0))
        for entrada in filter(None, (self.entrada, self.confirmacion)):
            entrada.bind("<Return>", lambda e: self._enviar())
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()
        self.after(50, self.entrada.focus_force)
        self._actualizar_espera()

    def _actualizar_espera(self):
        restante = self.control.segundos_restantes()
        self.boton.habilitar(restante == 0)
        if restante:
            self.mensaje.configure(text=f"Demasiados intentos. Espera {restante} s.")
            self._temporizador = self.after(500, self._actualizar_espera)
        elif self._temporizador:
            self.mensaje.configure(text="")
            self._temporizador = None

    def _sacudir(self):
        """Si la contraseña es incorrecta, los campos se agitan un instante para indicarlo."""
        if not tema.ANIMACIONES:
            return
        if self._sacudida:
            self._sacudida.cancelar()
        self._sacudida = Animacion(
            self._campos, 320,
            lambda p: self._campos.pack_configure(padx=(max(0, int(10 * math.sin(p * 18) * (1 - p))),
                                                         max(0, int(-10 * math.sin(p * 18) * (1 - p))))),
            fin=lambda: self._campos.pack_configure(padx=0), curva=lambda t: t)

    def _enviar(self):
        contrasena = self.entrada.get()
        if self.modo_crear:
            try:
                self.control.crear_contrasena(contrasena, self.confirmacion.get())
            except ValueError as error:
                self.mensaje.configure(text=str(error))
                self._sacudir()
                return
            self._salir()
            return
        correcto, mensaje = self.control.intentar(contrasena)
        self.entrada.delete(0, "end")
        if correcto:
            self._salir()
        else:
            self.mensaje.configure(text=mensaje)
            self._sacudir()
            self._actualizar_espera()

    def _salir(self):
        self.destroy()
        self.al_entrar()


class CambioContrasena(tk.Toplevel):
    def __init__(self, padre, control, al_terminar):
        super().__init__(padre)
        self.withdraw()
        self.title("Cambiar contraseña")
        self.transient(padre.winfo_toplevel())
        self.resizable(False, False)
        self.configure(bg=COLOR["fondo"])
        self.control = control
        self.al_terminar = al_terminar
        cabecera_dialogo(self, "Cambiar contraseña del operador", "Mínimo 8 caracteres.", "candado")
        cuerpo = tarjeta(self, 18)
        cuerpo.pack(fill="both", padx=16, pady=14)
        self.campos = {}
        for fila, (clave, texto) in enumerate((("actual", "Contraseña actual"), ("nueva", "Nueva contraseña"),
                                               ("repetir", "Repite la nueva"))):
            ttk.Label(cuerpo, text=texto, style="Campo.TLabel").grid(row=fila, column=0, sticky="w", pady=4, padx=(0, 12))
            entrada = ttk.Entry(cuerpo, show="•", width=30)
            entrada.grid(row=fila, column=1, pady=4)
            self.campos[clave] = entrada
        self.mensaje = tk.Label(cuerpo, text="", fg=COLOR["peligro"], bg=COLOR["tarjeta"], font=tema.f(9))
        self.mensaje.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))
        pie = tk.Frame(self, bg=COLOR["fondo"])
        pie.pack(fill="x", padx=16, pady=(0, 16))
        Boton(pie, "Guardar", icono="guardar", variante="primario", comando=self._guardar).pack(side="right")
        Boton(pie, "Cancelar", comando=self.destroy).pack(side="right", padx=(0, 8))
        self.bind("<Escape>", lambda e: self.destroy())
        centrar(self, padre)
        self.deiconify()
        self.grab_set()
        self.campos["actual"].focus_set()

    def _guardar(self):
        valores = {c: e.get() for c, e in self.campos.items()}
        try:
            self.control.cambiar_contrasena(valores["actual"], valores["nueva"], valores["repetir"])
        except ValueError as error:
            self.mensaje.configure(text=str(error))
            return
        self.destroy()
        self.al_terminar()
