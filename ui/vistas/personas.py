import json
import tkinter as tk
from tkinter import filedialog, ttk

import config
from seguridad import AVISO_PRIVACIDAD, enmascarar_correo, enmascarar_telefono
from ui import tema
from ui.componentes import (Ayuda, Boton, Formulario, Tabla, cabecera_dialogo, caja_texto, centrar,
                            confirmar, escribir, informar, tarjeta)
from ui.tema import COLOR
from ui.vistas.base import Vista, etiqueta_estado, fecha_corta
from validaciones import ESTADOS_MEXICO, GENEROS_PERSONA, OCUPACIONES, TIPOS_USUARIO

CAMPOS_FORMULARIO = [
    ("nombre", "Nombre *", "entry", ""),
    ("apellido_paterno", "Apellido paterno *", "entry", ""),
    ("apellido_materno", "Apellido materno", "entry", "Opcional"),
    ("fecha_nacimiento", "Fecha de nacimiento *", "entry", "Formato AAAA-MM-DD. La edad se calcula sola."),
    ("genero", "Género *", "combo", GENEROS_PERSONA),
    ("correo", "Correo *", "entry", "nombre@dominio.com"),
    ("telefono", "Teléfono *", "entry", "10 dígitos"),
    ("calle_numero", "Calle y número", "entry", ""),
    ("colonia", "Colonia", "entry", ""),
    ("ciudad", "Ciudad", "entry", ""),
    ("estado", "Estado *", "combo", ESTADOS_MEXICO),
    ("codigo_postal", "Código postal *", "entry", "5 dígitos"),
    ("ocupacion", "Ocupación *", "combo", OCUPACIONES),
    ("tipo_usuario", "Tipo de usuario *", "combo", TIPOS_USUARIO),
    ("acepta_aviso_privacidad", "Acepto el aviso de privacidad *", "check", False),
]

COLUMNAS = [("id", "ID", 70, "w", False), ("nombre_completo", "Nombre", 230), ("edad", "Edad", 55, "center", False),
            ("tipo_usuario", "Tipo", 80, "w", False), ("ocupacion", "Ocupación", 95, "w", False),
            ("correo_m", "Correo", 190), ("telefono_m", "Teléfono", 105, "w", False),
            ("ciudad", "Ciudad", 120), ("prestamos_txt", "Préstamos", 85, "center", False)]
TODOS = "Todos"


def mostrar_aviso(padre):
    ventana = tk.Toplevel(padre)
    ventana.withdraw()
    ventana.title("Aviso de privacidad")
    ventana.configure(bg=COLOR["fondo"])
    ventana.transient(padre.winfo_toplevel())
    cabecera_dialogo(ventana, "Aviso de privacidad", "Ley Federal de Protección de Datos Personales en "
                     "Posesión de los Particulares", "escudo")
    caja = tarjeta(ventana, 0)
    caja.pack(fill="both", expand=True, padx=16, pady=14)
    texto = caja_texto(caja, 24, width=82)
    texto.configure(highlightthickness=0, padx=18, pady=14, spacing1=2)
    escribir(texto, AVISO_PRIVACIDAD)
    barra = ttk.Scrollbar(caja, orient="vertical", command=texto.yview)
    texto.configure(yscrollcommand=barra.set)
    texto.pack(side="left", fill="both", expand=True)
    barra.pack(side="right", fill="y")
    Boton(ventana, "Cerrar", variante="primario", fondo=COLOR["fondo"], comando=ventana.destroy).pack(
        anchor="e", padx=16, pady=(0, 16))
    ventana.bind("<Escape>", lambda e: ventana.destroy())
    centrar(ventana, padre)
    ventana.deiconify()
    ventana.grab_set()


class FichaPersona(tk.Toplevel):
    """Derecho ARCO de acceso: todos los datos de la persona y su historial de préstamos."""

    def __init__(self, padre, persona: dict, historial: list[dict], maximo: int):
        super().__init__(padre)
        self.withdraw()
        self.title(f"Ficha de {persona['id']}")
        self.configure(bg=COLOR["fondo"])
        self.transient(padre.winfo_toplevel())
        self.resizable(False, False)
        cabecera = cabecera_dialogo(self, persona["nombre_completo"],
                                    f"{persona['id']} · {persona['tipo_usuario']} · {persona['ocupacion']}", "contacto")
        tk.Label(cabecera, text="DERECHO ARCO DE ACCESO", font=tema.f(7, "bold"), fg=COLOR["lateral_texto"],
                 bg=COLOR["lateral_hover"], padx=8, pady=3).pack(side="right", anchor="n")
        if not persona.get("integridad_ok", True):
            tk.Label(self, text="Algún dato no superó la verificación de integridad y no se muestra.",
                     bg=COLOR["peligro_claro"], fg=COLOR["peligro"], font=tema.f(9), pady=6).pack(fill="x")
        datos = tarjeta(self, 16)
        datos.pack(fill="x", padx=16, pady=(14, 8))
        filas = [
            ("Fecha de nacimiento", f"{persona['fecha_nacimiento']} (edad {persona['edad']})"),
            ("Género", persona["genero"]), ("Correo", persona["correo"]), ("Teléfono", persona["telefono"]),
            ("Domicilio", ", ".join(x for x in (persona["calle_numero"],
                                                persona["colonia"] and f"col. {persona['colonia']}",
                                                persona["ciudad"], persona["estado"],
                                                f"C.P. {persona['codigo_postal']}") if x)),
            ("Aviso de privacidad", f"Aceptado el {fecha_corta(persona['fecha_aviso'])}"
             if persona["acepta_aviso_privacidad"] else "No aceptado"),
            ("Registro", fecha_corta(persona["fecha_registro"])),
            ("Última rectificación", fecha_corta(persona.get("fecha_actualizacion", ""))),
        ]
        for n, (etiqueta, valor) in enumerate(filas):
            ttk.Label(datos, text=etiqueta, style="Suave.TLabel").grid(row=n, column=0, sticky="nw",
                                                                      padx=(0, 18), pady=2)
            ttk.Label(datos, text=valor, style="Campo.TLabel", wraplength=420, justify="left").grid(
                row=n, column=1, sticky="w", pady=2)
        prestamos = tarjeta(self, 14)
        prestamos.pack(fill="both", padx=16, pady=8)
        activos = sum(1 for p in historial if p["estado"] == "activo")
        cabeza = tk.Frame(prestamos, bg=COLOR["tarjeta"])
        cabeza.pack(fill="x", pady=(0, 8))
        ttk.Label(cabeza, text=f"HISTORIAL DE PRÉSTAMOS · {activos}/{maximo} ACTIVOS",
                  style="Seccion.TLabel").pack(side="left")
        ttk.Progressbar(cabeza, maximum=maximo, value=activos, length=120,
                        style=("CupoLleno" if activos >= maximo else "CupoOk") + ".Horizontal.TProgressbar"
                        ).pack(side="right")
        tabla = Tabla(prestamos, [("titulo", "Libro", 240), ("fecha_prestamo", "Prestado", 120, "w", False),
                                  ("fecha_limite", "Vence", 90, "w", False),
                                  ("fecha_devolucion", "Devuelto", 120, "w", False),
                                  ("estado_visible", "Estado", 100, "w", False)],
                      alto=6, mensaje_vacio="Sin préstamos registrados.",
                      formatos={"fecha_prestamo": fecha_corta, "fecha_devolucion": fecha_corta,
                                "estado_visible": etiqueta_estado},
                      estilo_fila=lambda p: ("alerta",) if p.get("vencido") else
                      (("tenue",) if p.get("estado") == "devuelto" else ()))
        tabla.pack(fill="both", expand=True)
        tabla.cargar(historial)
        Boton(self, "Cerrar", variante="primario", fondo=COLOR["fondo"], comando=self.destroy).pack(
            anchor="e", padx=16, pady=(8, 16))
        self.bind("<Escape>", lambda e: self.destroy())
        centrar(self, padre)
        self.deiconify()
        self.grab_set()


class VistaPersonas(Vista):
    titulo = "Personas"
    subtitulo = "Usuarios registrados. Los datos personales se guardan cifrados y se muestran parcialmente ocultos."

    def construir(self):
        self.accion("Registrar persona", "agregar", self.alta, "primario")
        self.accion("Aviso de privacidad", "escudo", lambda: mostrar_aviso(self))
        self.accion("Actualizar", "refrescar", self.refrescar)
        filtros = tarjeta(self.cuerpo, 14)
        filtros.pack(fill="x", pady=(0, 12))
        ttk.Label(filtros, text="Buscar", style="Campo.TLabel").pack(side="left")
        self.texto = ttk.Entry(filtros, width=36)
        self.texto.pack(side="left", padx=(8, 16))
        self.texto.bind("<KeyRelease>", lambda e: self._programar())
        ttk.Label(filtros, text="Tipo", style="Campo.TLabel").pack(side="left")
        self.tipo = ttk.Combobox(filtros, state="readonly", values=[TODOS] + TIPOS_USUARIO, width=12)
        self.tipo.set(TODOS)
        self.tipo.pack(side="left", padx=(8, 16))
        self.tipo.bind("<<ComboboxSelected>>", lambda e: self.refrescar())
        self.solo_prestamos = tk.BooleanVar()
        ttk.Checkbutton(filtros, text="Solo con préstamos activos", variable=self.solo_prestamos,
                        command=self.refrescar).pack(side="left")
        Ayuda(self.texto, "Busca por nombre, apellidos, ID, tipo de usuario, ocupación, ciudad o estado. "
                          "No se busca por correo ni teléfono.", retraso_ms=300)

        caja = tarjeta(self.cuerpo, 12)
        caja.pack(fill="both", expand=True)
        botones = tk.Frame(caja, bg=COLOR["tarjeta"])
        botones.pack(side="bottom", fill="x", pady=(10, 0))
        self.botones = [
            Boton(botones, "Ver ficha", icono="ver", comando=self.ver_ficha,
                  ayuda="Derecho ARCO de acceso: muestra todos los datos y el historial."),
            Boton(botones, "Editar datos", icono="editar", comando=self.editar,
                  ayuda="Derecho ARCO de rectificación."),
            Boton(botones, "Exportar datos", icono="exportar", comando=self.exportar,
                  ayuda="Entrega los datos de la persona en un archivo JSON."),
            Boton(botones, "Prestar libros", icono="prestar", comando=self.prestar),
        ]
        for boton in self.botones:
            boton.pack(side="left", padx=(0, 8))
        self.btn_eliminar = Boton(botones, "Eliminar (cancelación)", icono="eliminar", variante="peligro",
                                  comando=self.eliminar, ayuda="Derecho ARCO de cancelación. "
                                  "Solo procede si la persona no tiene préstamos activos.")
        self.btn_eliminar.pack(side="right")
        self.contador = tk.Label(botones, text="", font=tema.f(9), fg=COLOR["suave"], bg=COLOR["tarjeta"])
        self.contador.pack(side="right", padx=16)
        self.tabla = Tabla(caja, COLUMNAS, alto=16, icono_vacio="personas",
                           mensaje_vacio="No hay personas registradas.",
                           estilo_fila=lambda p: ("alerta",) if not p.get("integridad_ok", True) else ())
        self.tabla.pack(fill="both", expand=True)
        self.tabla.tree.bind("<<TreeviewSelect>>", lambda e: self._habilitar())
        self.tabla.tree.bind("<Double-1>", lambda e: self.ver_ficha())
        self._id_filtro = None
        self._habilitar()

    def al_mostrar(self, accion=None, **_):
        self.refrescar()
        if accion == "alta":
            self.after(100, self.alta)

    def _programar(self):
        if self._id_filtro:
            self.after_cancel(self._id_filtro)
        self._id_filtro = self.after(250, self.refrescar)

    def refrescar(self):
        tipo = "" if self.tipo.get() == TODOS else self.tipo.get()
        try:
            personas = self.servicio.buscar_personas(self.texto.get(), tipo, self.solo_prestamos.get())
            total = self.servicio.contar_personas()
        except Exception as error:  # noqa: BLE001
            return self.app.manejar_error(error)
        maximo = config.MAX_LIBROS_POR_PERSONA
        for persona in personas:
            persona["correo_m"] = enmascarar_correo(persona["correo"])
            persona["telefono_m"] = enmascarar_telefono(persona["telefono"])
            persona["prestamos_txt"] = f"{persona['num_prestamos']}/{maximo}"
        hay_filtro = self.texto.get().strip() or tipo or self.solo_prestamos.get()
        self.tabla.cargar(personas, mensaje_vacio="Ninguna persona coincide con la búsqueda." if hay_filtro
                          else "No hay personas registradas.")
        self.contador.configure(text=f"{len(personas)} de {total} personas")
        self._habilitar()

    def _habilitar(self):
        hay = bool(self.tabla.fila_seleccionada())
        for boton in [*self.botones, self.btn_eliminar]:
            boton.habilitar(hay)

    def _seleccionada(self) -> str | None:
        fila = self.tabla.fila_seleccionada()
        return fila["id"] if fila else None

    def alta(self):
        def guardar(datos, formulario):
            persona_id = self.servicio.registrar_persona(datos)
            formulario.destroy()
            self.exito(f"Persona registrada con el identificador {persona_id}.")
            self.refrescar()
            self.tabla.seleccionar(persona_id)
        Formulario(self, "Registrar persona", CAMPOS_FORMULARIO, guardar, columnas=2, icono="personas",
                   extra=("Leer aviso de privacidad", lambda: mostrar_aviso(self), "escudo"))

    def editar(self):
        persona_id = self._seleccionada()
        if not persona_id:
            return
        persona = self.servicio.obtener_persona(persona_id)
        if not persona:
            return self.refrescar()

        def guardar(datos, formulario):
            self.servicio.actualizar_persona(persona_id, datos)
            formulario.destroy()
            self.exito("Datos rectificados correctamente.")
            self.refrescar()
            self.tabla.seleccionar(persona_id)
        Formulario(self, f"Rectificar datos de {persona_id}", CAMPOS_FORMULARIO, guardar, valores=persona,
                   columnas=2, icono="editar",
                   extra=("Leer aviso de privacidad", lambda: mostrar_aviso(self), "escudo"))

    def ver_ficha(self):
        persona_id = self._seleccionada()
        if not persona_id:
            return
        persona = self.servicio.obtener_persona(persona_id)
        if persona:
            FichaPersona(self, persona, self.servicio.historial_prestamos(persona_id),
                         config.MAX_LIBROS_POR_PERSONA)

    def exportar(self):
        persona_id = self._seleccionada()
        if not persona_id:
            return
        ruta = filedialog.asksaveasfilename(parent=self, title="Exportar datos personales",
                                            defaultextension=".json", initialfile=f"datos_{persona_id}.json",
                                            filetypes=[("JSON", "*.json")])
        if not ruta:
            return
        datos = self.servicio.exportar_persona(persona_id)
        with open(ruta, "w", encoding="utf-8") as archivo:
            json.dump(datos, archivo, ensure_ascii=False, indent=2)
        self.exito("Datos exportados. Entrega el archivo solo a su titular.")

    def prestar(self):
        persona_id = self._seleccionada()
        if persona_id:
            self.app.navegar("prestamos", persona_id=persona_id)

    def eliminar(self):
        fila = self.tabla.fila_seleccionada()
        if not fila:
            return
        if fila["num_prestamos"]:
            informar(self, "No se puede eliminar", f"{fila['id']} tiene {fila['num_prestamos']} libro(s) prestado(s). "
                     "Registra primero la devolución.", "aviso")
            return
        if not confirmar(self, "Cancelación de datos personales",
                         f"¿Eliminar todos los datos personales de {fila['id']}? Esta acción no se puede deshacer. "
                         "Su historial de préstamos se conservará solo con el identificador.",
                         "Eliminar", peligro=True):
            return
        self.servicio.eliminar_persona(fila["id"])
        self.exito(f"Datos de {fila['id']} eliminados.")
        self.refrescar()
