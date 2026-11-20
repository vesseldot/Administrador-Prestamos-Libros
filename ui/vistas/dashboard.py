import tkinter as tk
from tkinter import ttk

from ui import tema
from ui.componentes import Boton, Indicador, Tabla, encabezado_tarjeta, tarjeta
from ui.tema import COLOR
from ui.vistas.base import Vista, fecha_corta

EVENTOS = {"libro_alta": "Alta de libro", "libro_actualizado": "Libro actualizado",
           "libro_eliminado": "Libro eliminado", "lote_importado": "Importación por lote",
           "persona_alta": "Alta de persona", "persona_actualizada": "Rectificación",
           "persona_eliminada": "Cancelación ARCO", "prestamo": "Préstamo", "devolucion": "Devolución",
           "modelo_cambiado": "Cambio de modelo", "migracion": "Migración"}


class VistaDashboard(Vista):
    titulo = "Dashboard"
    subtitulo = "Resumen del acervo, las personas registradas y los préstamos en curso."

    def construir(self):
        self.accion("Actualizar", "refrescar", self.refrescar)
        rejilla = ttk.Frame(self.cuerpo)
        rejilla.pack(fill="x")
        definicion = [
            ("libros", "Libros registrados", "libros", "primario", "libros"),
            ("disponibles", "Libros disponibles", "aceptar", "exito", "busqueda"),
            ("prestados", "Libros prestados", "prestamos", "aviso", "con_prestamo"),
            ("personas", "Personas registradas", "personas", "info", "personas"),
            ("prestamos_activos", "Préstamos activos", "calendario", "primario", "con_prestamo"),
            ("historicos", "Préstamos históricos", "reloj", "info", "prestamos"),
        ]
        self.indicadores = {}
        for n, (clave, titulo, icono, color, destino) in enumerate(definicion):
            indicador = Indicador(rejilla, titulo, icono, color, comando=lambda d=destino: self.app.navegar(d))
            indicador.grid(row=n // 3, column=n % 3, sticky="nsew", padx=(0 if n % 3 == 0 else 12, 0),
                           pady=(0, 12))
            self.indicadores[clave] = indicador
        for columna in range(3):
            rejilla.columnconfigure(columna, weight=1, uniform="kpi")

        rapidas = tarjeta(self.cuerpo, 14)
        rapidas.pack(fill="x", pady=(0, 12))
        tk.Label(rapidas, text="Acciones rápidas", font=tema.fs(12), fg=COLOR["texto"],
                 bg=COLOR["tarjeta"]).pack(side="left", padx=(0, 18))
        for texto, icono, destino, contexto in (
                ("Registrar libro", "agregar", "libros", {"accion": "alta"}),
                ("Registrar persona", "personas", "personas", {"accion": "alta"}),
                ("Nuevo préstamo", "prestar", "prestamos", {}),
                ("Búsqueda semántica", "buscar", "busqueda", {})):
            Boton(rapidas, texto, icono=icono, variante="chip",
                  comando=lambda d=destino, c=contexto: self.app.navegar(d, **c)).pack(side="left", padx=(0, 8))

        inferior = ttk.Frame(self.cuerpo)
        inferior.pack(fill="both", expand=True)
        inferior.columnconfigure(0, weight=3)
        inferior.columnconfigure(1, weight=2)
        inferior.rowconfigure(0, weight=1)

        actividad = tarjeta(inferior)
        actividad.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        encabezado_tarjeta(actividad, "Actividad reciente", "Últimas operaciones registradas en el sistema.")
        self.tabla_actividad = Tabla(actividad, [("fecha", "Fecha", 130, "w", False),
                                                 ("evento", "Evento", 150, "w", False),
                                                 ("descripcion", "Detalle", 320)], alto=8,
                                     mensaje_vacio="Aún no hay actividad registrada.", icono_vacio="reloj",
                                     clave_id="n")
        self.tabla_actividad.pack(fill="both", expand=True)

        vencimientos = tarjeta(inferior)
        vencimientos.grid(row=0, column=1, sticky="nsew")
        encabezado_tarjeta(vencimientos, "Próximos vencimientos", "Préstamos activos ordenados por fecha límite.")
        self.tabla_vencen = Tabla(vencimientos, [("fecha_limite", "Vence", 90, "w", False),
                                                 ("titulo", "Libro", 200), ("persona_id", "Persona", 70, "w", False)],
                                  alto=8, mensaje_vacio="No hay préstamos activos.", icono_vacio="calendario",
                                  estilo_fila=lambda p: ("alerta",) if p.get("vencido") else ())
        self.tabla_vencen.pack(fill="both", expand=True)

    def refrescar(self):
        self.tarea(self._datos, self._mostrar, "Calculando indicadores…")

    def _datos(self):
        return (self.servicio.estadisticas(), self.servicio.actividad_reciente(25),
                self.servicio.prestamos_activos())

    def _mostrar(self, datos):
        estadisticas, eventos, activos = datos
        total = estadisticas["libros"]
        porcentaje = f"{estadisticas['disponibles'] / total:.0%} del catálogo" if total else "sin libros"
        self.indicadores["libros"].actualizar(total, f"{estadisticas['documentos_indice']} en el índice semántico")
        self.indicadores["disponibles"].actualizar(estadisticas["disponibles"], porcentaje,
                                                   estadisticas["disponibles"] / total if total else None)
        vencidos = estadisticas["prestamos_vencidos"]
        self.indicadores["prestados"].actualizar(estadisticas["prestados"],
                                                 f"{vencidos} vencido(s)" if vencidos else "ninguno vencido",
                                                 estadisticas["prestados"] / total if total else None)
        self.indicadores["personas"].actualizar(estadisticas["personas"],
                                                f"{estadisticas['personas_con_prestamo']} con préstamo activo")
        self.indicadores["prestamos_activos"].actualizar(estadisticas["prestamos_activos"],
                                                         f"máximo {self.app.servicio.max_libros_por_persona} "
                                                         "por persona")
        self.indicadores["historicos"].actualizar(estadisticas["prestamos_historicos"], "registrados desde el inicio")
        filas = [{"n": n, "fecha": fecha_corta(e.get("fecha", "")), "evento": EVENTOS.get(e.get("tipo"), e.get("tipo")),
                  "descripcion": e.get("descripcion", "")} for n, e in enumerate(eventos)]
        self.tabla_actividad.cargar(filas)
        self.tabla_vencen.cargar(sorted(activos, key=lambda p: p.get("fecha_limite", ""))[:20])
        if estadisticas["sync_pendientes"]:
            self.aviso(f"{estadisticas['sync_pendientes']} libro(s) con sincronización pendiente.")
