import tkinter as tk
from tkinter import ttk

from ui import tema
from ui.componentes import Boton, Tabla, confirmar, encabezado_tarjeta, tarjeta
from ui.tema import COLOR
from ui.vistas.base import Vista, etiqueta_estado, fecha_corta
from validaciones import normalizar_texto

COLUMNAS_ACTIVOS = [("libro_id", "Libro", 75, "w", False), ("titulo", "Título", 220),
                    ("fecha_prestamo", "Prestado", 120, "w", False), ("fecha_limite", "Vence", 90, "w", False),
                    ("estado_visible", "Estado", 95, "w", False)]
COLUMNAS_HISTORIAL = [("titulo", "Título", 220), ("fecha_prestamo", "Prestado", 120, "w", False),
                      ("fecha_devolucion", "Devuelto", 120, "w", False), ("estado_visible", "Estado", 95, "w", False)]
COLUMNAS_DISPONIBLES = [("id", "ID", 75, "w", False), ("titulo", "Título", 230), ("autor", "Autor", 160),
                        ("similitud", "Similitud", 80, "center", False)]
FORMATOS = {"fecha_prestamo": fecha_corta, "fecha_devolucion": fecha_corta, "estado_visible": etiqueta_estado,
            "similitud": lambda v: f"{v:.0%}" if isinstance(v, float) else ""}


def estilo_prestamo(prestamo):
    if prestamo.get("vencido"):
        return ("alerta",)
    return ("tenue",) if prestamo.get("estado") == "devuelto" else ()


class VistaPrestamos(Vista):
    titulo = "Préstamos"
    subtitulo = "Registra préstamos de hasta tres libros por persona y sus devoluciones."

    def construir(self):
        self.accion("Actualizar", "refrescar", self.refrescar)
        self._personas: list[dict] = []
        self._opciones: list[dict] = []
        self._libro_preseleccionado = None
        self._disponibles: list[dict] = []

        superior = tarjeta(self.cuerpo, 16)
        superior.pack(fill="x", pady=(0, 12))
        ttk.Label(superior, text="Persona", style="Campo.TLabel").pack(side="left")
        self.combo = ttk.Combobox(superior, width=58)
        self.combo.pack(side="left", padx=10)
        self.combo.bind("<KeyRelease>", self._filtrar_personas)
        self.combo.bind("<<ComboboxSelected>>", lambda e: self._cargar_persona())
        self.combo.bind("<Return>", lambda e: self._elegir_primera())
        self.barra = ttk.Progressbar(superior, maximum=self.servicio.max_libros_por_persona, length=140,
                                     style="CupoOk.Horizontal.TProgressbar")
        self.barra.pack(side="right")
        self.cupo = ttk.Label(superior, text="", style="Suave.TLabel")
        self.cupo.pack(side="right", padx=12)

        cuerpo = ttk.Frame(self.cuerpo)
        cuerpo.pack(fill="both", expand=True)
        cuerpo.columnconfigure(0, weight=1, uniform="c")
        cuerpo.columnconfigure(1, weight=1, uniform="c")
        cuerpo.rowconfigure(0, weight=1)

        izquierda = ttk.Frame(cuerpo)
        izquierda.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        activos = tarjeta(izquierda, 14)
        activos.pack(fill="both", expand=True)
        encabezado_tarjeta(activos, "Libros que tiene prestados", "Selecciona uno o varios (Ctrl+clic) para devolver.")
        pie = tk.Frame(activos, bg=COLOR["tarjeta"])
        pie.pack(side="bottom", fill="x", pady=(10, 0))
        self.btn_devolver = Boton(pie, "Devolver seleccionados", icono="devolver", variante="primario",
                                  comando=self.devolver)
        self.btn_devolver.pack(side="right")
        self.btn_devolver_todos = Boton(pie, "Devolver todos", icono="devolver", comando=self.devolver_todos)
        self.btn_devolver_todos.pack(side="right", padx=8)
        self.tabla_activos = Tabla(activos, COLUMNAS_ACTIVOS, seleccion="extended", alto=6,
                                   mensaje_vacio="Elige una persona para ver sus préstamos.",
                                   icono_vacio="prestamos", formatos=FORMATOS, estilo_fila=estilo_prestamo)
        self.tabla_activos.pack(fill="both", expand=True)
        self.tabla_activos.tree.bind("<<TreeviewSelect>>", lambda e: self._habilitar())

        historial = tarjeta(izquierda, 14)
        historial.pack(fill="both", expand=True, pady=(12, 0))
        encabezado_tarjeta(historial, "Historial de la persona", "Los préstamos devueltos se conservan.")
        self.tabla_historial = Tabla(historial, COLUMNAS_HISTORIAL, alto=5, mensaje_vacio="Sin historial.",
                                     icono_vacio="reloj", formatos=FORMATOS, estilo_fila=estilo_prestamo)
        self.tabla_historial.pack(fill="both", expand=True)

        derecha = tarjeta(cuerpo, 14)
        derecha.grid(row=0, column=1, sticky="nsew")
        encabezado_tarjeta(derecha, "Libros disponibles", "Filtra por texto o busca por significado.")
        buscador = tk.Frame(derecha, bg=COLOR["tarjeta"])
        buscador.pack(fill="x", pady=(0, 8))
        self.busqueda = ttk.Entry(buscador)
        self.busqueda.pack(side="left", fill="x", expand=True)
        self.busqueda.bind("<KeyRelease>", lambda e: self._filtrar_disponibles())
        self.busqueda.bind("<Return>", lambda e: self.buscar_semantico())
        Boton(buscador, "Por significado", icono="buscar", comando=self.buscar_semantico,
              ayuda="Usa el modelo de embeddings sobre las sinopsis (Enter).").pack(side="left", padx=(8, 0))
        Boton(buscador, "Todos", variante="enlace", comando=self._ver_todos).pack(side="left", padx=(4, 0))
        pie_derecha = tk.Frame(derecha, bg=COLOR["tarjeta"])
        pie_derecha.pack(side="bottom", fill="x", pady=(10, 0))
        self.seleccion_info = tk.Label(pie_derecha, text="", font=tema.f(9), fg=COLOR["suave"], bg=COLOR["tarjeta"])
        self.seleccion_info.pack(side="left")
        self.btn_prestar = Boton(pie_derecha, "Prestar seleccionados", icono="prestar", variante="primario",
                                 comando=self.prestar)
        self.btn_prestar.pack(side="right")
        self.tabla_disponibles = Tabla(derecha, COLUMNAS_DISPONIBLES, seleccion="extended", alto=12,
                                       mensaje_vacio="No hay libros disponibles.", icono_vacio="libros",
                                       formatos=FORMATOS)
        self.tabla_disponibles.pack(fill="both", expand=True)
        self.tabla_disponibles.tree.bind("<<TreeviewSelect>>", lambda e: self._habilitar())
        self._habilitar()

    def al_mostrar(self, persona_id=None, libro_id=None, **_):
        actual = persona_id or self._persona_id()
        self._libro_preseleccionado = libro_id
        self._cargar_personas()
        if actual:
            self._seleccionar_persona(actual)
        self._cargar_persona()
        self._ver_todos()

    refrescar = al_mostrar

    def _etiqueta(self, persona: dict) -> str:
        return (f"{persona['id']} — {persona['nombre_completo']} ({persona['tipo_usuario']}) "
                f"[{persona['num_prestamos']}/{self.servicio.max_libros_por_persona}]")

    def _cargar_personas(self):
        self._personas = self.servicio.listar_personas()
        self._opciones = list(self._personas)
        self.combo.configure(values=[self._etiqueta(p) for p in self._opciones])

    def _filtrar_personas(self, evento):
        if evento.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        consulta = normalizar_texto(self.combo.get())
        self._opciones = [p for p in self._personas
                          if all(t in normalizar_texto(self._etiqueta(p)) for t in consulta.split())]
        self.combo.configure(values=[self._etiqueta(p) for p in self._opciones])

    def _elegir_primera(self):
        if self._opciones:
            self.combo.set(self._etiqueta(self._opciones[0]))
            self._cargar_persona()

    def _seleccionar_persona(self, persona_id):
        persona = next((p for p in self._personas if p["id"] == persona_id), None)
        if persona:
            self._opciones = list(self._personas)
            self.combo.configure(values=[self._etiqueta(p) for p in self._opciones])
            self.combo.set(self._etiqueta(persona))

    def _persona_id(self) -> str | None:
        texto = self.combo.get()
        persona_id = texto.split(" — ")[0].strip() if " — " in texto else ""
        return persona_id if any(p["id"] == persona_id for p in self._personas) else None

    def _cargar_persona(self):
        persona_id = self._persona_id()
        maximo = self.servicio.max_libros_por_persona
        if not persona_id:
            self.tabla_activos.cargar([], mensaje_vacio="Elige una persona para ver sus préstamos.")
            self.tabla_historial.cargar([])
            self.cupo.configure(text="Sin persona seleccionada", style="Suave.TLabel")
            self.barra.configure(value=0, style="CupoOk.Horizontal.TProgressbar")
            self._habilitar()
            return
        activos = self.servicio.prestamos_activos(persona_id)
        self.tabla_activos.cargar(activos, mensaje_vacio="Esta persona no tiene libros prestados.",
                                  conservar_seleccion=False)
        self.tabla_historial.cargar(self.servicio.historial_prestamos(persona_id))
        libres = maximo - len(activos)
        self.cupo.configure(text=f"Tiene {len(activos)} libro(s) · puede llevar {libres} más",
                            style="BadgeOk.TLabel" if libres else "BadgeMal.TLabel")
        self.barra.configure(value=len(activos), style="CupoOk.Horizontal.TProgressbar" if libres
                             else "CupoLleno.Horizontal.TProgressbar")
        self._habilitar()

    def _ver_todos(self):
        self._disponibles = [l for l in self.servicio.catalogo_libros() if l["estado"] == "Disponible"]
        self._filtrar_disponibles()

    def _filtrar_disponibles(self):
        consulta = normalizar_texto(self.busqueda.get())
        filas = [l for l in self._disponibles if not consulta or all(
            t in normalizar_texto(f"{l['id']} {l['titulo']} {l['autor']}") for t in consulta.split())]
        self.tabla_disponibles.cargar(filas, mensaje_vacio="Ningún libro disponible coincide.")
        if self._libro_preseleccionado:
            self.tabla_disponibles.seleccionar(self._libro_preseleccionado)
            self._libro_preseleccionado = None
        self._habilitar()

    def buscar_semantico(self):
        texto = self.busqueda.get().strip()
        if not texto:
            return self._ver_todos()

        def listo(resultados):
            self.tabla_disponibles.cargar(resultados, mensaje_vacio="Sin resultados disponibles.",
                                          conservar_seleccion=False)
            self._habilitar()
        self.tarea(lambda: self.servicio.buscar_libros(texto, 15, solo_disponibles=True), listo,
                   "Buscando libros disponibles…")

    def _habilitar(self):
        persona_id = self._persona_id()
        seleccion_activos = self.tabla_activos.seleccion()
        seleccion_disponibles = self.tabla_disponibles.seleccion()
        libres = self.servicio.cupo_disponible(persona_id) if persona_id else 0
        self.btn_devolver.habilitar(bool(persona_id and seleccion_activos))
        self.btn_devolver_todos.habilitar(bool(persona_id and self.tabla_activos.filas))
        valido = bool(persona_id and seleccion_disponibles and len(seleccion_disponibles) <= libres)
        self.btn_prestar.habilitar(valido)
        if not persona_id:
            texto = "Elige primero a la persona."
        elif not libres:
            texto = "La persona alcanzó el máximo de libros."
        elif len(seleccion_disponibles) > libres:
            texto = f"Seleccionaste {len(seleccion_disponibles)}; solo puede llevar {libres}."
        else:
            texto = f"{len(seleccion_disponibles)} seleccionado(s) · cupo {libres}"
        self.seleccion_info.configure(text=texto, fg=COLOR["peligro"] if persona_id and seleccion_disponibles
                                      and len(seleccion_disponibles) > libres else COLOR["suave"])

    def prestar(self):
        persona_id = self._persona_id()
        libros = self.tabla_disponibles.seleccion()
        if not persona_id or not libros:
            return

        def listo(prestamos):
            titulos = ", ".join(f"«{p['titulo']}»" for p in prestamos)
            self.exito(f"Préstamo registrado: {titulos}. Vence el {prestamos[0]['fecha_limite']}.")
            self.al_mostrar(persona_id=persona_id)
        self.tarea(lambda: self.servicio.prestar(persona_id, libros), listo, "Registrando préstamo…")

    def _devolver(self, prestamo_ids):
        persona_id = self._persona_id()

        def listo(devueltos):
            self.exito(f"Se registró la devolución de {len(devueltos)} libro(s).")
            self.al_mostrar(persona_id=persona_id)
        self.tarea(lambda: self.servicio.devolver(persona_id, prestamo_ids), listo, "Registrando devolución…")

    def devolver(self):
        seleccion = self.tabla_activos.seleccion()
        if seleccion:
            self._devolver(seleccion)

    def devolver_todos(self):
        filas = self.tabla_activos.filas
        if filas and confirmar(self, "Devolver todos", f"¿Registrar la devolución de los {len(filas)} libro(s) "
                               "que tiene esta persona?", "Devolver todos"):
            self._devolver(None)
