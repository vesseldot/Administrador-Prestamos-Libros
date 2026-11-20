"""Fondos ilustrados y animaciones suaves de la interfaz.

Todo se dibuja con `Canvas` (sin imágenes ni dependencias nuevas), con la paleta de `ui/tema.py`:

* `EscenaNocturna`: portada de la pantalla de acceso (sala de lectura de noche, con motas de luz).
* `Estanteria`: remate decorativo del menú lateral.
* `BandaTitulo`: cabecera de cada sección, con un pequeño estante dibujado.
* `Animacion`: interpolación temporal basada en `after`. Nunca bloquea el hilo de Tk, así que las
  tareas en segundo plano y los eventos del usuario siguen su curso mientras se anima.
"""
import math
import random
import time
import tkinter as tk
import tkinter.font as tkfont

from ui import tema
from ui.tema import COLOR


# ───────────────────────────── utilidades de color y tiempo ─────────────────────────────

def _rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def mezclar(a: str, b: str, t: float) -> str:
    """Color intermedio entre `a` (t=0) y `b` (t=1)."""
    t = max(0.0, min(1.0, t))
    ra, ga, ba = _rgb(a)
    rb, gb, bb = _rgb(b)
    return "#{:02X}{:02X}{:02X}".format(round(ra + (rb - ra) * t), round(ga + (gb - ga) * t),
                                         round(ba + (bb - ba) * t))


def suavizar(t: float) -> float:
    """Aceleración que frena al final (easeOutCubic): se siente natural al terminar."""
    return 1 - (1 - t) ** 3


class Animacion:
    """Llama a `paso(progreso)` con progreso de 0 a 1 durante `duracion_ms`, sin bloquear Tk."""

    def __init__(self, widget, duracion_ms: int, paso, fin=None, intervalo_ms: int = 16, curva=suavizar):
        self.widget, self.paso, self.fin, self.curva = widget, paso, fin, curva
        self.duracion = max(duracion_ms, 1)
        self.intervalo = intervalo_ms
        self._id = None
        self._activa = True
        self._inicio = time.monotonic()
        if not tema.ANIMACIONES:
            self._activa = False
            self._llamar(1.0)
            if fin:
                fin()
            return
        self._tic()

    def _llamar(self, progreso: float):
        try:
            self.paso(progreso)
        except tk.TclError:
            self._activa = False

    def _tic(self):
        if not self._activa:
            return
        try:
            if not self.widget.winfo_exists():
                return
        except tk.TclError:
            return
        t = min(1.0, (time.monotonic() - self._inicio) * 1000 / self.duracion)
        self._llamar(self.curva(t))
        if not self._activa:
            return
        if t >= 1.0:
            self._activa = False
            if self.fin:
                self.fin()
            return
        try:
            self._id = self.widget.after(self.intervalo, self._tic)
        except tk.TclError:
            self._activa = False

    def cancelar(self):
        self._activa = False
        if self._id is not None:
            try:
                self.widget.after_cancel(self._id)
            except tk.TclError:
                pass
            self._id = None


# ───────────────────────────── dibujo ─────────────────────────────

LOMOS = ["#4F46E5", "#3730A3", "#6366F1", "#312E81", "#4338CA", "#818CF8", "#5B54E8"]


def degradado(lienzo: tk.Canvas, x0, y0, x1, y1, arriba: str, abajo: str, etiqueta: str):
    alto = max(int(y1 - y0), 1)
    bandas = max(2, min(alto // 3, 140))
    for i in range(bandas):
        ya = y0 + alto * i // bandas
        yb = y0 + alto * (i + 1) // bandas + 1
        lienzo.create_rectangle(x0, ya, x1, yb, fill=mezclar(arriba, abajo, i / (bandas - 1)), outline="",
                                tags=etiqueta)


def dibujar_lomos(lienzo: tk.Canvas, x0: int, x1: int, base: int, alto_min: int, alto_max: int,
                  colores: list[str], semilla: int, etiqueta: str, dorado: str | None = None,
                  contorno: str = "", ancho_min: int = 12, ancho_max: int = 26):
    """Fila de lomos de libros apoyados en `base`. Es determinista: la misma semilla da el mismo estante."""
    azar = random.Random(semilla)
    x = x0
    while x < x1:
        color = azar.choice(colores)
        ancho = azar.randint(ancho_min, ancho_max)
        alto = azar.randint(alto_min, alto_max)
        if azar.random() < 0.07 and alto > 36:               # un libro inclinado
            inclinacion = int(alto * 0.2)
            lienzo.create_polygon(x, base, x + ancho, base, x + ancho + inclinacion, base - alto,
                                  x + inclinacion, base - alto, fill=color, outline=contorno, tags=etiqueta)
            x += ancho + inclinacion // 2 + 2
            continue
        derecha = min(x + ancho, x1)
        lienzo.create_rectangle(x, base - alto, derecha, base, fill=color, outline=contorno, tags=etiqueta)
        if dorado and ancho >= 14 and alto > 30:
            lienzo.create_rectangle(x, base - alto + 8, derecha, base - alto + 10, fill=dorado, outline="",
                                    tags=etiqueta)
            lienzo.create_rectangle(x, base - 10, derecha, base - 8, fill=dorado, outline="", tags=etiqueta)
            if azar.random() < 0.5:
                lienzo.create_rectangle(x + 3, base - alto // 2 - 7, derecha - 3, base - alto // 2 + 7,
                                        fill=mezclar(color, dorado, 0.35), outline="", tags=etiqueta)
        x += ancho + azar.choice((0, 0, 1, 2))


# ───────────────────────────── pantalla de acceso ─────────────────────────────

class EscenaNocturna(tk.Canvas):
    """Sala de lectura de noche: ventana en arco, estante con libros y motas de luz que suben despacio."""

    def __init__(self, padre, titulo: str, lineas: list[str]):
        super().__init__(padre, bg=COLOR["lateral"], highlightthickness=0, width=10, height=10)
        self._titulo, self._lineas = titulo, lineas
        self._motas: list[dict] = []
        self._pendiente = None
        self._ciclo = None
        self._ancho = self._alto = 0
        self.bind("<Configure>", self._programar_dibujo)
        if tema.ANIMACIONES:
            self._ciclo = self.after(60, self._mover)

    def destroy(self):
        for ident in (self._pendiente, self._ciclo):
            if ident:
                try:
                    self.after_cancel(ident)
                except tk.TclError:
                    pass
        super().destroy()

    def _programar_dibujo(self, evento):
        if (evento.width, evento.height) == (self._ancho, self._alto):
            return
        self._ancho, self._alto = evento.width, evento.height
        if self._pendiente:
            self.after_cancel(self._pendiente)
        self._pendiente = self.after(40, self._dibujar)

    def _dibujar(self):
        self._pendiente = None
        ancho, alto = self.winfo_width(), self.winfo_height()
        if ancho < 50 or alto < 50:
            return
        self.delete("escena")
        cielo_alto = mezclar(COLOR["lateral"], "#000000", 0.38)
        cielo_bajo = mezclar(COLOR["lateral_activo"], COLOR["lateral"], 0.45)
        degradado(self, 0, 0, ancho, alto, cielo_alto, cielo_bajo, "escena")

        base = alto - 28
        centro_x = ancho * 0.68
        radio = min(ancho, alto) * 0.5
        for i in range(20, 0, -1):                             # resplandor de la ventana
            r = radio * i / 20
            color = mezclar(mezclar(cielo_alto, cielo_bajo, 0.5), "#6366F1", 0.16 * (1 - i / 20) ** 1.6)
            self.create_oval(centro_x - r, alto * 0.36 - r, centro_x + r, alto * 0.36 + r, fill=color,
                             outline="", tags="escena")

        tope_ventana, fondo_ventana = alto * 0.09, base - 190
        mitad = min(130, (fondo_ventana - tope_ventana) / 3.3)
        if ancho > 620 and mitad > 50:
            self._ventana(centro_x, tope_ventana, fondo_ventana, mitad)

        fila_trasera = [mezclar(c, cielo_bajo, 0.62) for c in LOMOS]
        fila_delantera = [mezclar(c, cielo_bajo, 0.30) for c in LOMOS]
        dorado = mezclar(COLOR["dorado"], cielo_bajo, 0.45)
        dibujar_lomos(self, -6, ancho + 6, base, 110, 190, fila_trasera, 11, "escena", None, ancho_min=14,
                      ancho_max=30)
        dibujar_lomos(self, -10, ancho + 6, base, 62, 128, fila_delantera, 29, "escena", dorado)
        self.create_rectangle(0, base, ancho, alto, fill=mezclar("#0B0A24", cielo_bajo, 0.25), outline="",
                              tags="escena")
        self.create_rectangle(0, base, ancho, base + 3, fill=mezclar(COLOR["dorado"], cielo_bajo, 0.55), outline="",
                              tags="escena")

        x = max(48, int(ancho * 0.08))
        y = alto * 0.36
        self.create_text(x, y, text=self._titulo, font=tema.fs(46), fill="#FFFFFF", anchor="sw", tags="escena")
        self.create_rectangle(x + 2, y + 18, x + 58, y + 20, fill=COLOR["dorado"], outline="", tags="escena")
        self.create_text(x, y + 40, text="\n\n".join(self._lineas), font=tema.f(12), fill=COLOR["lateral_texto"],
                         anchor="nw", width=max(240, int(ancho * 0.40)), tags="escena", justify="left")
        self.tag_lower("escena")
        self._sembrar_motas(ancho, base)

    def _ventana(self, cx, y0, y1, mitad):
        marco = mezclar(COLOR["lateral_activo"], "#A5B4FC", 0.22)
        cristal = mezclar("#A5B4FC", COLOR["lateral"], 0.62)
        for borde, color in ((0, marco), (9, cristal)):
            izq, der, tope = cx - mitad + borde, cx + mitad - borde, y0 + borde
            self.create_arc(izq, tope, der, tope + 2 * (mitad - borde), start=0, extent=180, fill=color,
                            outline="", tags="escena")
            self.create_rectangle(izq, tope + mitad - borde, der, y1 - borde, fill=color, outline="", tags="escena")
        r_int = mitad - 9
        arranque = y0 + 9 + r_int
        self.create_line(cx, y0 + 9, cx, y1 - 9, fill=marco, width=5, tags="escena")
        for k in (1, 2):
            yy = arranque + (y1 - arranque) * k / 3
            self.create_line(cx - r_int, yy, cx + r_int, yy, fill=marco, width=5, tags="escena")
        luna_x, luna_y, luna_r = cx - r_int * 0.5, arranque - r_int * 0.1, r_int * 0.2
        self.create_oval(luna_x - luna_r, luna_y - luna_r, luna_x + luna_r, luna_y + luna_r, fill="#F4E6B8",
                         outline="", tags="escena")
        self.create_oval(luna_x - luna_r * 0.55, luna_y - luna_r * 1.15, luna_x + luna_r * 1.2,
                         luna_y + luna_r * 0.75, fill=cristal, outline="", tags="escena")
        self.create_rectangle(cx - mitad - 8, y1, cx + mitad + 8, y1 + 8, fill=marco, outline="", tags="escena")

    def _sembrar_motas(self, ancho, base):
        for mota in self._motas:
            self.delete(mota["id"])
        self._motas = []
        azar = random.Random(7)
        for _ in range(26 if ancho > 500 else 12):
            radio = azar.choice((1.2, 1.6, 2.0, 2.6))
            x, y = azar.uniform(0, ancho), azar.uniform(0, base)
            color = mezclar("#F4E6B8", COLOR["lateral"], azar.uniform(0.35, 0.8))
            ident = self.create_oval(x - radio, y - radio, x + radio, y + radio, fill=color, outline="",
                                     tags="mota")
            self._motas.append({"id": ident, "x": x, "y": y, "r": radio, "vy": azar.uniform(0.12, 0.38),
                                "fase": azar.uniform(0, 6.28), "tope": base})

    def _mover(self):
        try:
            if not self.winfo_exists():
                return
            if self.winfo_viewable():
                for m in self._motas:
                    m["fase"] += 0.025
                    dx = math.sin(m["fase"]) * 0.22
                    m["x"] += dx
                    m["y"] -= m["vy"]
                    if m["y"] < -6:
                        m["y"] = m["tope"]
                    self.coords(m["id"], m["x"] - m["r"], m["y"] - m["r"], m["x"] + m["r"], m["y"] + m["r"])
            self._ciclo = self.after(45, self._mover)
        except tk.TclError:
            pass


# ───────────────────────────── menú lateral ─────────────────────────────

class Estanteria(tk.Canvas):
    """Remate del menú lateral: una fila de libros que se pierde en la penumbra."""

    def __init__(self, padre):
        super().__init__(padre, bg=COLOR["lateral"], highlightthickness=0, height=40)
        self._tamano = (0, 0)
        self._pendiente = None
        self.bind("<Configure>", self._programar)

    def _programar(self, evento):
        if (evento.width, evento.height) == self._tamano:
            return
        self._tamano = (evento.width, evento.height)
        if self._pendiente:
            self.after_cancel(self._pendiente)
        self._pendiente = self.after(40, self._dibujar)

    def _dibujar(self):
        self._pendiente = None
        ancho, alto = self.winfo_width(), self.winfo_height()
        self.delete("arte")
        if alto < 40:
            return
        base = alto - 6
        fondo = COLOR["lateral"]
        colores = [mezclar(c, fondo, 0.72) for c in LOMOS]
        dorado = mezclar(COLOR["dorado"], fondo, 0.78)
        dibujar_lomos(self, 6, ancho - 6, base, 26, min(96, alto - 18), colores, 5, "arte", dorado,
                      ancho_min=10, ancho_max=20)
        self.create_rectangle(0, base, ancho, base + 2, fill=mezclar(COLOR["dorado"], fondo, 0.7), outline="",
                              tags="arte")


# ───────────────────────────── cabecera de cada sección ─────────────────────────────

class BandaTitulo(tk.Canvas):
    """Título de la sección con su subtítulo, las acciones a la derecha y un estante dibujado de fondo."""

    ANCHO_ARTE = 200

    def __init__(self, padre, titulo: str, subtitulo: str = "", semilla: int = 0):
        super().__init__(padre, bg=COLOR["banda"], highlightthickness=0, height=tema.px(90))
        self._titulo, self._subtitulo, self._semilla = titulo, subtitulo, semilla
        self.acciones = tk.Frame(self, bg=COLOR["banda"])
        self._ventana = self.create_window(0, 0, window=self.acciones, anchor="e")
        self._ancho = 0
        self._animacion = None
        self._pendiente = None
        self._acento = None
        self._ajustes = 0
        self._largo_acento = tema.px(76)
        self.bind("<Configure>", self._programar)
        self.acciones.bind("<Configure>", lambda e: self._programar(None), add="+")

    def _programar(self, evento):
        if evento is not None and evento.width == self._ancho:
            return
        if evento is not None:
            self._ancho = evento.width
            self._ajustes = 0
        if self._pendiente:
            self.after_cancel(self._pendiente)
        self._pendiente = self.after(15, self._dibujar)

    def _dibujar(self):
        self._pendiente = None
        ancho, alto = self.winfo_width(), self.winfo_height()
        if ancho < 100:
            return
        self.delete("arte", "texto", "acento")
        arte = self.ANCHO_ARTE if ancho > tema.px(900) else 0
        if arte:
            colores = [mezclar(c, COLOR["banda"], 0.84) for c in LOMOS]
            dibujar_lomos(self, ancho - arte, ancho, alto, 30, 70, colores, self._semilla + 3, "arte",
                          mezclar(COLOR["dorado"], COLOR["banda"], 0.6), ancho_min=10, ancho_max=20)
        self.create_line(0, alto - 1, ancho, alto - 1, fill=COLOR["banda_trazo"], tags="acento")
        self._acento = self.create_line(0, alto - 2, 0, alto - 2, fill=COLOR["primario"], width=3, tags="acento")

        self.coords(self._ventana, ancho - arte - tema.px(24), alto // 2)
        espacio = ancho - arte - self.acciones.winfo_reqwidth() - tema.px(80)
        titulo = self.create_text(tema.px(30), 0, text=self._titulo, font=tema.fs(23), fill=COLOR["texto"],
                                  anchor="nw", tags="texto")
        sub = self.create_text(tema.px(30), 0, text=self._subtitulo, font=tema.f(10), fill=COLOR["suave"],
                               anchor="nw", width=max(220, espacio), tags="texto") if self._subtitulo else None
        alto_titulo = self.bbox(titulo)[3] - self.bbox(titulo)[1]
        alto_sub = (self.bbox(sub)[3] - self.bbox(sub)[1]) if sub else 0
        necesario = alto_titulo + alto_sub + (tema.px(3) if sub else 0) + tema.px(28)
        objetivo = max(tema.px(90), necesario)          # la banda crece si el subtítulo ocupa más líneas
        if abs(objetivo - alto) > 1 and self._ajustes < 2:
            self._ajustes += 1
            self.configure(height=objetivo)
            self._pendiente = self.after(5, self._dibujar)
            return
        self._ajustes = 0
        y0 = max(tema.px(8), (alto - alto_titulo - alto_sub - (tema.px(3) if sub else 0)) // 2)
        self.coords(titulo, tema.px(30), y0)
        if sub:
            self.coords(sub, tema.px(31), y0 + alto_titulo + tema.px(3))
        self.tag_raise(self._ventana)
        self._largo_acento = tema.px(76)
        self.coords(self._acento, 0, alto - 2, self._largo_acento, alto - 2)

    def revelar(self):
        """El acento de la parte inferior se extiende al entrar en la sección."""
        if self._animacion:
            self._animacion.cancelar()
        largo = self._largo_acento

        def paso(p):
            alto = self.winfo_height()
            if self._acento is not None and alto > 20:
                self.coords(self._acento, 0, alto - 2, max(1, largo * p), alto - 2)
        self._animacion = Animacion(self, 420, paso)
