import time
import tkinter as tk
from tkinter import ttk

import config
from ui import tema
from ui.componentes import Boton, Tabla, caja_texto, encabezado_tarjeta, escribir, tarjeta
from ui.tema import COLOR
from ui.vistas.base import Vista, contenido_ficha, etiqueta_estado, ficha_libro

EJEMPLOS = ["náufrago solo en una isla", "sociedad que prohíbe los libros", "cómo formar buenos hábitos",
            "a boy wizard at a magic school"]

COLUMNAS = [("posicion", "#", 40, "center", False), ("similitud", "Similitud", 90, "center", False),
            ("titulo", "Título", 260), ("autor", "Autor", 170), ("anio", "Año", 60, "center", False),
            ("genero", "Género", 120, "w", False), ("estado", "Estado", 120, "w", False)]


class VistaBusqueda(Vista):
    titulo = "Buscar libros"
    subtitulo = "Búsqueda semántica: describe lo que buscas con tus palabras y se compara por significado."

    def construir(self):
        self._resultados: list[dict] = []
        self._excluir = None
        caja = tarjeta(self.cuerpo, 18)
        caja.pack(fill="x", pady=(0, 12))
        fila = tk.Frame(caja, bg=COLOR["tarjeta"])
        fila.pack(fill="x")
        self.consulta = ttk.Entry(fila, font=tema.f(12))
        self.consulta.pack(side="left", fill="x", expand=True, ipady=3)
        self.consulta.bind("<Return>", lambda e: self.buscar())
        ttk.Label(fila, text="Resultados", style="Campo.TLabel").pack(side="left", padx=(16, 6))
        self.cantidad = ttk.Spinbox(fila, from_=1, to=config.MAX_RESULTADOS_BUSQUEDA, width=4)
        self.cantidad.set(config.RESULTADOS_BUSQUEDA)
        self.cantidad.pack(side="left")
        self.solo_disponibles = tk.BooleanVar()
        ttk.Checkbutton(fila, text="Solo disponibles", variable=self.solo_disponibles).pack(side="left", padx=16)
        self.btn_buscar = Boton(fila, "Buscar", icono="buscar", variante="primario", comando=self.buscar)
        self.btn_buscar.pack(side="left")
        ejemplos = tk.Frame(caja, bg=COLOR["tarjeta"])
        ejemplos.pack(fill="x", pady=(12, 0))
        tk.Label(ejemplos, text="Prueba con:", font=tema.f(9), fg=COLOR["suave"], bg=COLOR["tarjeta"]).pack(side="left")
        for ejemplo in EJEMPLOS:
            Boton(ejemplos, ejemplo, variante="chip", tamano=9, padx=10, pady=3,
                  comando=lambda t=ejemplo: self._usar_ejemplo(t)).pack(side="left", padx=(8, 0))
        self.info = tk.Label(caja, text="", font=tema.f(9), fg=COLOR["suave"], bg=COLOR["tarjeta"], anchor="w")
        self.info.pack(fill="x", pady=(10, 0))

        cuerpo = ttk.Frame(self.cuerpo)
        cuerpo.pack(fill="both", expand=True)
        cuerpo.columnconfigure(0, weight=3, uniform="partes")
        cuerpo.columnconfigure(1, weight=2, minsize=tema.px(330), uniform="partes")
        cuerpo.rowconfigure(0, weight=1)
        caja_tabla = tarjeta(cuerpo, 12)
        caja_tabla.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.tabla = Tabla(caja_tabla, COLUMNAS, alto=14, icono_vacio="buscar",
                           mensaje_vacio="Escribe una descripción y pulsa Buscar.",
                           formatos={"similitud": lambda v: f"{v:.0%}", "estado": etiqueta_estado},
                           estilo_fila=lambda l: ("tenue",) if l.get("estado") != "Disponible" else ())
        self.tabla.pack(fill="both", expand=True)
        self.tabla.tree.bind("<<TreeviewSelect>>", lambda e: self._mostrar_detalle())

        detalle = tarjeta(cuerpo, 16)
        detalle.grid(row=0, column=1, sticky="nsew")
        encabezado_tarjeta(detalle, "Libro seleccionado")
        botones = tk.Frame(detalle, bg=COLOR["tarjeta"])
        botones.pack(side="bottom", fill="x", pady=(10, 0))
        self.btn_catalogo = Boton(botones, "Ver en catálogo", icono="libros", comando=self._ver_catalogo)
        self.btn_catalogo.pack(side="left")
        self.btn_prestar = Boton(botones, "Prestar", icono="prestar", variante="primario", comando=self._prestar)
        self.btn_prestar.pack(side="right")
        self.ficha = caja_texto(detalle, 18, solo_lectura=True)
        self.ficha.configure(bg=COLOR["tarjeta"], highlightthickness=0, padx=2)
        ficha_libro(self.ficha)
        self.ficha.pack(fill="both", expand=True)
        self._mostrar_detalle()

    def al_mostrar(self, consulta=None, excluir=None, **_):
        self._actualizar_info()
        if consulta:
            self._excluir = excluir
            self.consulta.delete(0, "end")
            self.consulta.insert(0, consulta)
            self.buscar()
        else:
            self.consulta.focus_set()

    def _actualizar_info(self, extra: str = ""):
        info = self.servicio.info_modelo()
        texto = f"Modelo: {info['modelo']} · {info['dispositivo']}"
        self.info.configure(text=texto + (f"   ·   {extra}" if extra else ""))

    def _usar_ejemplo(self, texto):
        self._excluir = None
        self.consulta.delete(0, "end")
        self.consulta.insert(0, texto)
        self.buscar()

    def buscar(self):
        texto = self.consulta.get().strip()
        if not texto:
            self.aviso("Escribe qué quieres buscar, por ejemplo «astronauta perdido en Marte».")
            return
        try:
            cantidad = max(1, min(int(self.cantidad.get()), config.MAX_RESULTADOS_BUSQUEDA))
        except ValueError:
            cantidad = config.RESULTADOS_BUSQUEDA
        solo = self.solo_disponibles.get()
        excluir = self._excluir
        self.btn_buscar.habilitar(False)

        def trabajo():
            inicio = time.perf_counter()
            resultados = self.servicio.buscar_libros(texto, cantidad + (1 if excluir else 0), solo)
            resultados = [r for r in resultados if r["id"] != excluir][:cantidad]
            return resultados, time.perf_counter() - inicio

        def listo(datos):
            resultados, segundos = datos
            for posicion, libro in enumerate(resultados, start=1):
                libro["posicion"] = posicion
            self._resultados = resultados
            self.tabla.cargar(resultados, mensaje_vacio="No se encontraron libros para esa descripción.",
                              conservar_seleccion=False)
            if resultados:
                self.tabla.seleccionar(resultados[0]["id"])
            self._mostrar_detalle()
            self._actualizar_info(f"{len(resultados)} resultado(s) en {segundos * 1000:.0f} ms")
            self.btn_buscar.habilitar(True)

        def fallo(error):
            self.btn_buscar.habilitar(True)
            self.app.manejar_error(error)
        self.tarea(trabajo, listo, "Buscando por significado…", fallo)

    def _mostrar_detalle(self):
        libro = self.tabla.fila_seleccionada()
        self.btn_catalogo.habilitar(bool(libro))
        self.btn_prestar.habilitar(bool(libro) and libro.get("estado") == "Disponible")
        escribir(self.ficha, contenido_ficha(libro, "Selecciona un resultado para ver la ficha completa."))

    def _ver_catalogo(self):
        libro = self.tabla.fila_seleccionada()
        if libro:
            self.app.navegar("libros", seleccionar=libro["id"])

    def _prestar(self):
        libro = self.tabla.fila_seleccionada()
        if libro:
            self.app.navegar("prestamos", libro_id=libro["id"])
