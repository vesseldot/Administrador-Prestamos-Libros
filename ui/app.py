"""Ventana principal: menú lateral, panel dinámico y servicios comunes de la interfaz."""
import logging
import time
import tkinter as tk
from tkinter import ttk

import config
from servicios import describir_error
from ui import iconos, tema
from ui.acceso import PantallaAcceso, dibujar_logo
from ui.componentes import Notificador, informar
from ui.fondos import Estanteria
from ui.tareas import GestorTareas
from ui.tema import COLOR

log = logging.getLogger("biblioteca")

SECCIONES = [
    ("dashboard", "Dashboard", "dashboard"),
    ("libros", "Libros", "libros"),
    ("busqueda", "Buscar libros", "buscar"),
    ("personas", "Personas", "personas"),
    ("prestamos", "Préstamos", "prestamos"),
    ("con_prestamo", "Personas con préstamos", "con_prestamo"),
    ("configuracion", "Configuración", "configuracion"),
]


class BotonLateral(tk.Frame):
    def __init__(self, padre, texto, icono, comando):
        super().__init__(padre, bg=COLOR["lateral"], cursor="hand2")
        self._activo = False
        self._marca = tk.Frame(self, bg=COLOR["lateral"], width=4)
        self._marca.pack(side="left", fill="y")
        self._icono = tk.Label(self, text=iconos.glifo(icono, self), font=iconos.fuente(self, 13),
                               fg=COLOR["lateral_texto"], bg=COLOR["lateral"], width=2)
        self._icono.pack(side="left", padx=(14, 10), pady=10)
        self._texto = tk.Label(self, text=texto, font=tema.f(10), fg=COLOR["lateral_texto"],
                               bg=COLOR["lateral"], anchor="w")
        self._texto.pack(side="left", fill="x", expand=True)
        for widget in (self, self._icono, self._texto):
            widget.bind("<Button-1>", lambda e: comando())
            widget.bind("<Enter>", lambda e: self._pintar(hover=True))
            widget.bind("<Leave>", lambda e: self._pintar())

    def _pintar(self, hover=False):
        fondo = COLOR["lateral_activo"] if self._activo else (COLOR["lateral_hover"] if hover else COLOR["lateral"])
        texto = "white" if self._activo or hover else COLOR["lateral_texto"]
        for widget in (self, self._icono, self._texto):
            widget.configure(bg=fondo)
        self._icono.configure(fg=texto)
        self._texto.configure(fg=texto, font=tema.f(10, "bold") if self._activo else tema.f(10))
        self._marca.configure(bg="#A5B4FC" if self._activo else fondo)

    def activar(self, valor: bool):
        self._activo = valor
        self._pintar()


class AplicacionBiblioteca(tk.Tk):
    def __init__(self, servicio):
        super().__init__()
        self.withdraw()
        self.title("Biblioteca · Administrador de préstamos")
        tema.aplicar_tema(self)
        ancho_pantalla, alto_pantalla = self.winfo_screenwidth(), self.winfo_screenheight()
        ancho = min(int(ancho_pantalla * 0.94), tema.px(1440))
        alto = min(int(alto_pantalla * 0.88), tema.px(900))
        self.geometry(f"{ancho}x{alto}+{(ancho_pantalla - ancho) // 2}+{max((alto_pantalla - alto) // 3, 0)}")
        self.minsize(min(tema.px(1100), ancho), min(tema.px(660), alto))
        self.servicio = servicio
        self.notificador = Notificador(self)
        self.tareas = GestorTareas(self, self._estado_tareas, self.manejar_error)
        self.acceso = servicio.acceso
        self._ultima_actividad = time.monotonic()
        self._bloqueado = True
        self._vistas: dict[str, ttk.Frame] = {}
        self._botones: dict[str, BotonLateral] = {}
        self._actual: str | None = None
        self._modelo_listo = False

        self._construir_lateral()
        derecha = ttk.Frame(self)
        derecha.pack(side="left", fill="both", expand=True)
        self._construir_barra_estado(derecha)
        self.contenedor = ttk.Frame(derecha)
        self.contenedor.pack(fill="both", expand=True)

        for evento in ("<Any-KeyPress>", "<Any-ButtonPress>", "<Motion>", "<MouseWheel>"):
            self.bind_all(evento, self._registrar_actividad, add="+")
        self.protocol("WM_DELETE_WINDOW", self.cerrar)
        self.report_callback_exception = self._excepcion_no_controlada
        self.after(30_000, self._revisar_inactividad)
        self.deiconify()
        self._mostrar_acceso(primera_vez=True)

    def _construir_lateral(self):
        lateral = tk.Frame(self, bg=COLOR["lateral"], width=tema.px(236))
        lateral.pack(side="left", fill="y")
        lateral.pack_propagate(False)
        marca = tk.Frame(lateral, bg=COLOR["lateral"], padx=20, pady=22)
        marca.pack(fill="x")
        logo = tk.Canvas(marca, width=46, height=46, bg=COLOR["lateral"], highlightthickness=0)
        logo.pack(side="left")
        dibujar_logo(logo)
        textos = tk.Frame(marca, bg=COLOR["lateral"])
        textos.pack(side="left", padx=(12, 0))
        tk.Label(textos, text="Biblioteca", font=tema.fs(17), fg="white", bg=COLOR["lateral"]).pack(anchor="w")
        tk.Label(textos, text="Gestión de préstamos", font=tema.f(8), fg=COLOR["lateral_tenue"],
                 bg=COLOR["lateral"]).pack(anchor="w")
        tk.Frame(lateral, bg=COLOR["lateral_hover"], height=1).pack(fill="x", padx=20, pady=(0, 10))
        for clave, texto, icono in SECCIONES:
            boton = BotonLateral(lateral, texto, icono, lambda c=clave: self.navegar(c))
            boton.pack(fill="x")
            self._botones[clave] = boton

        pie = tk.Frame(lateral, bg=COLOR["lateral"], padx=20, pady=18)
        pie.pack(side="bottom", fill="x")
        self._lbl_redis = tk.Label(pie, text="● Redis", font=tema.f(9), fg=COLOR["lateral_texto"],
                                   bg=COLOR["lateral"], anchor="w")
        self._lbl_redis.pack(fill="x")
        self._lbl_modelo = tk.Label(pie, text="● Modelo: cargando…", font=tema.f(9), fg=COLOR["lateral_texto"],
                                    bg=COLOR["lateral"], anchor="w", justify="left", wraplength=200)
        self._lbl_modelo.pack(fill="x", pady=(4, 14))
        bloquear = tk.Label(pie, text=f"{iconos.glifo('candado', pie)}", font=iconos.fuente(pie, 11),
                            fg=COLOR["lateral_texto"], bg=COLOR["lateral_hover"], padx=10, pady=8, cursor="hand2")
        bloquear.pack(side="left")
        texto_bloquear = tk.Label(pie, text="Bloquear sesión", font=tema.f(10), fg=COLOR["lateral_texto"],
                                  bg=COLOR["lateral_hover"], pady=8, padx=10, anchor="w", cursor="hand2")
        texto_bloquear.pack(side="left", fill="x", expand=True)
        for widget in (bloquear, texto_bloquear):
            widget.bind("<Button-1>", lambda e: self.bloquear())
        Estanteria(lateral).pack(fill="both", expand=True, pady=(14, 0))

    def _construir_barra_estado(self, padre):
        barra = tk.Frame(padre, bg=COLOR["tarjeta"], highlightthickness=1, highlightbackground=COLOR["borde"],
                         padx=16, pady=6)
        barra.pack(side="bottom", fill="x")
        self._lbl_estado = tk.Label(barra, text="Listo", font=tema.f(9), fg=COLOR["suave"], bg=COLOR["tarjeta"])
        self._lbl_estado.pack(side="left")
        self._progreso = ttk.Progressbar(barra, mode="indeterminate", length=160)
        tk.Label(barra, text=self.servicio.descripcion_conexion(), font=tema.f(9), fg=COLOR["tenue"],
                 bg=COLOR["tarjeta"]).pack(side="right")

    def _excepcion_no_controlada(self, tipo, valor, rastro):
        log.error("Excepción no controlada en la interfaz", exc_info=(tipo, valor, rastro))
        self.manejar_error(valor)

    def mensaje_estado(self, texto: str):
        self._lbl_estado.configure(text=texto)

    def _estado_tareas(self, pendientes: int, mensaje: str):
        if pendientes:
            if mensaje:
                self._lbl_estado.configure(text=mensaje)
            self.configure(cursor="watch")
            if not self._progreso.winfo_ismapped():
                self._progreso.pack(side="left", padx=14)
                self._progreso.start(12)
        else:
            self._lbl_estado.configure(text="Listo")
            self.configure(cursor="")
            self._progreso.stop()
            self._progreso.pack_forget()

    def manejar_error(self, error: Exception):
        descripcion = describir_error(error)
        if descripcion["categoria"] == "redis":
            self._actualizar_redis(False)
        informar(self, descripcion["titulo"], descripcion["mensaje"], descripcion["tipo"])

    def _actualizar_redis(self, conectado: bool | None = None):
        if conectado is None:
            conectado = self.servicio.redis_disponible()
        self._lbl_redis.configure(text="● Redis conectado" if conectado else "● Redis sin conexión",
                                  fg="#6EE7B7" if conectado else "#FCA5A5")
        return conectado

    def actualizar_modelo(self):
        estado = self.servicio.info_modelo()["dispositivo"] if self._modelo_listo else "cargando…"
        self._lbl_modelo.configure(text=f"● {self.servicio.clave_modelo}\n   {estado}",
                                   fg="#6EE7B7" if self._modelo_listo else COLOR["lateral_texto"])

    def _crear_vista(self, clave: str):
        from ui.vistas.busqueda import VistaBusqueda
        from ui.vistas.configuracion import VistaConfiguracion
        from ui.vistas.dashboard import VistaDashboard
        from ui.vistas.libros import VistaLibros
        from ui.vistas.personas import VistaPersonas
        from ui.vistas.personas_prestamos import VistaPersonasConPrestamo
        from ui.vistas.prestamos import VistaPrestamos
        clases = {"dashboard": VistaDashboard, "libros": VistaLibros, "busqueda": VistaBusqueda,
                  "personas": VistaPersonas, "prestamos": VistaPrestamos,
                  "con_prestamo": VistaPersonasConPrestamo, "configuracion": VistaConfiguracion}
        return clases[clave](self.contenedor, self)

    def navegar(self, clave: str, **contexto):
        if self._bloqueado:
            return
        if clave not in self._vistas:
            self._vistas[clave] = self._crear_vista(clave)
        if self._actual and self._actual != clave:
            self._vistas[self._actual].pack_forget()
        vista = self._vistas[clave]
        cambia = self._actual != clave
        if cambia:
            vista.pack(fill="both", expand=True)
        self._actual = clave
        for nombre, boton in self._botones.items():
            boton.activar(nombre == clave)
        try:
            vista.al_mostrar(**contexto)
        except Exception as error:  # noqa: BLE001
            log.exception("Error al mostrar la vista %s", clave)
            self.manejar_error(error)
        if cambia:
            vista.revelar()

    def refrescar_vista_actual(self):
        if self._actual and self._actual in self._vistas:
            self._vistas[self._actual].al_mostrar()

    def _al_entrar(self, primera_vez: bool):
        self._bloqueado = False
        self._ultima_actividad = time.monotonic()
        self._actualizar_redis()
        if primera_vez:
            self.navegar("dashboard")
            self._precargar_modelo()
        else:
            self.refrescar_vista_actual()

    def ofrecer_descarga(self, clave: str, al_completar=None):
        from ui.descarga_modelo import DialogoDescargaModelo

        def posponer():
            self._lbl_modelo.configure(text=f"● {clave}\n   no descargado", fg="#FCD34D")
            self.notificador.mostrar("La búsqueda semántica y las altas de libros necesitan el modelo. "
                                     "Puedes descargarlo en Configuración › Modelo semántico.", "aviso", 7000)
        DialogoDescargaModelo(self, self, clave, al_completar, posponer)

    def _precargar_modelo(self):
        self.actualizar_modelo()
        if self.servicio.modelo_pendiente_de_descarga():
            self.ofrecer_descarga(self.servicio.clave_modelo, self._precargar_modelo)
            return

        def listo(_):
            self._modelo_listo = True
            self.actualizar_modelo()
            self.tareas.ejecutar(self.servicio.revisar_sincronizacion, self._avisar_sincronizacion,
                                 al_error=lambda e: log.warning("Revisión de sincronización fallida: %s", e),
                                 mensaje="Revisando sincronización Redis ↔ Chroma…")

        def fallo(error):
            self._lbl_modelo.configure(text=f"● {self.servicio.clave_modelo}\n   no disponible", fg="#FCA5A5")
            self.manejar_error(error)

        self.tareas.ejecutar(self.servicio.precargar_modelo, listo,
                             fallo, mensaje="Cargando el modelo de embeddings en memoria…")

    def _avisar_sincronizacion(self, informe):
        if not informe.consistente:
            self.notificador.mostrar("Redis y Chroma tienen diferencias. Revísalas en Configuración › "
                                     "Sincronización.", "aviso", 7000)

    def _mostrar_acceso(self, primera_vez=False, motivo=""):
        self._bloqueado = True
        PantallaAcceso(self, self.acceso, lambda: self._al_entrar(primera_vez), motivo)

    def bloquear(self, motivo: str = "Sesión bloqueada. Ingresa la contraseña para continuar."):
        if not self._bloqueado:
            for ventana in self.winfo_children():
                if isinstance(ventana, tk.Toplevel):
                    ventana.destroy()
            self._mostrar_acceso(motivo=motivo)

    def _registrar_actividad(self, _evento=None):
        self._ultima_actividad = time.monotonic()

    def _revisar_inactividad(self):
        inactivo = time.monotonic() - self._ultima_actividad
        if not self._bloqueado and inactivo > config.MINUTOS_BLOQUEO_INACTIVIDAD * 60:
            self.bloquear("Sesión bloqueada por inactividad.")
        self.after(30_000, self._revisar_inactividad)

    def cerrar(self):
        self.tareas.cerrar()
        self.destroy()
