"""Diálogo para descargar el modelo de embeddings con progreso."""
import time
import tkinter as tk
from tkinter import ttk

import config
from servicios import describir_error
from ui import tema
from ui.componentes import Boton, cabecera_dialogo, centrar, tarjeta
from ui.tema import COLOR


class DialogoDescargaModelo(tk.Toplevel):
    def __init__(self, padre, app, clave: str, al_completar=None, al_posponer=None):
        super().__init__(padre)
        self.withdraw()
        self.app = app
        self.clave = clave
        self.al_completar = al_completar
        self.al_posponer = al_posponer
        self._ultimo_aviso = 0.0
        self._inicio = 0.0
        self._descargando = False
        datos = app.servicio.estado_modelo(clave)
        self.title("Modelo de embeddings")
        self.transient(padre.winfo_toplevel())
        self.resizable(False, False)
        self.configure(bg=COLOR["fondo"])
        cabecera_dialogo(self, "Modelo de embeddings no disponible",
                         "La búsqueda semántica necesita descargar el modelo una sola vez.", "exportar")
        cuerpo = tarjeta(self, 18)
        cuerpo.pack(fill="both", padx=16, pady=14)
        filas = [("Modelo", datos["repositorio"]), ("Revisión", datos["revision"][:12] + "…"),
                 ("Licencia", datos["licencia"]), ("Tamaño aproximado", datos["tamano"]),
                 ("Destino", str(datos["directorio"])),
                 ("Espacio libre", f"{datos['espacio_libre'] / 1e9:.1f} GB")]
        for n, (etiqueta, valor) in enumerate(filas):
            ttk.Label(cuerpo, text=etiqueta, style="Suave.TLabel").grid(row=n, column=0, sticky="w", padx=(0, 16), pady=2)
            ttk.Label(cuerpo, text=valor, style="Campo.TLabel", wraplength=tema.px(420)).grid(row=n, column=1, sticky="w", pady=2)
        self.barra = ttk.Progressbar(cuerpo, mode="determinate", maximum=1000, length=tema.px(460),
                                     style="CupoOk.Horizontal.TProgressbar")
        self.barra.grid(row=len(filas), column=0, columnspan=2, sticky="we", pady=(16, 4))
        self.estado = tk.Label(cuerpo, text="Sin descargar.", font=tema.f(9), fg=COLOR["suave"],
                               bg=COLOR["tarjeta"], anchor="w", justify="left", wraplength=tema.px(460))
        self.estado.grid(row=len(filas) + 1, column=0, columnspan=2, sticky="we")
        pie = tk.Frame(self, bg=COLOR["fondo"])
        pie.pack(fill="x", padx=16, pady=(0, 16))
        self.btn_descargar = Boton(pie, "Descargar", icono="exportar", variante="primario", comando=self.descargar)
        self.btn_descargar.pack(side="right")
        self.btn_despues = Boton(pie, "Más tarde", comando=self.posponer)
        self.btn_despues.pack(side="right", padx=(0, 8))
        if not config.PERMITIR_DESCARGA_MODELOS:
            self.btn_descargar.habilitar(False)
            self.estado.configure(text="La descarga está desactivada (BIBLIOTECA_PERMITIR_DESCARGA=0). "
                                       "Usa:  python gestionar_modelos.py descargar", fg=COLOR["aviso"])
        self.protocol("WM_DELETE_WINDOW", self.posponer)
        centrar(self, padre)
        self.deiconify()
        self.grab_set()

    def posponer(self):
        if self._descargando:
            return
        self.grab_release()
        self.destroy()
        if self.al_posponer:
            self.al_posponer()

    def _progreso(self, hechos: int, total: int, archivo: str):
        ahora = time.monotonic()
        if hechos < total and ahora - self._ultimo_aviso < 0.25:
            return
        self._ultimo_aviso = ahora
        self.app.tareas.en_interfaz(self._mostrar_progreso, hechos, total, archivo)

    def _mostrar_progreso(self, hechos: int, total: int, archivo: str):
        if not self.winfo_exists():
            return
        proporcion = hechos / total if total else 0
        velocidad = hechos / max(time.monotonic() - self._inicio, 0.001) / 1e6
        self.barra.configure(value=int(proporcion * 1000))
        self.estado.configure(text=f"{proporcion:.0%} · {hechos / 1e6:.0f} de {total / 1e6:.0f} MB · "
                                   f"{velocidad:.1f} MB/s · {archivo or 'preparando…'}", fg=COLOR["suave"])

    def descargar(self):
        self._descargando = True
        self._inicio = time.monotonic()
        self.btn_descargar.habilitar(False)
        self.btn_despues.habilitar(False)
        self.estado.configure(text="Consultando Hugging Face Hub…", fg=COLOR["suave"])

        def trabajo():
            return self.app.servicio.descargar_modelo(self.clave, self._progreso)

        def listo(resultado):
            self._descargando = False
            if not self.winfo_exists():
                return
            self.barra.configure(value=1000)
            self.estado.configure(text=f"Descarga verificada: {resultado['dimensiones']} dimensiones en "
                                       f"{resultado['dispositivo']}.", fg=COLOR["exito"])
            self.app.notificador.mostrar("Modelo descargado y verificado.", "exito")
            self.after(900, self._cerrar_completado)

        def fallo(error):
            self._descargando = False
            if not self.winfo_exists():
                return
            mensaje = describir_error(error)["mensaje"]
            self.estado.configure(text=mensaje, fg=COLOR["peligro"])
            self.btn_descargar.texto("Reintentar")
            self.btn_descargar.habilitar(True)
            self.btn_despues.habilitar(True)
        self.app.tareas.ejecutar(trabajo, listo, fallo, "Descargando el modelo de embeddings…", independiente=True)

    def _cerrar_completado(self):
        self.grab_release()
        self.destroy()
        if self.al_completar:
            self.al_completar()
