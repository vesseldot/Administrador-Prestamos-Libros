"""Componentes visuales reutilizables."""
import base64
import tkinter as tk
from tkinter import ttk

from ui import iconos, tema
from ui.fondos import Animacion, mezclar
from ui.tema import COLOR
from validaciones import clave_natural


def centrar(ventana, padre):
    ventana.update_idletasks()
    raiz = padre.winfo_toplevel()
    ancho, alto = ventana.winfo_reqwidth(), ventana.winfo_reqheight()
    x = raiz.winfo_rootx() + (raiz.winfo_width() - ancho) // 2
    y = raiz.winfo_rooty() + (raiz.winfo_height() - alto) // 2
    ventana.geometry(f"+{max(x, 0)}+{max(y, 0)}")


def tarjeta(padre, padding: int = 16) -> tk.Frame:
    return tk.Frame(padre, bg=COLOR["tarjeta"], highlightthickness=1,
                    highlightbackground=COLOR["borde"], highlightcolor=COLOR["borde"],
                    padx=padding, pady=padding)


def encabezado_tarjeta(padre, titulo: str, subtitulo: str | None = None):
    fila = ttk.Frame(padre, style="Tarjeta.TFrame")
    fila.pack(fill="x", pady=(0, 10))
    textos = ttk.Frame(fila, style="Tarjeta.TFrame")
    textos.pack(side="left", fill="x", expand=True)
    etiqueta = ttk.Label(textos, text=titulo, style="Titulo.TLabel")
    etiqueta.pack(anchor="w")
    if subtitulo:
        sub = ttk.Label(textos, text=subtitulo, style="Subtitulo.TLabel", wraplength=600, justify="left")
        sub.pack(anchor="w", pady=(2, 0))
        textos.bind("<Configure>", lambda e: sub.configure(wraplength=max(240, e.width - 10)), add="+")
    return fila, etiqueta


def caja_texto(padre, alto: int, solo_lectura: bool = False, mono: bool = False, **opciones) -> tk.Text:
    texto = tk.Text(padre, height=alto, wrap="word", relief="flat", borderwidth=0,
                    bg=COLOR["fila_alterna"] if solo_lectura else "white", fg=COLOR["texto"],
                    font=tema.fm(10) if mono else tema.f(10), padx=12, pady=10,
                    highlightthickness=1, highlightbackground=COLOR["borde_fuerte"],
                    highlightcolor=COLOR["primario"], insertbackground=COLOR["texto"],
                    selectbackground=COLOR["seleccion"], selectforeground=COLOR["texto"], **opciones)
    if solo_lectura:
        texto.configure(state="disabled")
    return texto


def escribir(texto: tk.Text, contenido, limpiar: bool = True):
    """Escribe texto simple o una lista de (texto, etiqueta) en un Text de solo lectura."""
    texto.configure(state="normal")
    if limpiar:
        texto.delete("1.0", "end")
    if isinstance(contenido, str):
        texto.insert("end", contenido)
    else:
        for fragmento, estilo in contenido:
            texto.insert("end", fragmento, estilo)
    texto.configure(state="disabled")


class Boton(tk.Frame):
    """Botón con icono y texto, estados de hover, presión, foco y deshabilitado."""

    VARIANTES = {
        "primario": {"bg": "primario", "fg": "#FFFFFF", "hover": "primario_hover", "borde": "primario",
                     "presion": "lateral"},
        "secundario": {"bg": "tarjeta", "fg": "texto", "hover": "fila_alterna", "borde": "borde_fuerte",
                       "presion": "borde"},
        "peligro": {"bg": "tarjeta", "fg": "peligro", "hover": "peligro_claro", "borde": "borde_fuerte",
                    "presion": "peligro_claro"},
        "enlace": {"bg": None, "fg": "primario", "hover": "primario_claro", "borde": None,
                   "presion": "seleccion"},
        "chip": {"bg": "primario_claro", "fg": "primario", "hover": "seleccion", "borde": "primario_claro",
                 "presion": "seleccion"},
    }

    def __init__(self, padre, texto: str = "", icono: str | None = None, comando=None,
                 variante: str = "secundario", fondo: str | None = None, tamano: int = 10,
                 padx: int = 14, pady: int = 7, ayuda: str | None = None):
        self._v = self.VARIANTES[variante]
        self._fondo_padre = fondo or COLOR["tarjeta"]
        self._comando = comando
        self._habilitado = True
        self._dentro = False
        super().__init__(padre, bg=self._color("bg"), cursor="hand2", takefocus=1,
                         highlightthickness=1, highlightbackground=self._color("borde"),
                         highlightcolor=COLOR["primario"], padx=padx, pady=pady)
        self._actual_bg = self._color("bg")
        self._anim = None
        self._partes = []
        if icono:
            lbl = tk.Label(self, text=iconos.glifo(icono, self), font=iconos.fuente(self, tamano + 1),
                           bg=self._color("bg"), fg=self._color("fg"))
            lbl.pack(side="left", padx=(0, 8 if texto else 0))
            self._partes.append(lbl)
        self._etiqueta = tk.Label(self, text=texto, font=tema.f(tamano, "bold") if variante == "primario"
                                  else tema.f(tamano), bg=self._color("bg"), fg=self._color("fg"))
        if texto:
            self._etiqueta.pack(side="left")
        self._partes.append(self._etiqueta)
        for widget in [self, *self._partes]:
            widget.bind("<Enter>", self._entrar, add="+")
            widget.bind("<Leave>", self._salir, add="+")
            widget.bind("<ButtonPress-1>", self._presionar, add="+")
            widget.bind("<ButtonRelease-1>", self._soltar, add="+")
        self.bind("<Return>", lambda e: self.invocar())
        self.bind("<space>", lambda e: self.invocar())
        if ayuda:
            Ayuda(self, ayuda)

    def _color(self, clave):
        valor = self._v[clave]
        if valor is None:
            return self._fondo_padre
        return COLOR.get(valor, valor)

    def _pintar(self, fondo: str, texto: str | None = None):
        self._actual_bg = fondo
        self.configure(bg=fondo)
        for parte in self._partes:
            parte.configure(bg=fondo, fg=texto or self._color("fg"))

    def _transicion(self, destino: str, ms: int = 110):
        """Cambia de color de forma gradual; ante un clic o un cambio de estado se corta de inmediato."""
        if getattr(self, "_anim", None):
            self._anim.cancelar()
        origen = getattr(self, "_actual_bg", destino)
        self._anim = Animacion(self, ms, lambda p: self._pintar(mezclar(origen, destino, p)),
                               fin=lambda: self._pintar(destino), intervalo_ms=18)

    def _detener_transicion(self):
        if getattr(self, "_anim", None):
            self._anim.cancelar()
            self._anim = None

    def _entrar(self, _e=None):
        self._dentro = True
        if self._habilitado:
            self._transicion(self._color("hover"))

    def _salir(self, _e=None):
        self._dentro = False
        if self._habilitado:
            self._transicion(self._color("bg"))

    def _presionar(self, _e=None):
        if self._habilitado:
            self._detener_transicion()
            self._pintar(self._color("presion"))

    def _soltar(self, evento=None):
        if not self._habilitado:
            return
        x, y = self.winfo_pointerx() - self.winfo_rootx(), self.winfo_pointery() - self.winfo_rooty()
        dentro = 0 <= x <= self.winfo_width() and 0 <= y <= self.winfo_height()
        self._detener_transicion()
        self._pintar(self._color("hover") if dentro else self._color("bg"))
        if dentro:
            self.invocar()

    def invocar(self):
        if self._habilitado and self._comando:
            self._comando()

    def habilitar(self, valor: bool = True):
        self._detener_transicion()
        self._habilitado = valor
        self.configure(cursor="hand2" if valor else "arrow", takefocus=1 if valor else 0,
                       highlightbackground=self._color("borde") if valor else
                       (COLOR["borde"] if self._v["borde"] else self._fondo_padre))
        if valor:
            self._pintar(self._color("hover") if self._dentro else self._color("bg"))
        else:
            self._pintar(COLOR["fondo"] if self._v["bg"] else self._fondo_padre, COLOR["tenue"])

    def texto(self, valor: str):
        self._etiqueta.configure(text=valor)


class Portada(tk.Frame):
    """Marco de tamaño fijo con la portada de un libro (PNG que entrega el servicio) o un aviso si no hay."""

    def __init__(self, padre, ancho: int = 110, alto: int = 165):
        self.ancho, self.alto = tema.px(ancho), tema.px(alto)
        super().__init__(padre, width=self.ancho, height=self.alto, bg=COLOR["fila_alterna"],
                         highlightthickness=1, highlightbackground=COLOR["borde"])
        self.pack_propagate(False)
        self._foto = None
        self.etiqueta = tk.Label(self, bg=COLOR["fila_alterna"], fg=COLOR["tenue"], font=tema.f(8),
                                 justify="center", wraplength=self.ancho - tema.px(10))
        self.etiqueta.pack(fill="both", expand=True)
        self.mostrar(None)

    @property
    def tamano(self) -> tuple[int, int]:
        """Espacio disponible para la imagen, en píxeles, descontando el borde."""
        return self.ancho - 2, self.alto - 2

    @property
    def con_imagen(self) -> bool:
        return self._foto is not None

    def mostrar(self, png: bytes | None, mensaje: str = "Sin portada"):
        if png:
            self._foto = tk.PhotoImage(master=self, data=base64.b64encode(png).decode("ascii"))
            self.etiqueta.configure(image=self._foto, text="")
        else:
            self._foto = None
            self.etiqueta.configure(image="", text=mensaje)


class Ayuda:
    """Globo de ayuda que aparece al dejar el cursor sobre un widget."""

    def __init__(self, widget, texto: str, retraso_ms: int = 600):
        self.widget, self.texto, self.retraso = widget, texto, retraso_ms
        self._id = None
        self._ventana = None
        widget.bind("<Enter>", self._programar, add="+")
        widget.bind("<Leave>", self._ocultar, add="+")
        widget.bind("<ButtonPress>", self._ocultar, add="+")

    def _programar(self, _e=None):
        self._cancelar()
        self._id = self.widget.after(self.retraso, self._mostrar)

    def _cancelar(self):
        if self._id:
            self.widget.after_cancel(self._id)
            self._id = None

    def _mostrar(self):
        self._ventana = tk.Toplevel(self.widget)
        self._ventana.wm_overrideredirect(True)
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self._ventana.geometry(f"+{x}+{y}")
        tk.Label(self._ventana, text=self.texto, bg=COLOR["lateral"], fg="white", font=tema.f(9),
                 padx=10, pady=5, justify="left", wraplength=320).pack()

    def _ocultar(self, _e=None):
        self._cancelar()
        if self._ventana:
            self._ventana.destroy()
            self._ventana = None


class Tabla(ttk.Frame):
    """Treeview con desplazamiento, ordenamiento por columna y estado vacío."""

    def __init__(self, padre, columnas, seleccion: str = "browse", alto: int = 12,
                 mensaje_vacio: str = "No hay registros para mostrar.", icono_vacio: str = "documento",
                 clave_id: str = "id", estilo_fila=None, formatos: dict | None = None, arbol: bool = False):
        super().__init__(padre, style="Tarjeta.TFrame")
        self.columnas = columnas
        self.clave_id = clave_id
        self.estilo_fila = estilo_fila
        self.formatos = formatos or {}
        self._filas: list[dict] = []
        self._orden: tuple[str, bool] | None = None
        claves = [c[0] for c in columnas]
        self.tree = ttk.Treeview(self, columns=claves, show="tree headings" if arbol else "headings",
                                 selectmode=seleccion, height=alto)
        self._arbol = arbol
        if arbol:
            self.tree.column("#0", width=int(28 * tema.ESCALA), stretch=False)
        self._anchos_base = {}
        self._ancho_previo = 0
        for clave, titulo, ancho, *resto in columnas:
            alineacion = resto[0] if resto else "w"
            self.tree.heading(clave, text=titulo, anchor=alineacion,
                              command=lambda c=clave: self.ordenar(c))
            self.tree.column(clave, width=int(ancho * tema.ESCALA), minwidth=40, anchor=alineacion, stretch=False)
            self._anchos_base[clave] = ancho
        self.tree.bind("<Configure>", self._ajustar_columnas, add="+")
        self.tree.tag_configure("par", background=COLOR["fila_alterna"])
        self.tree.tag_configure("tenue", foreground=COLOR["tenue"])
        self.tree.tag_configure("alerta", foreground=COLOR["peligro"])
        self.tree.tag_configure("grupo", font=tema.f(10, "bold"))
        barra = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=barra.set)
        self.tree.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")

        self._vacio = tk.Frame(self.tree, bg=COLOR["tarjeta"])
        tk.Label(self._vacio, text=iconos.glifo(icono_vacio, self), font=iconos.fuente(self, 26),
                 fg=COLOR["borde_fuerte"], bg=COLOR["tarjeta"]).pack()
        self._lbl_vacio = tk.Label(self._vacio, text=mensaje_vacio, font=tema.f(10),
                                   fg=COLOR["suave"], bg=COLOR["tarjeta"])
        self._lbl_vacio.pack(pady=(6, 0))

    def _formatear(self, clave, valor):
        if clave in self.formatos:
            return self.formatos[clave](valor)
        if isinstance(valor, bool):
            return "Sí" if valor else "No"
        if valor is None:
            return ""
        return valor

    def cargar(self, filas: list[dict], mensaje_vacio: str | None = None, conservar_seleccion: bool = True):
        seleccion = set(self.tree.selection()) if conservar_seleccion else set()
        self._filas = list(filas)
        if self._orden:
            self._aplicar_orden()
        self._dibujar(seleccion)
        if mensaje_vacio:
            self._lbl_vacio.configure(text=mensaje_vacio)

    def cargar_arbol(self, grupos: list[tuple[dict, list[dict]]], mensaje_vacio: str | None = None):
        """grupos = [(fila_padre, [filas_hijas]), ...]"""
        self.tree.delete(*self.tree.get_children())
        self._filas = []
        for n, (padre, hijos) in enumerate(grupos):
            iid = str(padre[self.clave_id])
            self.tree.insert("", "end", iid=iid, open=True, tags=("grupo",) + (("par",) if n % 2 else ()),
                             values=[self._formatear(c[0], padre.get(c[0], "")) for c in self.columnas])
            self._filas.append(padre)
            for hijo in hijos:
                etiquetas = self.estilo_fila(hijo) if self.estilo_fila else ()
                self.tree.insert(iid, "end", iid=str(hijo[self.clave_id]), tags=tuple(etiquetas),
                                 values=[self._formatear(c[0], hijo.get(c[0], "")) for c in self.columnas])
                self._filas.append(hijo)
        if mensaje_vacio:
            self._lbl_vacio.configure(text=mensaje_vacio)
        self._mostrar_vacio(not grupos)

    def _dibujar(self, seleccion=()):
        self.tree.delete(*self.tree.get_children())
        for n, fila in enumerate(self._filas):
            etiquetas = ["par"] if n % 2 else []
            if self.estilo_fila:
                etiquetas += list(self.estilo_fila(fila))
            self.tree.insert("", "end", iid=str(fila[self.clave_id]), tags=etiquetas,
                             values=[self._formatear(c[0], fila.get(c[0], "")) for c in self.columnas])
        vigentes = [i for i in seleccion if self.tree.exists(i)]
        if vigentes:
            self.tree.selection_set(vigentes)
        self._mostrar_vacio(not self._filas)
        self._marcar_encabezados()

    def _mostrar_vacio(self, vacio: bool):
        if vacio:
            self._vacio.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self._vacio.place_forget()

    @staticmethod
    def _llave_orden(valor):
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            return (0, valor, ())
        return (1, 0, clave_natural(valor))

    def _ajustar_columnas(self, evento):
        disponible = evento.width - 4 - (self.tree.column("#0", "width") if self._arbol else 0)
        if disponible < 100 or disponible == self._ancho_previo:
            return
        self._ancho_previo = disponible
        total = sum(self._anchos_base.values())
        for clave, base in self._anchos_base.items():
            self.tree.column(clave, width=max(40, int(base * disponible / total)))

    def _aplicar_orden(self):
        clave, descendente = self._orden
        self._filas.sort(key=lambda f: self._llave_orden(f.get(clave, "")), reverse=descendente)

    def _marcar_encabezados(self):
        for clave, titulo, *_ in self.columnas:
            marca = ""
            if self._orden and self._orden[0] == clave:
                marca = "  ▼" if self._orden[1] else "  ▲"
            self.tree.heading(clave, text=titulo + marca)

    def ordenar(self, clave: str):
        descendente = bool(self._orden and self._orden[0] == clave and not self._orden[1])
        self._orden = (clave, descendente)
        self._aplicar_orden()
        self._dibujar(set(self.tree.selection()))

    def seleccion(self) -> list[str]:
        return list(self.tree.selection())

    def fila(self, iid: str) -> dict | None:
        return next((f for f in self._filas if str(f[self.clave_id]) == iid), None)

    def fila_seleccionada(self) -> dict | None:
        seleccion = self.seleccion()
        return self.fila(seleccion[0]) if seleccion else None

    def filas_seleccionadas(self) -> list[dict]:
        return [f for f in (self.fila(i) for i in self.seleccion()) if f]

    def seleccionar(self, iid: str):
        if self.tree.exists(iid):
            self.tree.selection_set(iid)
            self.tree.see(iid)

    @property
    def filas(self) -> list[dict]:
        return list(self._filas)


class Notificador:
    """Avisos breves en la esquina inferior derecha de la ventana."""

    ESTILOS = {"exito": ("exito", "exito_claro", "aceptar"), "error": ("peligro", "peligro_claro", "error"),
               "aviso": ("aviso", "aviso_claro", "aviso"), "info": ("primario", "primario_claro", "info")}

    def __init__(self, raiz):
        self.raiz = raiz
        self._activos: list[tk.Frame] = []

    def mostrar(self, texto: str, tipo: str = "exito", duracion_ms: int = 3800):
        color, fondo, icono = self.ESTILOS.get(tipo, self.ESTILOS["info"])
        caja = tk.Frame(self.raiz, bg=COLOR[fondo], highlightthickness=1,
                        highlightbackground=COLOR[color], padx=14, pady=10, cursor="hand2")
        tk.Label(caja, text=iconos.glifo(icono, caja), font=iconos.fuente(caja, 13), fg=COLOR[color],
                 bg=COLOR[fondo]).pack(side="left", padx=(0, 10))
        tk.Label(caja, text=texto, font=tema.f(10), fg=COLOR["texto"], bg=COLOR[fondo],
                 justify="left", wraplength=360).pack(side="left")
        self._activos.append(caja)
        caja._dx = 0
        self._reubicar()
        if tema.ANIMACIONES:
            caja._dx = 56

            def deslizar(p, c=caja):
                if c in self._activos:
                    c._dx = int(56 * (1 - p))
                    c.place_configure(x=-24 + c._dx)
            Animacion(caja, 220, deslizar)
        for widget in (caja, *caja.winfo_children()):
            widget.bind("<Button-1>", lambda e, c=caja: self._cerrar(c))
        self.raiz.after(duracion_ms, lambda: self._cerrar(caja))

    def _reubicar(self):
        desplazamiento = -46
        for caja in reversed(self._activos):
            caja.place(relx=1.0, rely=1.0, anchor="se", x=-24 + getattr(caja, "_dx", 0), y=desplazamiento)
            caja.lift()
            caja.update_idletasks()
            desplazamiento -= caja.winfo_reqheight() + 8

    def _cerrar(self, caja):
        if caja in self._activos:
            self._activos.remove(caja)
            caja.destroy()
            self._reubicar()


class Indicador(tk.Frame):
    """Tarjeta de indicador del Dashboard: el número sube hasta su valor y, si aplica, muestra una proporción."""

    def __init__(self, padre, titulo: str, icono: str, color: str = "primario", comando=None):
        super().__init__(padre, bg=COLOR["tarjeta"], highlightthickness=1,
                         highlightbackground=COLOR["borde"], padx=20, pady=14)
        claro = {"primario": "primario_claro", "exito": "exito_claro", "peligro": "peligro_claro",
                 "aviso": "aviso_claro", "info": "info_claro"}[color]
        self._color = COLOR[color]
        self._valor_actual = 0
        self._anim_valor = self._anim_barra = None
        self._fraccion = 0.0
        cabecera = tk.Frame(self, bg=COLOR["tarjeta"])
        cabecera.pack(fill="x")
        tk.Label(cabecera, text=titulo, font=tema.f(10), fg=COLOR["suave"],
                 bg=COLOR["tarjeta"]).pack(side="left", anchor="n", pady=(4, 0))
        tk.Label(cabecera, text=iconos.glifo(icono, self), font=iconos.fuente(self, 14),
                 fg=COLOR[color], bg=COLOR[claro], padx=8, pady=5).pack(side="right")
        self._valor = tk.Label(self, text="—", font=tema.f(26, "bold"), fg=COLOR["texto"], bg=COLOR["tarjeta"])
        self._valor.pack(anchor="w", pady=(2, 0))
        self._barra = tk.Canvas(self, height=6, bg=COLOR["tarjeta"], highlightthickness=0)
        self._barra.bind("<Configure>", lambda e: self._dibujar_barra())
        self._detalle = tk.Label(self, text="", font=tema.f(9), fg=COLOR["suave"], bg=COLOR["tarjeta"])
        self._detalle.pack(anchor="w", pady=(4, 0))
        if comando:
            for widget in (self, cabecera, self._valor, self._detalle, self._barra, *cabecera.winfo_children()):
                widget.configure(cursor="hand2")
                widget.bind("<Button-1>", lambda e: comando())
            self.bind("<Enter>", lambda e: self.configure(highlightbackground=COLOR["primario"]))
            self.bind("<Leave>", lambda e: self.configure(highlightbackground=COLOR["borde"]))

    def _dibujar_barra(self, fraccion: float | None = None):
        ancho = self._barra.winfo_width()
        fraccion = self._fraccion if fraccion is None else fraccion
        self._barra.delete("all")
        self._barra.create_rectangle(0, 1, ancho, 5, fill=COLOR["borde"], outline="")
        if fraccion > 0:
            self._barra.create_rectangle(0, 1, max(4, ancho * fraccion), 5, fill=self._color, outline="")

    def actualizar(self, valor, detalle: str = "", fraccion: float | None = None):
        """`fraccion` (0 a 1) muestra una barra de proporción bajo el número; None la oculta."""
        self._detalle.configure(text=detalle)
        if isinstance(valor, int) and not isinstance(valor, bool):
            origen, destino = self._valor_actual, valor
            if self._anim_valor:
                self._anim_valor.cancelar()
            if origen == destino:
                self._valor.configure(text=str(destino))
            else:
                self._anim_valor = Animacion(
                    self._valor, 750, lambda p: self._valor.configure(text=str(round(origen + (destino - origen) * p))),
                    fin=lambda: self._valor.configure(text=str(destino)))
            self._valor_actual = destino
        else:
            self._valor.configure(text=str(valor))
        if fraccion is None:
            self._barra.pack_forget()
            self._fraccion = 0.0
            return
        if not self._barra.winfo_manager():
            self._barra.pack(fill="x", pady=(8, 0), before=self._detalle)
        inicio, fin = self._fraccion, max(0.0, min(1.0, fraccion))
        if self._anim_barra:
            self._anim_barra.cancelar()
        self._anim_barra = Animacion(self._barra, 750, lambda p: self._dibujar_barra(inicio + (fin - inicio) * p),
                                     fin=lambda: setattr(self, "_fraccion", fin))
        self._fraccion = fin


def cabecera_dialogo(ventana, titulo: str, subtitulo: str | None = None, icono: str | None = None):
    cabecera = tk.Frame(ventana, bg=COLOR["lateral"], padx=20, pady=14)
    cabecera.pack(fill="x")
    if icono:
        tk.Label(cabecera, text=iconos.glifo(icono, ventana), font=iconos.fuente(ventana, 18),
                 fg=COLOR["lateral_texto"], bg=COLOR["lateral"]).pack(side="left", padx=(0, 14))
    textos = tk.Frame(cabecera, bg=COLOR["lateral"])
    textos.pack(side="left", fill="x")
    tk.Label(textos, text=titulo, font=tema.fs(14), fg="white", bg=COLOR["lateral"]).pack(anchor="w")
    if subtitulo:
        tk.Label(textos, text=subtitulo, font=tema.f(9), fg=COLOR["lateral_texto"],
                 bg=COLOR["lateral"]).pack(anchor="w")
    return cabecera


class Dialogo(tk.Toplevel):
    """Diálogo modal con el estilo de la aplicación. `resultado` guarda el botón elegido."""

    TIPOS = {"info": ("info", "primario"), "exito": ("aceptar", "exito"), "aviso": ("aviso", "aviso"),
             "error": ("error", "peligro"), "pregunta": ("info", "primario"), "peligro": ("aviso", "peligro")}

    def __init__(self, padre, titulo: str, mensaje: str, tipo: str = "info", botones=None, detalle: str = ""):
        super().__init__(padre)
        self.withdraw()
        self.title(titulo)
        self.resizable(False, False)
        self.configure(bg=COLOR["tarjeta"])
        self.transient(padre.winfo_toplevel())
        self.resultado = None
        icono, color = self.TIPOS.get(tipo, self.TIPOS["info"])
        cuerpo = tk.Frame(self, bg=COLOR["tarjeta"], padx=24, pady=20)
        cuerpo.pack(fill="both", expand=True)
        tk.Label(cuerpo, text=iconos.glifo(icono, self), font=iconos.fuente(self, 24), fg=COLOR[color],
                 bg=COLOR["tarjeta"]).grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, 16))
        tk.Label(cuerpo, text=titulo, font=tema.fs(14), fg=COLOR["texto"], bg=COLOR["tarjeta"],
                 anchor="w").grid(row=0, column=1, sticky="w")
        tk.Label(cuerpo, text=mensaje, font=tema.f(10), fg=COLOR["texto"], bg=COLOR["tarjeta"],
                 justify="left", wraplength=440, anchor="w").grid(row=1, column=1, sticky="w", pady=(6, 0))
        if detalle:
            caja = caja_texto(cuerpo, min(12, detalle.count("\n") + 2), solo_lectura=True, mono=True, width=60)
            escribir(caja, detalle)
            caja.grid(row=2, column=1, sticky="we", pady=(12, 0))
        pie = tk.Frame(self, bg=COLOR["fondo"], padx=20, pady=12)
        pie.pack(fill="x")
        botones = botones or [("Aceptar", True, "primario")]
        primero = None
        for texto, valor, variante in reversed(botones):
            boton = Boton(pie, texto, variante=variante, fondo=COLOR["fondo"],
                          comando=lambda v=valor: self._elegir(v))
            boton.pack(side="right", padx=(8, 0))
            primero = primero or boton
        self.bind("<Escape>", lambda e: self._elegir(None))
        self.protocol("WM_DELETE_WINDOW", lambda: self._elegir(None))
        centrar(self, padre)
        self.deiconify()
        self.grab_set()
        primero.focus_set()

    def _elegir(self, valor):
        self.resultado = valor
        self.grab_release()
        self.destroy()


def informar(padre, titulo: str, mensaje: str, tipo: str = "info", detalle: str = ""):
    dialogo = Dialogo(padre, titulo, mensaje, tipo, detalle=detalle)
    padre.wait_window(dialogo)


def confirmar(padre, titulo: str, mensaje: str, texto_si: str = "Confirmar", peligro: bool = False) -> bool:
    dialogo = Dialogo(padre, titulo, mensaje, "peligro" if peligro else "pregunta",
                      botones=[("Cancelar", False, "secundario"),
                               (texto_si, True, "primario")])
    padre.wait_window(dialogo)
    return dialogo.resultado is True


class Formulario(tk.Toplevel):
    """Formulario modal genérico.

    campos = [(clave, etiqueta, tipo, opciones)]  con tipo: entry | combo | texto | check | info
    `al_guardar(datos, formulario)` puede lanzar ValueError; los errores se muestran en el propio
    formulario y la ventana permanece abierta.
    """

    def __init__(self, padre, titulo: str, campos, al_guardar, valores: dict | None = None,
                 bloqueados=(), columnas: int = 1, subtitulo: str | None = None, icono: str | None = None,
                 texto_guardar: str = "Guardar", extra=None, ancho_campo: int = 34):
        super().__init__(padre)
        self.withdraw()
        self.title(titulo)
        self.transient(padre.winfo_toplevel())
        self.resizable(False, False)
        self.configure(bg=COLOR["fondo"])
        self.al_guardar = al_guardar
        self.widgets: dict[str, tuple] = {}
        valores = valores or {}

        cabecera_dialogo(self, titulo, subtitulo or "Los campos marcados con * son obligatorios.", icono)
        self._errores = tk.Label(self, text="", font=tema.f(9), fg=COLOR["peligro"], bg=COLOR["peligro_claro"],
                                 justify="left", anchor="w", padx=14, pady=8, wraplength=640)
        cuerpo = tarjeta(self, padding=18)
        cuerpo.pack(fill="both", expand=True, padx=16, pady=(14, 10))
        self._cuerpo = cuerpo
        fila_actual, columna_actual = 0, 0
        for clave, etiqueta, tipo, opciones in campos:
            ancho_completo = tipo == "texto" or columnas == 1
            if ancho_completo and columna_actual:
                fila_actual, columna_actual = fila_actual + 1, 0
            col = columna_actual * 2
            obligatorio = etiqueta.endswith("*")
            marco_etiqueta = ttk.Frame(cuerpo, style="Tarjeta.TFrame")
            marco_etiqueta.grid(row=fila_actual, column=col, sticky="nw" if tipo == "texto" else "w",
                                pady=4, padx=(0 if col == 0 else 18, 10))
            ttk.Label(marco_etiqueta, text=etiqueta.rstrip(" *"), style="Campo.TLabel").pack(side="left")
            if obligatorio:
                ttk.Label(marco_etiqueta, text=" *", style="Obligatorio.TLabel").pack(side="left")
            valor = valores.get(clave, "")
            if tipo == "texto":
                widget = caja_texto(cuerpo, 6, width=ancho_campo * columnas + 20)
                widget.insert("1.0", str(valor))
            elif tipo == "combo":
                widget = ttk.Combobox(cuerpo, values=opciones, state="readonly", width=ancho_campo - 3)
                if valor in opciones:
                    widget.set(valor)
            elif tipo == "check":
                variable = tk.BooleanVar(value=bool(valor) if valor != "" else bool(opciones))
                widget = ttk.Checkbutton(cuerpo, variable=variable, text="")
                widget.variable = variable
            elif tipo == "info":
                widget = ttk.Label(cuerpo, text=str(valor), style="Suave.TLabel")
            else:
                widget = ttk.Entry(cuerpo, width=ancho_campo)
                widget.insert(0, "" if valor is None else str(valor))
                if opciones:
                    Ayuda(widget, opciones, retraso_ms=300)
            span = columnas * 2 - 1 if tipo == "texto" else 1
            widget.grid(row=fila_actual, column=col + 1, columnspan=span, sticky="we" if tipo == "texto" else "w",
                        pady=4)
            if clave in bloqueados:
                widget.configure(state="disabled")
            self.widgets[clave] = (widget, tipo)
            if ancho_completo:
                fila_actual += 1
            else:
                columna_actual = (columna_actual + 1) % columnas
                if columna_actual == 0:
                    fila_actual += 1

        pie = tk.Frame(self, bg=COLOR["fondo"])
        pie.pack(fill="x", padx=16, pady=(0, 16))
        if extra:
            Boton(pie, extra[0], icono=extra[2] if len(extra) > 2 else None, variante="enlace",
                  fondo=COLOR["fondo"], comando=extra[1]).pack(side="left")
        self._guardar_btn = Boton(pie, texto_guardar, icono="guardar", variante="primario", comando=self._guardar)
        self._guardar_btn.pack(side="right")
        Boton(pie, "Cancelar", variante="secundario", comando=self.destroy).pack(side="right", padx=(0, 8))
        self._estado = tk.Label(pie, text="", font=tema.f(9), fg=COLOR["suave"], bg=COLOR["fondo"])
        self._estado.pack(side="right", padx=12)

        self.bind("<Escape>", lambda e: self.destroy())
        centrar(self, padre)
        self.deiconify()
        self.grab_set()
        for widget, tipo in self.widgets.values():
            if tipo == "entry" and str(widget.cget("state")) != "disabled":
                widget.focus_set()
                break

    def valores(self) -> dict:
        datos = {}
        for clave, (widget, tipo) in self.widgets.items():
            if tipo == "texto":
                datos[clave] = widget.get("1.0", "end").strip()
            elif tipo == "check":
                datos[clave] = widget.variable.get()
            elif tipo == "info":
                continue
            else:
                datos[clave] = widget.get().strip()
        return datos

    def mostrar_errores(self, mensaje: str):
        if mensaje:
            lineas = [l for l in mensaje.splitlines() if l.strip()]
            visibles = [f"•  {l}" for l in lineas[:5]]
            if len(lineas) > 5:
                visibles.append(f"…y {len(lineas) - 5} campo(s) más por revisar.")
            self._errores.configure(text="\n".join(visibles))
            self._errores.pack(fill="x", padx=16, pady=(12, 0), before=self._cuerpo)
        else:
            self._errores.pack_forget()
        self.update_idletasks()
        alto_pantalla = self.winfo_screenheight()
        if self.winfo_rooty() + self.winfo_reqheight() > alto_pantalla - 60:
            self.geometry(f"+{self.winfo_rootx()}+{max(0, alto_pantalla - self.winfo_reqheight() - 80)}")

    def ocupado(self, valor: bool, mensaje: str = "Guardando…"):
        self._guardar_btn.habilitar(not valor)
        self._estado.configure(text=mensaje if valor else "")

    def _guardar(self):
        try:
            self.mostrar_errores("")
            self.al_guardar(self.valores(), self)
        except ValueError as error:
            self.mostrar_errores(str(error))
