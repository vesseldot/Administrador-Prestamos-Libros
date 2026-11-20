import tkinter as tk
from tkinter import filedialog, ttk

import config
from ui import tema
from ui.componentes import (Boton, Dialogo, Formulario, Portada, Tabla, caja_texto, confirmar,
                            encabezado_tarjeta, escribir, informar, tarjeta)
from ui.tema import COLOR
from ui.vistas.base import Vista, contenido_ficha, etiqueta_estado, ficha_libro
from validaciones import TIPOS_PASTA

CAMPOS_FORMULARIO = [
    ("id", "ID *", "entry", "Letras, números, guion o guion bajo. Ej. libro201"),
    ("isbn", "ISBN *", "entry", "ISBN-10 o ISBN-13 con dígito de control válido"),
    ("titulo", "Título *", "entry", ""),
    ("autor", "Autor *", "entry", ""),
    ("anio", "Año *", "entry", "Número entero, ej. 2011"),
    ("editorial", "Editorial *", "entry", ""),
    ("genero", "Género *", "entry", "Ej. ciencia ficcion, novela, divulgacion"),
    ("tema", "Tema *", "entry", "Ej. marte, dictadura, amistad"),
    ("idioma", "Idioma *", "entry", "Código de 2 o 3 letras: es, en…"),
    ("pasta", "Pasta *", "combo", TIPOS_PASTA),
    ("paginas", "Páginas *", "entry", "Número entero mayor a 0"),
    ("calificacion", "Calificación *", "entry", "De 0 a 5, ej. 4.3"),
    ("disponible", "Disponible", "check", True),
    ("sinopsis", "Sinopsis *", "texto", None),
]

COLUMNAS = [("id", "ID", 84, "w", False), ("titulo", "Título", 230), ("autor", "Autor", 160),
            ("anio", "Año", 55, "center", False), ("genero", "Género", 130, "w", False),
            ("calificacion", "Calif.", 55, "center", False), ("estado", "Estado", 135, "w", False)]

TODOS = "Todos"
TIPOS_IMAGEN = [("Imágenes", "*.jpg *.jpeg *.png *.webp *.gif *.bmp"), ("Todos los archivos", "*.*")]


def mostrar_reporte_lote(padre, resultado):
    lineas = [f"Fila {r['fila']} · {r['id']}: " + "; ".join(r["motivos"]) for r in resultado.rechazados]
    mensaje = (f"Registros leídos: {resultado.total}\nImportados correctamente: {len(resultado.agregados)}\n"
               f"Rechazados: {len(resultado.rechazados)}")
    tipo = "exito" if not resultado.rechazados else ("aviso" if resultado.agregados else "error")
    dialogo = Dialogo(padre, "Reporte de importación", mensaje, tipo,
                      detalle="\n".join(lineas) if lineas else "")
    padre.wait_window(dialogo)


class VistaLibros(Vista):
    titulo = "Libros"
    subtitulo = "Catálogo completo: filtra, ordena por columna y administra cada registro."

    def construir(self):
        self.accion("Nuevo libro", "agregar", self.alta, "primario")
        self.accion("Importar lote", "importar", self.importar,
                    ayuda="Carga varios libros desde un archivo CSV o JSON y muestra un reporte por fila.")
        self.accion("Actualizar", "refrescar", self.refrescar)
        self._libros: list[dict] = []
        self._detalle_id = None

        filtros = tarjeta(self.cuerpo, 14)
        filtros.pack(fill="x", pady=(0, 12))
        ttk.Label(filtros, text="Buscar", style="Campo.TLabel").pack(side="left")
        self.texto = ttk.Entry(filtros, width=34)
        self.texto.pack(side="left", padx=(8, 16))
        self.texto.bind("<KeyRelease>", lambda e: self._programar_filtro())
        self.combos = {}
        for clave, etiqueta in (("genero", "Género"), ("idioma", "Idioma"), ("estado", "Estado")):
            ttk.Label(filtros, text=etiqueta, style="Campo.TLabel").pack(side="left")
            combo = ttk.Combobox(filtros, state="readonly", width=16 if clave == "genero" else 12, values=[TODOS])
            combo.set(TODOS)
            combo.pack(side="left", padx=(8, 16))
            combo.bind("<<ComboboxSelected>>", lambda e: self._filtrar())
            self.combos[clave] = combo
        Boton(filtros, "Limpiar", icono="filtro", variante="enlace", comando=self._limpiar).pack(side="left")
        self.contador = ttk.Label(filtros, text="", style="Suave.TLabel")
        self.contador.pack(side="right")

        cuerpo = ttk.Frame(self.cuerpo)
        cuerpo.pack(fill="both", expand=True)
        cuerpo.columnconfigure(0, weight=3, uniform="partes")
        cuerpo.columnconfigure(1, weight=2, minsize=tema.px(330), uniform="partes")
        cuerpo.rowconfigure(0, weight=1)

        caja_tabla = tarjeta(cuerpo, 12)
        caja_tabla.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.tabla = Tabla(caja_tabla, COLUMNAS, alto=14, icono_vacio="libros",
                           mensaje_vacio="No hay libros. Registra uno o importa un lote.",
                           formatos={"estado": etiqueta_estado},
                           estilo_fila=lambda l: ("tenue",) if l.get("estado") != "Disponible" else ())
        self.tabla.pack(fill="both", expand=True)
        self.tabla.tree.bind("<<TreeviewSelect>>", lambda e: self._cargar_detalle())
        self.tabla.tree.bind("<Double-1>", lambda e: self.editar())

        detalle = tarjeta(cuerpo, 16)
        detalle.grid(row=0, column=1, sticky="nsew")
        encabezado_tarjeta(detalle, "Ficha del libro")
        botones = tk.Frame(detalle, bg=COLOR["tarjeta"])
        botones.pack(side="bottom", fill="x", pady=(10, 0))
        self.btn_editar = Boton(botones, "Editar", icono="editar", comando=self.editar)
        self.btn_editar.pack(side="left")
        self.btn_similares = Boton(botones, "Buscar similares", icono="buscar", comando=self.similares)
        self.btn_similares.pack(side="left", padx=8)
        self.btn_eliminar = Boton(botones, "Eliminar", icono="eliminar", variante="peligro", comando=self.eliminar)
        self.btn_eliminar.pack(side="right")

        cabecera = tk.Frame(detalle, bg=COLOR["tarjeta"])
        cabecera.pack(fill="x", pady=(0, 10))
        self.portada = Portada(cabecera)
        self.portada.pack(side="left")
        acciones = tk.Frame(cabecera, bg=COLOR["tarjeta"])
        acciones.pack(side="left", fill="y", padx=(12, 0))
        self.btn_elegir_portada = Boton(acciones, "Elegir imagen…", icono="imagen", variante="enlace", tamano=9,
                                        padx=6, pady=3, comando=self.elegir_portada,
                                        ayuda="Usa una imagen JPG, PNG, WEBP, GIF o BMP de tu equipo.")
        self.btn_elegir_portada.pack(anchor="w")
        self.btn_buscar_portada = Boton(acciones, "Buscar en internet", icono="buscar", variante="enlace",
                                        tamano=9, padx=6, pady=3, comando=self.buscar_portada,
                                        ayuda="Busca la portada en Open Library por ISBN y por título.")
        self.btn_buscar_portada.pack(anchor="w", pady=(2, 0))
        self.btn_quitar_portada = Boton(acciones, "Quitar portada", icono="eliminar", variante="enlace",
                                        tamano=9, padx=6, pady=3, comando=self.quitar_portada)
        self.btn_quitar_portada.pack(anchor="w", pady=(2, 0))
        self.lbl_origen = tk.Label(acciones, text="", font=tema.f(8), fg=COLOR["suave"], bg=COLOR["tarjeta"],
                                   justify="left", anchor="w", wraplength=tema.px(170))
        self.lbl_origen.pack(anchor="w", pady=(8, 0))

        self.ficha = caja_texto(detalle, 18, solo_lectura=True)
        self.ficha.configure(bg=COLOR["tarjeta"], highlightthickness=0, padx=2)
        ficha_libro(self.ficha)
        self.ficha.pack(fill="both", expand=True)
        self._habilitar_acciones(False)
        self._id_filtro = None

    def al_mostrar(self, accion=None, seleccionar=None, **_):
        self.refrescar(seleccionar)
        if accion == "alta":
            self.after(100, self.alta)

    def refrescar(self, seleccionar=None):
        try:
            self._libros = self.servicio.catalogo_libros()
        except Exception as error:  # noqa: BLE001
            self.app.manejar_error(error)
            return
        for clave in ("genero", "idioma"):
            valores = sorted({l[clave] for l in self._libros if l.get(clave)})
            self.combos[clave].configure(values=[TODOS] + valores)
        self.combos["estado"].configure(values=[TODOS, "Disponible", "Prestado", "No disponible"])
        self._filtrar()
        if seleccionar:
            self.tabla.seleccionar(seleccionar)
        self._cargar_detalle()

    def _programar_filtro(self):
        if self._id_filtro:
            self.after_cancel(self._id_filtro)
        self._id_filtro = self.after(200, self._filtrar)

    def _filtrar(self):
        valor = {c: ("" if combo.get() == TODOS else combo.get()) for c, combo in self.combos.items()}
        filtrados = self.servicio.filtrar_catalogo(self._libros, self.texto.get(), valor["genero"],
                                                   valor["idioma"], valor["estado"])
        mensaje = ("No hay libros. Registra uno o importa un lote." if not self._libros
                   else "Ningún libro coincide con los filtros.")
        self.tabla.cargar(filtrados, mensaje_vacio=mensaje)
        self.contador.configure(text=f"{len(filtrados)} de {len(self._libros)} libros")
        if self._detalle_id and not self.tabla.fila(self._detalle_id):
            self._cargar_detalle()

    def _limpiar(self):
        self.texto.delete(0, "end")
        for combo in self.combos.values():
            combo.set(TODOS)
        self._filtrar()

    def _habilitar_acciones(self, valor: bool, con_portada: bool = False):
        for boton in (self.btn_editar, self.btn_similares, self.btn_eliminar, self.btn_elegir_portada):
            boton.habilitar(valor)
        self.btn_buscar_portada.habilitar(valor and self._descarga_portadas)
        self.btn_quitar_portada.habilitar(valor and con_portada)

    @property
    def _descarga_portadas(self) -> bool:
        return bool(config.DESCARGAR_PORTADAS)

    def _mostrar_portada(self, libro: dict | None, png: bytes | None):
        self.portada.mostrar(png)
        info = (libro or {}).get("portada")
        self.lbl_origen.configure(text=f"Portada: {info['origen']}" if info else "")

    def _cargar_detalle(self):
        fila = self.tabla.fila_seleccionada()
        self._detalle_id = fila["id"] if fila else None
        self._habilitar_acciones(bool(fila))
        if not fila:
            self._mostrar_portada(None, None)
            escribir(self.ficha, contenido_ficha(None, "Selecciona un libro de la tabla para ver su ficha completa."))
            return
        libro_id = fila["id"]
        ancho, alto = self.portada.tamano

        def trabajo():
            libro = self.servicio.obtener_libro(libro_id)
            return libro, (self.servicio.portada_libro(libro_id, ancho, alto) if libro else None)

        def mostrar(datos):
            libro, png = datos
            if self._detalle_id == libro_id:
                self._libro_detalle = libro
                self._mostrar_portada(libro, png)
                self._habilitar_acciones(bool(libro), con_portada=bool(libro and libro.get("portada")))
                escribir(self.ficha, contenido_ficha(libro, "El libro ya no existe."))
        self.tarea(trabajo, mostrar, "Cargando ficha…")

    def _formulario(self, titulo, valores, al_guardar, bloqueados=()):
        Formulario(self, titulo, CAMPOS_FORMULARIO, al_guardar, valores=valores, bloqueados=bloqueados,
                   columnas=2, icono="libros", ancho_campo=30)

    def alta(self):
        def guardar(datos, formulario):
            self.servicio.validar_alta(datos)
            formulario.ocupado(True, "Calculando embedding…")

            def listo(libro_id):
                formulario.destroy()
                self.exito(f"Libro «{datos['titulo']}» registrado.")
                self.refrescar(seleccionar=libro_id)
                self._portada_automatica(libro_id)

            def fallo(error):
                if not formulario.winfo_exists():
                    return self.app.manejar_error(error)
                formulario.ocupado(False)
                if isinstance(error, ValueError):
                    formulario.mostrar_errores(str(error))
                else:
                    self.app.manejar_error(error)
            self.tarea(lambda: self.servicio.alta_libro(datos), listo, "Registrando libro…", fallo)
        self._formulario("Registrar libro", {"idioma": "es", "pasta": "blanda", "disponible": True}, guardar)

    def editar(self):
        fila = self.tabla.fila_seleccionada()
        if not fila:
            return
        libro_id = fila["id"]

        def abrir(libro):
            if not libro:
                self.aviso("El libro ya no existe.")
                return self.refrescar()
            prestado = libro["estado"] == "Prestado"

            def guardar(datos, formulario):
                formulario.ocupado(True, "Actualizando…")

                def listo(_):
                    formulario.destroy()
                    self.exito("Libro actualizado en Redis y ChromaDB.")
                    self.refrescar(seleccionar=libro_id)

                def fallo(error):
                    formulario.ocupado(False)
                    if isinstance(error, ValueError):
                        formulario.mostrar_errores(str(error))
                    else:
                        self.app.manejar_error(error)
                self.tarea(lambda: self.servicio.actualizar_libro(libro_id, datos), listo, "Actualizando libro…", fallo)
            self._formulario(f"Editar libro {libro_id}" + (" (prestado)" if prestado else ""), libro, guardar,
                             bloqueados=("id", "disponible") if prestado else ("id",))
        self.tarea(lambda: self.servicio.obtener_libro(libro_id), abrir, "Cargando libro…")

    def eliminar(self):
        fila = self.tabla.fila_seleccionada()
        if not fila:
            return
        if fila["estado"] == "Prestado":
            informar(self, "No se puede eliminar", f"«{fila['titulo']}» está prestado a {fila['prestado_a']}. "
                     "Registra primero la devolución.", "aviso")
            return
        if not confirmar(self, "Eliminar libro", f"¿Eliminar definitivamente «{fila['titulo']}»? Se borrará de "
                         "Redis y del índice semántico. El historial de préstamos se conserva.",
                         "Eliminar", peligro=True):
            return

        def listo(_):
            self.exito(f"Libro «{fila['titulo']}» eliminado.")
            self.refrescar()
        self.tarea(lambda: self.servicio.eliminar_libro(fila["id"]), listo, "Eliminando libro…")

    def similares(self):
        libro = getattr(self, "_libro_detalle", None)
        if libro and libro.get("sinopsis"):
            self.app.navegar("busqueda", consulta=libro["sinopsis"], excluir=libro["id"])

    def _portada_automatica(self, libro_id: str):
        """Tras un alta, busca la portada en segundo plano sin interrumpir al operador."""
        if not self._descarga_portadas:
            return

        def listo(resultado):
            if resultado.get("nueva") and self._detalle_id == libro_id:
                self._cargar_detalle()

        self.app.tareas.ejecutar(lambda: self.servicio.buscar_portada(libro_id), listo,
                                 lambda error: self.app.mensaje_estado("No se pudo buscar la portada en internet."),
                                 "Buscando la portada en Open Library…", independiente=True)

    def elegir_portada(self):
        libro_id = self._detalle_id
        if not libro_id:
            return
        ruta = filedialog.askopenfilename(parent=self, title="Selecciona la imagen de la portada",
                                          filetypes=TIPOS_IMAGEN)
        if not ruta:
            return

        def listo(_):
            self.exito("Portada actualizada.")
            self._cargar_detalle()
        self.tarea(lambda: self.servicio.asignar_portada(libro_id, ruta), listo, "Guardando la portada…")

    def buscar_portada(self):
        libro = getattr(self, "_libro_detalle", None)
        if not libro or libro["id"] != self._detalle_id:
            return
        if libro.get("portada") and not confirmar(self, "Reemplazar portada",
                                                  "El libro ya tiene portada. ¿Buscar otra en Open Library y "
                                                  "reemplazarla si se encuentra?", "Buscar"):
            return
        self.btn_buscar_portada.habilitar(False)

        def listo(resultado):
            if resultado["encontrada"]:
                self.exito(f"Portada encontrada para «{libro['titulo']}».")
            else:
                informar(self, "Sin resultados", f"Open Library no tiene una portada para «{libro['titulo']}». "
                         "Puedes elegir una imagen de tu equipo.", "info")
            self._cargar_detalle()

        def fallo(error):
            self._cargar_detalle()
            self.app.manejar_error(error)
        self.app.tareas.ejecutar(lambda: self.servicio.buscar_portada(libro["id"], reemplazar=True), listo, fallo,
                                 "Buscando la portada en Open Library…", independiente=True)

    def quitar_portada(self):
        libro_id = self._detalle_id
        if not libro_id or not confirmar(self, "Quitar portada", "¿Quitar la portada de este libro? Podrás "
                                         "elegir otra o buscarla de nuevo.", "Quitar", peligro=True):
            return

        def listo(_):
            self.exito("Portada quitada.")
            self._cargar_detalle()
        self.tarea(lambda: self.servicio.quitar_portada(libro_id), listo, "Quitando la portada…")

    def importar(self):
        ruta = filedialog.askopenfilename(parent=self, title="Selecciona el archivo de libros",
                                          initialdir=str(config.DIR_DATOS),
                                          filetypes=[("CSV o JSON", "*.csv *.json"), ("CSV", "*.csv"),
                                                     ("JSON", "*.json")])
        if not ruta:
            return

        def progreso(hechos, total):
            self.app.mensaje_estado(f"Calculando embeddings… {hechos}/{total}")

        def listo(resultado):
            mostrar_reporte_lote(self, resultado)
            self.refrescar()
        self.tarea(lambda: self.servicio.importar_archivo(ruta, self.app.tareas.progreso(progreso)), listo,
                   "Importando libros…")
