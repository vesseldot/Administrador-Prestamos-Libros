import tkinter as tk
from tkinter import ttk

import config
from ui.acceso import CambioContrasena
from ui.componentes import Boton, Dialogo, Tabla, caja_texto, confirmar, encabezado_tarjeta, escribir, tarjeta
from ui.tema import COLOR
from ui.vistas.base import Vista, badge
from ui.vistas.libros import mostrar_reporte_lote
from ui.vistas.personas import mostrar_aviso

COLUMNAS_MODELOS = [("clave", "Modelo", 260), ("dim", "Dim.", 70, "center", False),
                    ("max_tokens", "Tokens", 70, "center", False), ("estilo_txt", "Consultas", 105, "w", False),
                    ("descargado", "En equipo", 90, "center", False), ("tamano", "Tamaño", 80, "w", False),
                    ("nota", "Nota", 400)]


def _fila_info(padre, fila, etiqueta, valor):
    ttk.Label(padre, text=etiqueta, style="Suave.TLabel").grid(row=fila, column=0, sticky="nw", padx=(0, 18), pady=3)
    lbl = ttk.Label(padre, text=valor, style="Campo.TLabel", wraplength=520, justify="left")
    lbl.grid(row=fila, column=1, sticky="w", pady=3)
    return lbl


class VistaConfiguracion(Vista):
    titulo = "Configuración"
    subtitulo = "Modelo semántico, sincronización entre bases, seguridad y estado del sistema."

    def construir(self):
        self.pestanas = ttk.Notebook(self.cuerpo)
        self.pestanas.pack(fill="both", expand=True)
        self._construir_modelo()
        self._construir_sincronizacion()
        self._construir_seguridad()
        self._construir_sistema()
        self.pestanas.bind("<<NotebookTabChanged>>", lambda e: self.refrescar())

    def _pestana(self, texto):
        marco = ttk.Frame(self.pestanas, padding=(0, 14, 0, 0))
        self.pestanas.add(marco, text=texto)
        return marco

    def _construir_modelo(self):
        marco = self._pestana("Modelo semántico")
        superior = tarjeta(marco)
        superior.pack(fill="x")
        fila, _ = encabezado_tarjeta(superior, "Modelo de embeddings",
                                     "Indexar y consultar siempre con el mismo modelo. Cada modelo conserva lo que ya "
                                     "procesó: al cambiar solo se calculan los libros que le faltan.")
        self.badge_modelo = badge(fila, "", "Info")
        self.badge_modelo.pack(side="right", anchor="n")
        self.tabla_modelos = Tabla(superior, COLUMNAS_MODELOS, alto=5, clave_id="clave")
        self.tabla_modelos.pack(fill="x")
        botones = tk.Frame(superior, bg=COLOR["tarjeta"])
        botones.pack(fill="x", pady=(12, 0))
        Boton(botones, "Usar el modelo seleccionado", icono="sincronizar", variante="primario",
              comando=self.cambiar_modelo).pack(side="left")
        Boton(botones, "Revisar sinopsis que se cortan", icono="documento",
              comando=self.revisar_cortes).pack(side="left", padx=8)
        Boton(botones, "Descargar modelo seleccionado", icono="exportar", comando=self.descargar_modelo,
              ayuda="Descarga desde Hugging Face Hub la revisión fijada del modelo seleccionado.").pack(side="left")

        prueba = tarjeta(marco)
        prueba.pack(fill="both", expand=True, pady=(12, 0))
        encabezado_tarjeta(prueba, "Prueba una sinopsis", "Cuenta los tokens con el modelo seleccionado en la tabla.")
        cuerpo = tk.Frame(prueba, bg=COLOR["tarjeta"])
        cuerpo.pack(fill="both", expand=True)
        cuerpo.columnconfigure(0, weight=1, uniform="p")
        cuerpo.columnconfigure(1, weight=1, uniform="p")
        cuerpo.rowconfigure(0, weight=1)
        izquierda = tk.Frame(cuerpo, bg=COLOR["tarjeta"])
        izquierda.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        Boton(izquierda, "Contar tokens", icono="aceptar", variante="primario", comando=self.contar_tokens).pack(
            side="bottom", anchor="w", pady=(8, 0))
        self.texto_prueba = caja_texto(izquierda, 6)
        self.texto_prueba.pack(fill="both", expand=True)
        self.salida_modelo = caja_texto(cuerpo, 6, solo_lectura=True, mono=True)
        self.salida_modelo.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

    def _construir_sincronizacion(self):
        marco = self._pestana("Sincronización")
        caja = tarjeta(marco)
        caja.pack(fill="both", expand=True)
        encabezado_tarjeta(caja, "Redis ↔ ChromaDB",
                           "Redis es la fuente de verdad de identificadores, metadatos y disponibilidad; Chroma "
                           "guarda sinopsis, embeddings y una copia de los metadatos. Cada operación compensa los "
                           "fallos, y aquí puedes revisar y reparar cualquier diferencia.")
        botones = tk.Frame(caja, bg=COLOR["tarjeta"])
        botones.pack(fill="x", pady=(0, 12))
        Boton(botones, "Revisar", icono="buscar", variante="primario", comando=self.revisar_sync).pack(side="left")
        Boton(botones, "Reparar metadatos", icono="sincronizar", comando=self.reparar_sync,
              ayuda="Copia a Chroma los metadatos de Redis y limpia los pendientes.").pack(side="left", padx=8)
        Boton(botones, "Importar documentos huérfanos", icono="importar", comando=self.importar_huerfanos,
              ayuda="Da de alta en Redis los libros que solo existen en Chroma (migración del esquema "
                    "anterior). Nunca borra documentos.").pack(side="left")
        self.salida_sync = caja_texto(caja, 16, solo_lectura=True, mono=True)
        self.salida_sync.pack(fill="both", expand=True)

    def _construir_seguridad(self):
        marco = self._pestana("Seguridad")
        izquierda = tarjeta(marco)
        izquierda.pack(fill="x")
        encabezado_tarjeta(izquierda, "Protección de datos personales")
        rejilla = tk.Frame(izquierda, bg=COLOR["tarjeta"])
        rejilla.pack(fill="x")
        _fila_info(rejilla, 0, "Cifrado", "AES-256-GCM por campo, con datos asociados persona/campo "
                                          "(detecta alteraciones e intercambios de valores).")
        _fila_info(rejilla, 1, "Derivación de llaves", "HKDF-SHA256: una llave para cifrar y otra para el índice "
                                                       "ciego HMAC del correo.")
        self.lbl_llave = _fila_info(rejilla, 2, "Llave maestra", "")
        self.lbl_heredado = _fila_info(rejilla, 3, "Cifrado heredado", "")
        _fila_info(rejilla, 4, "Visualización", "Correo y teléfono enmascarados en listados; datos completos solo "
                                                "en la ficha ARCO o a petición, con sesión autenticada.")
        _fila_info(rejilla, 5, "Registro de eventos", "La bitácora y el archivo de log solo guardan identificadores, "
                                                      "nunca datos personales.")
        botones = tk.Frame(izquierda, bg=COLOR["tarjeta"])
        botones.pack(fill="x", pady=(12, 0))
        self.btn_migrar = Boton(botones, "Migrar cifrado heredado", icono="sincronizar", comando=self.migrar_cifrado)
        self.btn_migrar.pack(side="left")
        Boton(botones, "Aviso de privacidad", icono="escudo",
              comando=lambda: mostrar_aviso(self)).pack(side="left", padx=8)

        acceso = tarjeta(marco)
        acceso.pack(fill="x", pady=(12, 0))
        encabezado_tarjeta(acceso, "Acceso del operador",
                           f"La contraseña se guarda como hash scrypt. La sesión se bloquea tras "
                           f"{config.MINUTOS_BLOQUEO_INACTIVIDAD} minutos de inactividad y tras "
                           f"{config.MAX_INTENTOS_ACCESO} intentos fallidos se espera "
                           f"{config.SEGUNDOS_ESPERA_TRAS_FALLOS} segundos.")
        botones = tk.Frame(acceso, bg=COLOR["tarjeta"])
        botones.pack(fill="x")
        Boton(botones, "Cambiar contraseña", icono="candado", comando=self.cambiar_contrasena).pack(side="left")
        Boton(botones, "Bloquear ahora", icono="candado", comando=self.app.bloquear).pack(side="left", padx=8)

    def _construir_sistema(self):
        marco = self._pestana("Sistema")
        caja = tarjeta(marco)
        caja.pack(fill="x")
        encabezado_tarjeta(caja, "Conexiones y almacenamiento")
        self.rejilla_sistema = tk.Frame(caja, bg=COLOR["tarjeta"])
        self.rejilla_sistema.pack(fill="x")
        inferior = ttk.Frame(marco)
        inferior.pack(fill="x", pady=(12, 0))
        inferior.columnconfigure(0, weight=1, uniform="sistema")
        inferior.columnconfigure(1, weight=1, uniform="sistema")
        datos = tarjeta(inferior)
        datos.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        encabezado_tarjeta(datos, "Datos de ejemplo",
                           "Importa todos los archivos datos/libros_*.csv. Los libros que ya existan se reportan "
                           "como rechazados, así que puede ejecutarse más de una vez.")
        self.lbl_archivos = ttk.Label(datos, text="", style="Suave.TLabel", justify="left")
        self.lbl_archivos.pack(anchor="w", pady=(0, 10))
        Boton(datos, "Cargar datos de ejemplo", icono="importar", variante="primario",
              comando=self.cargar_ejemplos).pack(anchor="w")

        portadas = tarjeta(inferior)
        portadas.grid(row=0, column=1, sticky="nsew")
        encabezado_tarjeta(portadas, "Portadas de los libros",
                           "Se buscan en Open Library por ISBN y por título. Las que no se encuentren pueden "
                           "elegirse a mano desde la ficha del libro.")
        self.lbl_portadas = ttk.Label(portadas, text="", style="Suave.TLabel", justify="left", wraplength=460)
        self.lbl_portadas.pack(anchor="w", pady=(0, 8))
        self.barra_portadas = ttk.Progressbar(portadas, mode="determinate", maximum=1)
        self.lbl_progreso_portadas = ttk.Label(portadas, text="", style="Suave.TLabel")
        botones = tk.Frame(portadas, bg=COLOR["tarjeta"])
        botones.pack(fill="x", side="bottom")
        self.btn_portadas = Boton(botones, "Descargar portadas faltantes", icono="imagen", variante="primario",
                                  comando=self.descargar_portadas)
        self.btn_portadas.pack(side="left")
        self.btn_detener_portadas = Boton(botones, "Detener", icono="cerrar",
                                          comando=self.servicio.detener_descarga_portadas)
        self.btn_detener_portadas.pack(side="left", padx=8)
        self.btn_detener_portadas.habilitar(False)
        self._descargando_portadas = False

    def refrescar(self):
        indice = self.pestanas.index("current")
        if indice == 0:
            self._refrescar_modelos()
        elif indice == 2:
            self._refrescar_seguridad()
        elif indice == 3:
            self._refrescar_sistema()

    def _refrescar_modelos(self):
        info = self.servicio.info_modelo()
        self.badge_modelo.configure(
            text=f"Activo: {info['modelo']} · {info['dimensiones']} dim · {info['dispositivo']}")
        self._modelos = {m["clave"]: m for m in self.servicio.catalogo_modelos()}
        filas = [{**m, "estilo_txt": {"e5": "prefijos e5", "instruccion": "instrucción"}.get(m["estilo"], "directas")}
                 for m in self._modelos.values()]
        self.tabla_modelos.cargar(filas)
        if not self.tabla_modelos.seleccion():
            self.tabla_modelos.seleccionar(info["modelo"])

    def _modelo_seleccionado(self) -> str:
        fila = self.tabla_modelos.fila_seleccionada()
        return fila["clave"] if fila else self.servicio.clave_modelo

    def _descargado(self, clave: str) -> bool:
        return self.servicio.estado_modelo(clave)["disponible"]

    def descargar_modelo(self):
        clave = self._modelo_seleccionado()
        if self._descargado(clave):
            return self.aviso(f"{clave} ya está descargado en este equipo.")
        al_completar = self.app._precargar_modelo if clave == self.servicio.clave_modelo else None

        def completado():
            self._refrescar_modelos()
            if al_completar:
                al_completar()
        self.app.ofrecer_descarga(clave, completado)

    def cambiar_modelo(self):
        clave = self._modelo_seleccionado()
        if clave == self.servicio.clave_modelo:
            return self.aviso("Ese modelo ya está activo.")
        if not self._descargado(clave):
            return self.app.ofrecer_descarga(clave, self._refrescar_modelos)
        total = self.servicio.contar_libros()
        if not confirmar(self, "Cambiar modelo", f"¿Cambiar a {clave} con los {total} libros? Se conserva lo que ese modelo "
                         "ya procesó y solo se calculan los libros que le faltan. La búsqueda usará el nuevo "
                         "modelo cuando termine.", "Cambiar de modelo"):
            return

        def progreso(hechos, total_):
            self.app.mensaje_estado(f"Calculando libros pendientes con {clave}… {hechos}/{total_}")

        def listo(cantidad):
            self._refrescar_modelos()
            self.app.actualizar_modelo()
            resumen = self.servicio.resumen_ultimo_cambio or {}
            escribir(self.salida_modelo, f"{clave} listo con {cantidad} libros: "
                                         f"{resumen.get('reutilizados', 0)} reutilizados, "
                                         f"{resumen.get('calculados', 0)} calculados y "
                                         f"{resumen.get('eliminados', 0)} eliminados.")
            self.exito(f"Modelo cambiado a {clave}.")
        self.tarea(lambda: self.servicio.cambiar_modelo(clave, self.app.tareas.progreso(progreso)), listo,
                   f"Cargando {clave} y sincronizando libros…")

    def contar_tokens(self):
        texto = self.texto_prueba.get("1.0", "end").strip()
        if not texto:
            return
        clave = self._modelo_seleccionado()

        def listo(r):
            if r["cabe"]:
                mensaje = (f"✓ {r['tokens']} tokens ({r['palabras']} palabras).\n"
                           f"Cabe completa en {r['clave']} (máx. {r['maximo']}).")
            else:
                mensaje = (f"✗ {r['tokens']} tokens ({r['palabras']} palabras).\n{r['clave']} solo lee "
                           f"{r['maximo']}: se pierden {r['tokens'] - r['maximo']} tokens del final.")
            escribir(self.salida_modelo, mensaje)
        self.tarea(lambda: self.servicio.contar_tokens(texto, clave), listo, f"Contando tokens con {clave}…")

    def revisar_cortes(self):
        clave = self._modelo_seleccionado()

        def listo(r):
            lineas = [f"{r['clave']} (máx. {r['maximo']} tokens): {r['cortadas']} de {len(r['resultados'])} "
                      "sinopsis se cortan.", ""]
            for libro_id, titulo, cantidad in r["resultados"][:60]:
                marca = "✗ se corta" if cantidad > r["maximo"] else "✓"
                lineas.append(f"{marca:11} {cantidad:4} tokens  {libro_id:9} {titulo}")
            escribir(self.salida_modelo, "\n".join(lineas))
        self.tarea(lambda: self.servicio.revisar_cortes(clave), listo, f"Contando tokens del catálogo con {clave}…")

    def _mostrar_informe(self, informe, extra=""):
        def lista(titulo, ids):
            if not ids:
                return [f"{titulo}: 0"]
            return [f"{titulo}: {len(ids)}", f"   {', '.join(ids[:40])}{' …' if len(ids) > 40 else ''}"]
        lineas = ["Estado: " + ("CONSISTENTE ✓" if informe.consistente else "CON DIFERENCIAS"), ""]
        lineas += lista("Libros en Redis sin documento en Chroma", informe.faltan_en_chroma)
        lineas += lista("Documentos en Chroma sin registro en Redis", informe.huerfanos_en_chroma)
        lineas += lista("Metadatos distintos entre bases", informe.metadatos_distintos)
        lineas += lista("Operaciones pendientes de sincronizar", informe.pendientes)
        if extra:
            lineas += ["", extra]
        escribir(self.salida_sync, "\n".join(lineas))

    def revisar_sync(self):
        self.tarea(self.servicio.revisar_sincronizacion, self._mostrar_informe, "Comparando Redis y Chroma…")

    def reparar_sync(self):
        def trabajo():
            resultado = self.servicio.reparar_sincronizacion()
            return resultado, self.servicio.revisar_sincronizacion()

        def listo(datos):
            resultado, informe = datos
            extra = f"Reparación: {resultado['corregidos']} libro(s) corregidos."
            if resultado["sin_sinopsis"]:
                extra += (f"\n{len(resultado['sin_sinopsis'])} libro(s) no tienen sinopsis en Chroma y deben "
                          "editarse o darse de alta de nuevo.")
            self._mostrar_informe(informe, extra)
            self.exito("Reparación terminada.")
        self.tarea(trabajo, listo, "Reparando sincronización…")

    def importar_huerfanos(self):
        def listo(resultado):
            mostrar_reporte_lote(self, resultado)
            self.revisar_sync()
        self.tarea(self.servicio.importar_huerfanos, listo, "Importando documentos huérfanos…")

    def _refrescar_seguridad(self):
        estado = self.servicio.estado_seguridad()
        self.lbl_llave.configure(text=f"Presente · {estado['origen_llave']}")
        legada = "presente (solo lectura)" if estado["llave_legada"] else "no existe"
        self.lbl_heredado.configure(text=f"{estado['cifrado_heredado']} persona(s) con cifrado Fernet del esquema "
                                         f"anterior · llave heredada {legada}")
        self.btn_migrar.habilitar(estado["cifrado_heredado"] > 0)

    def migrar_cifrado(self):
        if confirmar(self, "Migrar cifrado", "¿Volver a cifrar con AES-256-GCM los registros heredados?", "Migrar"):
            cantidad = self.servicio.migrar_cifrado_heredado()
            self.exito(f"{cantidad} registro(s) migrados a AES-256-GCM.")
            self._refrescar_seguridad()

    def cambiar_contrasena(self):
        CambioContrasena(self, self.app.acceso, lambda: self.exito("Contraseña actualizada."))

    def _refrescar_sistema(self):
        for hijo in self.rejilla_sistema.winfo_children():
            hijo.destroy()

        def listo(info):
            filas = [
                ("Redis", f"{info['redis_host']}:{info['redis_port']} · base {info['redis_db']} · servidor "
                          f"{info['redis_version']}"),
                ("Espacio de nombres", f"prefijo '{info['prefijo']}' · {info['llaves_propias']} llave(s) · "
                                       f"esquema v{info['esquema']}"),
                ("ChromaDB", info["chroma_path"]),
                ("Colección activa", f"{info['coleccion']} · {info['documentos']} documento(s)"),
                ("Modelo", f"{info['modelo']} · {info['dispositivo']}"),
                ("Modelos descargados en", f"{info['dir_modelos']} · descarga "
                                           f"{'permitida' if info['descarga_permitida'] else 'desactivada'}"),
                ("GPU", info["gpu"]),
                ("Entorno", f"Python {info['python']} · torch {info['torch']}"),
            ]
            for n, (etiqueta, valor) in enumerate(filas):
                _fila_info(self.rejilla_sistema, n, etiqueta, valor)
        self.tarea(self.servicio.info_sistema, listo, "Consultando el sistema…")
        archivos = self.servicio.archivos_ejemplo()
        self.lbl_archivos.configure(text="\n".join(f"•  {a.name}" for a in archivos) or "No hay archivos de ejemplo.")
        self._refrescar_portadas()

    def _refrescar_portadas(self):
        estado = self.servicio.estado_portadas()
        busqueda = "permitida" if estado["descarga_permitida"] else "desactivada (BIBLIOTECA_DESCARGAR_PORTADAS=0)"
        self.lbl_portadas.configure(text=f"{estado['con_portada']} de {estado['total']} libros con portada\n"
                                         f"Carpeta: {estado['carpeta']}\nBúsqueda en internet: {busqueda}")
        faltan = estado["con_portada"] < estado["total"]
        self.btn_portadas.habilitar(estado["descarga_permitida"] and faltan and not self._descargando_portadas)

    def descargar_portadas(self):
        self._descargando_portadas = True
        self.btn_portadas.habilitar(False)
        self.btn_detener_portadas.habilitar(True)
        self.barra_portadas.configure(value=0, maximum=1)
        self.barra_portadas.pack(fill="x", pady=(0, 4))
        self.lbl_progreso_portadas.configure(text="Preparando…")
        self.lbl_progreso_portadas.pack(anchor="w", pady=(0, 10))

        def progreso(hechos, total, titulo):
            self.barra_portadas.configure(maximum=max(total, 1), value=hechos)
            self.lbl_progreso_portadas.configure(text=f"{hechos} de {total} · {titulo}")

        def terminar():
            self._descargando_portadas = False
            self.btn_detener_portadas.habilitar(False)
            self.barra_portadas.pack_forget()
            self.lbl_progreso_portadas.pack_forget()
            self._refrescar_portadas()

        def listo(resultado):
            terminar()
            revisados = len(resultado.descargadas) + len(resultado.sin_portada)
            mensaje = (f"Libros revisados: {revisados} de {resultado.total}\n"
                       f"Portadas descargadas: {len(resultado.descargadas)}\n"
                       f"Sin portada en Open Library: {len(resultado.sin_portada)}")
            if resultado.cancelado:
                mensaje += "\nLa descarga se detuvo a petición del operador."
            detalle = ""
            if resultado.sin_portada:
                detalle = ("Puedes elegir una imagen para estos libros desde su ficha:\n"
                           + "\n".join(f"{l['id']} · {l['titulo']}" for l in resultado.sin_portada))
            tipo = "exito" if resultado.descargadas and not resultado.sin_portada else "info"
            self.wait_window(Dialogo(self, "Portadas de los libros", mensaje, tipo, detalle=detalle))

        def fallo(error):
            terminar()
            self.app.manejar_error(error)
        self.app.tareas.ejecutar(
            lambda: self.servicio.descargar_portadas(self.app.tareas.progreso(progreso)), listo, fallo,
            "Descargando portadas desde Open Library…", independiente=True)

    def cargar_ejemplos(self):
        if not self.servicio.archivos_ejemplo():
            return self.aviso("No hay archivos datos/libros_*.csv.")

        def progreso(hechos, total):
            self.app.mensaje_estado(f"Calculando embeddings… {hechos}/{total}")

        def listo(resultado):
            mostrar_reporte_lote(self, resultado)
            self._refrescar_sistema()
        self.tarea(lambda: self.servicio.importar_datos_ejemplo(self.app.tareas.progreso(progreso)), listo,
                   "Importando datos de ejemplo…")
