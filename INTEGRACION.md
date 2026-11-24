# Integración frontend ↔ backend

Este documento es el **contrato** entre la interfaz Tkinter (`ui/`) y el backend. Quien trabaje en el frontend puede rediseñar por completo la experiencia visual siempre que consuma el backend **solo** a través de lo que aquí se describe.

Todas las funciones listadas existen en el código. La prueba `tests/test_arquitectura.py` verifica automáticamente que `ui/` no use nada más.

## 1. Capas

```
┌──────────────────────────── Frontend ─────────────────────────────┐
│ ui/  tema · iconos · componentes · acceso · descarga_modelo ·     │
│      app (ventana, navegación) · vistas/*                         │
│      tareas.py (hilo trabajador)                                  │
└───────────────┬───────────────────────────────────────────────────┘
                │  self.servicio  (ServicioBiblioteca: API pública)
                │  describir_error(error)
┌───────────────▼──────────────── Backend ──────────────────────────┐
│ servicios.py  lógica de negocio y coordinación Redis ↔ Chroma     │
│ db_catalogo · db_personas · db_prestamos · db_redis  → Redis      │
│ db_libros                                            → ChromaDB   │
│ modelos · gestor_modelos                             → modelo     │
│ seguridad (cifrado, ControlAcceso) · validaciones · config        │
└───────────────────────────────────────────────────────────────────┘
```

## 2. Reglas de la integración

1. **La interfaz solo habla con `ServicioBiblioteca`.** Dentro de una vista se accede como `self.servicio` (o `self.app.servicio`). Nunca se usan sus atributos internos `r`, `catalogo`, `indice`, `personas`, `prestamos`, `actividad`, `llaves`, `portadas` ni `cliente_portadas`.
2. **Importaciones permitidas en `ui/`** (todas son funciones puras o constantes, sin acceso a bases de datos):

   | Módulo | Nombres permitidos |
   |---|---|
   | `servicios` | `describir_error` |
   | `validaciones` | `ESTADOS_MEXICO`, `GENEROS_PERSONA`, `OCUPACIONES`, `TIPOS_USUARIO`, `TIPOS_PASTA`, `normalizar_texto`, `clave_natural` |
   | `seguridad` | `AVISO_PRIVACIDAD`, `enmascarar_correo`, `enmascarar_telefono` |
   | `config` | Solo lectura de constantes (`MAX_RESULTADOS_BUSQUEDA`, `MINUTOS_BLOQUEO_INACTIVIDAD`, `DIR_DATOS`…) |

   Prohibido: `redis`, `chromadb`, `db_*`, `modelos`, `gestor_modelos`, `portadas`, `PIL` (Pillow), `torch`, `sentence_transformers`, `huggingface_hub`, `cryptography`. Las portadas llegan ya convertidas a PNG y se muestran con `tk.PhotoImage` (componente `ui.componentes.Portada`).
3. **Nada pesado en el hilo de Tkinter.** Todo lo que toca ChromaDB o el modelo se ejecuta con `self.tarea(...)` (ver la sección 4). Las operaciones que solo usan Redis son rápidas y pueden llamarse directamente. La columna «Hilo» de la sección 3 indica cuál es cuál.
4. **Los errores llegan como excepciones** y se muestran con `describir_error` (sección 5). La interfaz no traduce excepciones por su cuenta.
5. **Datos personales.** Los métodos de personas devuelven los datos **descifrados**. La interfaz es responsable de **enmascarar** el correo y el teléfono en listados (`enmascarar_correo`, `enmascarar_telefono`), de no escribirlos en el registro y de mostrarlos completos solo en la ficha ARCO o a petición.
6. **¿Falta una función?** No accedas a la base de datos «solo esta vez»: abre un issue con la etiqueta `backend` describiendo qué necesitas. Backend la añade a la API de `servicios.py`, con su prueba y su documentación aquí.

## 3. Referencia de la API (`ServicioBiblioteca`)

Hilo: **UI** = puede llamarse directamente (solo Redis o cálculo ligero). **Tarea** = usar `self.tarea(...)`.

### 3.1 Libros

| Método | Devuelve | Excepciones | Hilo |
|---|---|---|---|
| `catalogo_libros()` | `list[dict]` de libros (3.6) con `estado` y `prestado_a` | Redis | UI |
| `filtrar_catalogo(libros, texto="", genero="", idioma="", estado="")` | `list[dict]` filtrada (sin acentos ni mayúsculas) | — | UI |
| `obtener_libro(libro_id)` | `dict` con `sinopsis`, `indexado`, `prestamo` (o `None`), `estado` y `portada` (dict o `None`); `None` si no existe | Redis, Chroma | Tarea |
| `validar_alta(datos)` | `dict` limpio | `ValueError` (campos, id o ISBN duplicado) | UI |
| `alta_libro(datos)` | `str` id | `ValueError`, `ModeloNoDisponible` | Tarea |
| `actualizar_libro(libro_id, datos)` | `None` | `ValueError` (no existe, campos, ISBN de otro libro) | Tarea |
| `eliminar_libro(libro_id)` | `None` (también borra su portada) | `ValueError` (no existe, está prestado) | Tarea |
| `importar_archivo(ruta, progreso=None)` | `ResultadoLote` | `ValueError` (JSON mal formado), `OSError` (no se puede leer) | Tarea |
| `importar_lote(registros, progreso=None)` | `ResultadoLote` | — (las filas inválidas van a `rechazados`) | Tarea |
| `importar_datos_ejemplo(progreso=None)` | `ResultadoLote` | — | Tarea |
| `archivos_ejemplo()` | `list[Path]` de `datos/libros_*.csv` | — | UI |
| `contar_libros()` | `int` | Redis | UI |
| `buscar_libros(texto, cantidad, solo_disponibles=False)` | `list[dict]` ordenada por `similitud` (0–1); `[]` si `texto` está vacío | `ModeloNoDisponible` | Tarea |

`progreso` es un callable `progreso(hechos, total)` que se invoca **desde el hilo trabajador**: envuélvelo con `self.app.tareas.progreso(funcion)` para que se ejecute en la interfaz.

#### Portadas

Las portadas son archivos en `BIBLIOTECA_DIR_PORTADAS` (no están en Redis ni en ChromaDB). Se obtienen de Open Library o de una imagen del equipo.

| Método | Devuelve | Excepciones | Hilo |
|---|---|---|---|
| `portada_libro(libro_id, ancho=180, alto=270)` | `bytes` PNG ajustado a ancho×alto píxeles, o `None` si no hay portada | — | Tarea |
| `asignar_portada(libro_id, ruta)` | `dict` `{origen, fuente, fecha}` | `ValueError` (libro inexistente, archivo ilegible, no es imagen, más de 15 MB, menos de 40 px) | Tarea |
| `quitar_portada(libro_id)` | `bool` (si había portada) | — | Tarea |
| `buscar_portada(libro_id, reemplazar=False)` | `dict` `{encontrada, nueva, portada}` | `ValueError` (libro inexistente, búsqueda desactivada), `ErrorPortada` (sin red) | **Tarea independiente** |
| `descargar_portadas(progreso=None)` | `ResultadoPortadas` (3.6); solo busca las que faltan | `ValueError` (desactivada), `ErrorPortada` (tras 3 fallos de red seguidos) | **Tarea independiente** |
| `detener_descarga_portadas()` | `None`: la descarga termina tras el libro en curso | — | UI |
| `estado_portadas()` | `dict` `{total, con_portada, descarga_permitida, carpeta}` | Redis | UI |

`progreso` de `descargar_portadas` recibe `(hechos, total, titulo)`. Las búsquedas en Open Library hacen una pausa de 1 s entre peticiones, así que conviene ejecutarlas con `self.app.tareas.ejecutar(..., independiente=True)` para no bloquear la cola del modelo.

### 3.2 Personas

| Método | Devuelve | Excepciones | Hilo |
|---|---|---|---|
| `registrar_persona(datos)` | `str` id (`P0001`…) | `ValueError` (validación, aviso no aceptado, correo duplicado) | UI |
| `actualizar_persona(persona_id, datos)` | `None` | `ValueError` (incluye `PersonaNoEncontrada`) | UI |
| `obtener_persona(persona_id)` | `dict` (3.6) o `None` | Redis | UI |
| `buscar_personas(texto="", tipo_usuario=None, solo_con_prestamos=False)` | `list[dict]` (busca por nombre, apellidos, id, tipo, ocupación, ciudad y estado; nunca por correo ni teléfono) | Redis | UI |
| `listar_personas()` | `list[dict]` | Redis | UI |
| `contar_personas()` | `int` | Redis | UI |
| `eliminar_persona(persona_id)` | `None` (cancelación ARCO) | `ValueError` (no existe, tiene préstamos activos) | UI |
| `exportar_persona(persona_id)` | `dict` con los datos y el historial, para guardar como JSON | `ValueError` (no existe) | UI |

### 3.3 Préstamos

| Método | Devuelve | Excepciones | Hilo |
|---|---|---|---|
| `prestar(persona_id, libro_ids)` | `list[dict]` de préstamos creados (3.6) | `ValueError` (persona o libro inexistente, más de 3, sin cupo, no disponible) | Tarea |
| `devolver(persona_id, prestamo_ids=None)` | `list[dict]` devueltos (`None` = todos los activos) | `ValueError` (vacío, ajeno o ya devuelto) | Tarea |
| `prestamos_activos(persona_id=None)` | `list[dict]` de la persona o de toda la biblioteca | Redis | UI |
| `historial_prestamos(persona_id)` | `list[dict]`, del más reciente al más antiguo | Redis | UI |
| `cupo_disponible(persona_id)` | `int` (0–3) | Redis | UI |
| `max_libros_por_persona` *(propiedad)* | `int` (3) | — | UI |
| `personas_con_prestamos()` | `list[dict]` de personas, cada una con su clave `prestamos` | Redis | Tarea (lista grande) |

`prestar` es **todo o nada**: si un libro falla, no se presta ninguno.

### 3.4 Dashboard, sistema y sincronización

| Método | Devuelve | Excepciones | Hilo |
|---|---|---|---|
| `estadisticas()` | `dict` (3.6) | Redis, Chroma | Tarea |
| `actividad_reciente(cantidad=20)` | `list[dict]` `{fecha, tipo, descripcion, refs}` | Redis | UI |
| `redis_disponible()` | `bool` (nunca lanza) | — | UI |
| `descripcion_conexion()` | `str` para la barra de estado | — | UI |
| `info_sistema()` | `dict`: `redis_host`, `redis_port`, `redis_db`, `redis_version`, `prefijo`, `llaves_propias`, `esquema`, `chroma_path`, `coleccion`, `documentos`, `modelo`, `dispositivo`, `dir_modelos`, `descarga_permitida`, `gpu`, `python`, `torch`… | Redis | Tarea |
| `estado_seguridad()` | `dict`: `origen_llave`, `cifrado_heredado` (int), `llave_legada` (bool) | Redis | UI |
| `migrar_cifrado_heredado()` | `int` de registros migrados | Redis | UI |
| `revisar_sincronizacion()` | `InformeSincronizacion` | Redis, Chroma | Tarea |
| `reparar_sincronizacion()` | `dict`: `corregidos`, `sin_sinopsis`, `huerfanos` | Redis, Chroma | Tarea |
| `importar_huerfanos()` | `ResultadoLote` | Redis, Chroma | Tarea |

### 3.5 Modelo semántico

| Método | Devuelve | Excepciones | Hilo |
|---|---|---|---|
| `clave_modelo` *(propiedad)* | `str` del modelo activo | — | UI |
| `resumen_ultimo_cambio` *(propiedad)* | `dict` con `reutilizados`, `calculados` y `eliminados` del último cambio de modelo, o `None` | — | UI |
| `info_modelo()` | `dict`: `modelo`, `modelo_repositorio`, `dimensiones`, `max_tokens`, `modelo_cargado`, `dispositivo` | — | UI |
| `modelo_pendiente_de_descarga()` | `bool` | — | UI |
| `precargar_modelo()` | `dict` (como `info_modelo`) | `ModeloNoDisponible` | Tarea |
| `catalogo_modelos()` | `list[dict]`: `clave`, `nombre_completo`, `revision`, `licencia`, `dim`, `max_tokens`, `estilo`, `tamano`, `nota`, `descargado`, `activo`… | — | UI |
| `estado_modelo(clave=None)` | `dict`: `repositorio`, `revision`, `licencia`, `tamano`, `disponible`, `faltantes`, `directorio`, `espacio_libre`… | — | UI |
| `descargar_modelo(clave=None, progreso=None)` | `dict` `{dimensiones, dispositivo}` tras validar | `SinConexion`, `EspacioInsuficiente`, `ErrorDescarga` | **Tarea independiente** (`independiente=True`) |
| `contar_tokens(texto, clave=None)` | `dict` `{clave, tokens, palabras, maximo, cabe}` | `ModeloNoDisponible` | Tarea |
| `revisar_cortes(clave=None)` | `dict` `{clave, maximo, cortadas, resultados: [(id, titulo, tokens)]}` | `ModeloNoDisponible` | Tarea |
| `cambiar_modelo(clave, progreso=None)` | `int` de libros con el nuevo modelo; el detalle (reutilizados, calculados, eliminados) queda en `resumen_ultimo_cambio` | `ValueError`, `ModeloNoDisponible` | Tarea |

`progreso` de `descargar_modelo` recibe `(bytes_hechos, bytes_totales, archivo)`.

### 3.6 Estructuras de datos

| Estructura | Claves |
|---|---|
| **Libro** (`catalogo_libros`) | `id`, `isbn`, `titulo`, `autor`, `anio` (int), `editorial`, `genero`, `tema`, `idioma`, `pasta`, `paginas` (int), `calificacion` (float), `disponible` (bool), `fecha_alta`, `fecha_actualizacion`, `estado` (`"Disponible"`, `"Prestado"` o `"No disponible"`), `prestado_a` |
| **Libro con detalle** (`obtener_libro`) | Lo anterior más `sinopsis`, `indexado` (bool), `prestamo` (dict o `None`) y `portada` (`{origen, fuente, fecha}` o `None`), sin `prestado_a` |
| **Resultado de búsqueda** (`buscar_libros`) | Libro más `sinopsis` y `similitud` (float 0–1) |
| **Persona** | `id`, `nombre`, `apellido_paterno`, `apellido_materno`, `nombre_completo`, `fecha_nacimiento`, `edad` (derivada), `genero`, `correo`, `telefono`, `calle_numero`, `colonia`, `ciudad`, `estado`, `codigo_postal`, `ocupacion`, `tipo_usuario`, `acepta_aviso_privacidad`, `fecha_aviso`, `fecha_registro`, `fecha_actualizacion`, `num_prestamos`, `integridad_ok` (False si un dato no superó la verificación), `cifrado_heredado` |
| **Préstamo** | `id` (`PR000001`), `persona_id`, `libro_id`, `titulo`, `autor`, `fecha_prestamo`, `fecha_limite`, `fecha_devolucion`, `estado` (`"activo"` o `"devuelto"`), `estado_visible` (`"Activo"`, `"Vencido"` o `"Devuelto"`), `vencido` (bool) |
| **Estadísticas** | `libros`, `disponibles`, `prestados`, `no_disponibles`, `personas`, `prestamos_activos`, `prestamos_vencidos`, `prestamos_historicos`, `personas_con_prestamo`, `sync_pendientes`, `documentos_indice` |
| **`ResultadoLote`** | `total`, `agregados` (list[str]), `rechazados` (list[dict] `{fila, id, motivos}`) |
| **`ResultadoPortadas`** | `total`, `descargadas` y `sin_portada` (list[dict] `{id, titulo}`), `cancelado` (bool) |
| **`InformeSincronizacion`** | `faltan_en_chroma`, `huerfanos_en_chroma`, `metadatos_distintos`, `pendientes` (listas de ids), `consistente` (bool) |

Las fechas son texto ISO: `"2026-11-19T21:33:05"` en los campos de fecha y hora, y `"2026-12-03"` en `fecha_limite`.

### 3.7 Datos que reciben los métodos de alta y edición

- **Libro** (`alta_libro`, `actualizar_libro`, `validar_alta`): `dict` con las claves de `validaciones.CAMPOS_LIBRO` (`id`, `sinopsis`, `isbn`, `titulo`, `autor`, `anio`, `editorial`, `genero`, `tema`, `idioma`, `pasta`, `paginas`, `calificacion`, `disponible`). Los valores pueden ser texto, tal como vienen de un formulario: el backend convierte los tipos.
- **Persona** (`registrar_persona`, `actualizar_persona`): claves de `validaciones.CAMPOS_PERSONA`. `acepta_aviso_privacidad` debe ser `True`. `genero`, `estado`, `ocupacion` y `tipo_usuario` deben pertenecer a las listas cerradas.

### 3.8 Control de acceso (`self.servicio.acceso`, clase `seguridad.ControlAcceso`)

| Método | Devuelve | Excepciones |
|---|---|---|
| `configurado()` | `bool`: existe una contraseña de operador | — |
| `intentar(contrasena)` | `(bool, str)`: correcto y mensaje para el usuario (incluye la espera tras 5 fallos) | — |
| `segundos_restantes()` | `int` de espera tras demasiados fallos | — |
| `crear_contrasena(contrasena, repetida)` | `None` | `ValueError` (no coinciden, menos de 8 caracteres) |
| `cambiar_contrasena(actual, nueva, repetida)` | `None` | `ValueError` con el mensaje para el usuario |

## 4. Cómo llamar al backend desde una vista

Todas las vistas heredan de `ui.vistas.base.Vista`, que ofrece:

| Ayuda | Uso |
|---|---|
| `self.servicio` | La API de la sección 3. |
| `self.tarea(trabajo, al_terminar=None, mensaje="…", al_error=None)` | Ejecuta `trabajo()` en el hilo trabajador y llama a `al_terminar(resultado)` en la interfaz. Si no se pasa `al_error`, el error se muestra con el diálogo estándar. |
| `self.exito(texto)` / `self.aviso(texto)` | Avisos breves (*toast*). |
| `self.app.navegar(seccion, **contexto)` | Cambia de sección. Por ejemplo, `navegar("prestamos", persona_id="P0001", libro_id="libro09")`. |
| `self.app.manejar_error(error)` | Diálogo estándar a partir de `describir_error`. |
| `self.app.tareas.progreso(funcion)` | Adapta un callback de progreso para ejecutarlo en la interfaz. |
| `self.app.tareas.ejecutar(..., independiente=True)` | Hilo propio para descargas largas. |

### Ejemplo 1: operación rápida (solo Redis) en el hilo de la interfaz (`ui/vistas/personas.py`, simplificado)

```python
def refrescar(self):
    tipo = "" if self.tipo.get() == TODOS else self.tipo.get()
    try:
        personas = self.servicio.buscar_personas(self.texto.get(), tipo, self.solo_prestamos.get())
        total = self.servicio.contar_personas()
    except Exception as error:
        return self.app.manejar_error(error)
    for persona in personas:                                   # el frontend enmascara
        persona["correo_m"] = enmascarar_correo(persona["correo"])
        persona["telefono_m"] = enmascarar_telefono(persona["telefono"])
    self.tabla.cargar(personas)
```

### Ejemplo 2: operación pesada con resultado (`ui/vistas/busqueda.py`, simplificado)

```python
def buscar(self):
    texto = self.consulta.get().strip()

    def listo(resultados):                  # se ejecuta en el hilo de Tkinter
        self.tabla.cargar(resultados)       # cada resultado trae "similitud" entre 0 y 1

    def fallo(error):
        self.btn_buscar.habilitar(True)
        self.app.manejar_error(error)       # p. ej. ModeloNoDisponible → diálogo claro

    self.btn_buscar.habilitar(False)
    self.tarea(lambda: self.servicio.buscar_libros(texto, 10, solo_disponibles=False),
               listo, "Buscando por significado…", fallo)
```

### Ejemplo 3: formulario con validación en línea (`ui/vistas/libros.py`, alta)

```python
def guardar(datos, formulario):
    self.servicio.validar_alta(datos)                  # ValueError → el formulario muestra los errores
    formulario.ocupado(True, "Calculando embedding…")

    def listo(libro_id):
        formulario.destroy()
        self.exito(f"Libro «{datos['titulo']}» registrado.")
        self.refrescar(seleccionar=libro_id)

    def fallo(error):
        formulario.ocupado(False)
        if isinstance(error, ValueError):
            formulario.mostrar_errores(str(error))     # p. ej. "El ISBN ... ya pertenece al libro 'libro07'."
        else:
            self.app.manejar_error(error)

    self.tarea(lambda: self.servicio.alta_libro(datos), listo, "Registrando libro…", fallo)
```

### Ejemplo 4: progreso de una operación larga (`ui/vistas/libros.py`, importación, simplificado)

```python
def progreso(hechos, total):
    self.app.mensaje_estado(f"Calculando embeddings… {hechos}/{total}")

self.tarea(lambda: self.servicio.importar_archivo(ruta, self.app.tareas.progreso(progreso)),
           lambda resultado: mostrar_reporte_lote(self, resultado),   # ResultadoLote
           "Importando libros…")
```

### Ejemplo 5: préstamo (todo o nada) y refresco de la vista (`ui/vistas/prestamos.py`)

```python
def listo(prestamos):
    titulos = ", ".join(f"«{p['titulo']}»" for p in prestamos)
    self.exito(f"Préstamo registrado: {titulos}. Vence el {prestamos[0]['fecha_limite']}.")
    self.al_mostrar(persona_id=persona_id)

self.tarea(lambda: self.servicio.prestar(persona_id, libro_ids), listo, "Registrando préstamo…")
# Si un libro no está disponible: ValueError("El libro «…» no está disponible.") y no se presta ninguno.
```

## 5. Errores y resultados

- **Resultado correcto**: el método devuelve un valor (sección 3). Muestra la confirmación con `self.exito(...)` y refresca la vista.
- **Error esperado del usuario**: `ValueError`, con un mensaje ya redactado en español y listo para mostrar. En formularios va en línea (`formulario.mostrar_errores(str(error))`) y en el resto, con `self.app.manejar_error(error)`.
- **Error del sistema**: cualquier otra excepción. `describir_error(error)` devuelve:

  ```python
  {"titulo": "Sin conexión con Redis", "mensaje": "No se pudo comunicar con Redis en …", "tipo": "error", "categoria": "redis"}
  ```

  | `categoria` | Origen | `tipo` |
  |---|---|---|
  | `validacion` | `ValueError` | `aviso` |
  | `modelo` | `ModeloNoDisponible`, `ErrorDescarga`, `SinConexion`, `EspacioInsuficiente` | `error` |
  | `redis` | Conexión, tiempo de espera o autenticación de Redis | `error` |
  | `integridad` | `ErrorCifrado`, `ErrorLlave` | `error` |
  | `red` | `ErrorPortada` (sin conexión con Open Library) | `error` |
  | `inesperado` | Cualquier otra; el detalle técnico queda en `biblioteca.log` | `error` |

  `AplicacionBiblioteca.manejar_error` ya usa esta función: puedes cambiar **cómo** se presenta el diálogo, pero no dupliques la clasificación. Los mensajes nunca contienen datos personales.
- **Datos ilegibles**: `obtener_persona` no lanza excepción si un campo cifrado no supera la verificación. Devuelve el campo vacío e `integridad_ok = False`; la interfaz debe señalarlo (hoy, la fila aparece en rojo).

## 6. Probar la interfaz sin tocar datos reales

| Herramienta | Qué hace |
|---|---|
| `python demo_interfaz.py` | Abre la aplicación completa con **fakeredis** y **ChromaDB en memoria**, una llave temporal, la contraseña `demo1234`, los 200 libros de ejemplo y 4 personas ficticias con préstamos (uno vencido). Usa un modelo simulado: no necesita GPU ni descargar el modelo. Las portadas que se elijan o descarguen van a una carpeta temporal. No lee ni escribe `.env`, `secrets/`, `chroma_db/`, `portadas/` ni ningún Redis real. Todo se borra al cerrar. |
| `python demo_interfaz.py --sin-datos` | Igual, con las bases vacías, para revisar los mensajes de tabla vacía y el primer uso. |
| `python demo_interfaz.py --modelo-real` | Usa el modelo descargado para revisar la búsqueda real (los datos siguen en memoria). |
| `python -m pytest tests/test_interfaz.py` | Recorre las 7 secciones y un flujo completo con fakeredis. |
| `python -m pytest tests/test_arquitectura.py` | Comprueba que `ui/` respete este contrato. |
| `python -m pytest tests` | Toda la suite; no usa servicios externos salvo que se active la integración real. |

Recomendaciones:

- Durante el desarrollo visual usa siempre `demo_interfaz.py`.
- Si necesitas tu Redis local, usa una base vacía distinta (`REDIS_DB`) y nunca una con datos de otro proyecto.
- No uses datos personales reales en capturas, issues ni Pull Requests.
