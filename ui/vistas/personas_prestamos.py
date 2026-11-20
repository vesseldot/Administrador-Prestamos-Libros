import tkinter as tk
from tkinter import ttk

from seguridad import enmascarar_correo, enmascarar_telefono
from ui import tema
from ui.componentes import Boton, Tabla, tarjeta
from ui.tema import COLOR
from ui.vistas.base import Vista, etiqueta_estado, fecha_corta
from validaciones import normalizar_texto

COLUMNAS = [("nombre", "Persona / libro", 300), ("correo", "Correo", 210), ("telefono", "Teléfono", 120, "w", False),
            ("cantidad", "Libros", 70, "center", False), ("fecha", "Fecha de préstamo", 140, "w", False),
            ("vence", "Vence", 95, "w", False), ("estado", "Estado", 110, "w", False)]
SEGUNDOS_VISIBLE = 20


class VistaPersonasConPrestamo(Vista):
    titulo = "Personas con préstamos"
    subtitulo = "Préstamos activos agrupados por persona. Los datos de contacto se muestran solo cuando se necesitan."

    def construir(self):
        self.accion("Actualizar", "refrescar", self.refrescar)
        self._personas: list[dict] = []
        self._visible: str | None = None
        self._temporizador = None

        resumen = tarjeta(self.cuerpo, 14)
        resumen.pack(fill="x", pady=(0, 12))
        ttk.Label(resumen, text="Buscar", style="Campo.TLabel").pack(side="left")
        self.texto = ttk.Entry(resumen, width=32)
        self.texto.pack(side="left", padx=(8, 16))
        self.texto.bind("<KeyRelease>", lambda e: self._dibujar())
        self.solo_vencidos = tk.BooleanVar()
        ttk.Checkbutton(resumen, text="Solo con préstamos vencidos", variable=self.solo_vencidos,
                        command=self._dibujar).pack(side="left")
        self.resumen = tk.Label(resumen, text="", font=tema.f(10), fg=COLOR["suave"], bg=COLOR["tarjeta"])
        self.resumen.pack(side="right")

        caja = tarjeta(self.cuerpo, 12)
        caja.pack(fill="both", expand=True)
        pie = tk.Frame(caja, bg=COLOR["tarjeta"])
        pie.pack(side="bottom", fill="x", pady=(10, 0))
        self.btn_contacto = Boton(pie, "Mostrar contacto", icono="ver", comando=self.mostrar_contacto,
                                  ayuda=f"Revela correo y teléfono de la persona seleccionada durante "
                                        f"{SEGUNDOS_VISIBLE} segundos.")
        self.btn_contacto.pack(side="left")
        self.btn_devolucion = Boton(pie, "Registrar devolución", icono="devolver", variante="primario",
                                    comando=self.ir_a_prestamos)
        self.btn_devolucion.pack(side="right")
        tk.Label(pie, text="Teléfono visible solo para contactar por retraso o aclaraciones.", font=tema.f(9),
                 fg=COLOR["suave"], bg=COLOR["tarjeta"]).pack(side="left", padx=14)
        self.tabla = Tabla(caja, COLUMNAS, alto=16, arbol=True, icono_vacio="con_prestamo",
                           mensaje_vacio="No hay personas con préstamos activos.", clave_id="iid",
                           formatos={"estado": etiqueta_estado},
                           estilo_fila=lambda f: ("alerta",) if f.get("vencido") else ())
        self.tabla.pack(fill="both", expand=True)
        self.tabla.tree.bind("<<TreeviewSelect>>", lambda e: self._habilitar())
        self._habilitar()

    def refrescar(self):
        self._ocultar()
        self.tarea(self.servicio.personas_con_prestamos, self._recibir, "Cargando préstamos activos…")

    def _recibir(self, personas):
        self._personas = personas
        self._dibujar()

    def _persona_de(self, iid: str | None) -> str | None:
        if not iid:
            return None
        return iid.split("|")[0]

    def _dibujar(self):
        consulta = normalizar_texto(self.texto.get())
        grupos = []
        total_prestamos = vencidos = 0
        for persona in self._personas:
            if consulta and not all(t in normalizar_texto(f"{persona['id']} {persona['nombre_completo']}")
                                    for t in consulta.split()):
                continue
            prestamos = persona["prestamos"]
            if self.solo_vencidos.get() and not any(p["vencido"] for p in prestamos):
                continue
            visible = persona["id"] == self._visible
            padre = {"iid": persona["id"], "nombre": f"{persona['nombre_completo']}  ·  {persona['id']}",
                     "correo": persona["correo"] if visible else enmascarar_correo(persona["correo"]),
                     "telefono": persona["telefono"] if visible else enmascarar_telefono(persona["telefono"]),
                     "cantidad": f"{len(prestamos)}/{self.servicio.max_libros_por_persona}",
                     "fecha": "", "vence": "", "estado": ""}
            hijos = [{"iid": f"{persona['id']}|{p['id']}", "nombre": f"     {p['titulo']}", "correo": "",
                      "telefono": "", "cantidad": "", "fecha": fecha_corta(p["fecha_prestamo"]),
                      "vence": p["fecha_limite"], "estado": p["estado_visible"], "vencido": p["vencido"]}
                     for p in prestamos]
            total_prestamos += len(prestamos)
            vencidos += sum(1 for p in prestamos if p["vencido"])
            grupos.append((padre, hijos))
        seleccion = self.tabla.seleccion()
        self.tabla.cargar_arbol(grupos, mensaje_vacio="Ninguna persona coincide." if consulta or self.solo_vencidos.get()
                                else "No hay personas con préstamos activos.")
        if seleccion and self.tabla.tree.exists(seleccion[0]):
            self.tabla.tree.selection_set(seleccion[0])
        self.resumen.configure(text=f"{len(grupos)} persona(s) · {total_prestamos} préstamo(s) activo(s) · "
                                    f"{vencidos} vencido(s)")
        self._habilitar()

    def _habilitar(self):
        hay = bool(self._persona_de(next(iter(self.tabla.seleccion()), None)))
        self.btn_contacto.habilitar(hay)
        self.btn_devolucion.habilitar(hay)

    def mostrar_contacto(self):
        persona_id = self._persona_de(next(iter(self.tabla.seleccion()), None))
        if not persona_id:
            return
        self._visible = persona_id
        self._dibujar()
        if self._temporizador:
            self.after_cancel(self._temporizador)
        self._temporizador = self.after(SEGUNDOS_VISIBLE * 1000, self._ocultar)

    def _ocultar(self):
        self._temporizador = None
        if self._visible:
            self._visible = None
            self._dibujar()

    def ir_a_prestamos(self):
        persona_id = self._persona_de(next(iter(self.tabla.seleccion()), None))
        if persona_id:
            self.app.navegar("prestamos", persona_id=persona_id)
