# Flujos de datos

Recorrido de cada operación desde la interfaz hasta Redis, ChromaDB y el modelo. Los nombres de clases, métodos y llaves corresponden al código actual; en las llaves de Redis se omite el prefijo `bib:`.

**Convenciones de los diagramas**: *Vista* es la sección de `ui/vistas/`; *Tareas* es `ui/tareas.GestorTareas` (hilo trabajador); *Servicio* es `servicios.ServicioBiblioteca`; *Catálogo*, *Personas* y *Préstamos* son los gestores de Redis (`db_catalogo`, `db_personas`, `db_prestamos`); *Índice* es `db_libros.GestorLibros` (ChromaDB + modelo).

## 1. Arranque de la aplicación

```mermaid
sequenceDiagram
    participant M as main.py
    participant C as config
    participant S as ServicioBiblioteca
    participant R as Redis
    participant I as GestorLibros
    M->>M: asegurar_entorno()
    Note right of M: relanza con .venv si faltan dependencias
    M->>M: configurar_registro() · activar_alta_densidad()
    M->>C: validar() · advertencias()
    M->>S: crear()
    S->>R: conectar_redis() → PING
    S->>R: preparar_base(): SCAN · SETNX meta:esquema
    S->>S: Cifrador(llave maestra, llave heredada)
    S->>I: GestorLibros(): PersistentClient · colección del modelo activo
    S-->>M: servicio listo
```

Después, la ventana y el acceso:

```mermaid
sequenceDiagram
    participant M as main.py
    participant A as AplicacionBiblioteca
    participant T as GestorTareas
    participant S as ServicioBiblioteca
    M->>A: AplicacionBiblioteca(servicio)
    A->>A: tema · menú lateral · barra de estado · PantallaAcceso
    M->>A: mainloop()
    Note over A: contraseña correcta → _al_entrar()
    A->>A: navegar("dashboard") · _precargar_modelo()
    alt falta el modelo
        A->>A: ofrecer_descarga() → DialogoDescargaModelo
    else modelo disponible
        A->>T: ejecutar(precargar_modelo)
        T->>S: precargar_modelo()
        A->>T: ejecutar(revisar_sincronizacion)
        T->>S: revisar_sincronizacion()
        S-->>A: InformeSincronizacion (aviso si hay diferencias)
    end
```

Errores que detienen el arranque y muestran un diálogo (`main.error_de_arranque`): configuración inválida, Redis sin conexión o con credenciales incorrectas, base ocupada por llaves ajenas (`ErrorBaseOcupada`) y llave de cifrado inválida (`ErrorLlave`).

## 2. Alta de un libro

```mermaid
sequenceDiagram
    participant V as VistaLibros
    participant T as Tareas
    participant S as Servicio
    participant I as Índice (Chroma + modelo)
    participant C as Catálogo (Redis)
    V->>V: Formulario (14 campos)
    V->>S: validar_alta(datos) [hilo de la UI]
    S->>C: existe(id) · dueno_isbn(isbn)
    alt ValueError
        S-->>V: errores en línea en el formulario
    end
    V->>T: alta_libro(datos)
    T->>S: alta_libro(datos)
    S->>I: agregar([libro]) → embeber_documentos + upsert
    S->>C: guardar(libro, nuevo=True): WATCH libro:{id}, idx:isbn:{isbn} → MULTI HSET/SADD/SET
    alt falla Redis
        S->>I: eliminar([id]) (compensación)
    end
    S->>C: actividad: libro_alta
    T-->>V: libro_id → aviso de éxito y refrescar(seleccionar=id)
```

Escrituras en Redis: `HSET libro:{id}`, `SADD libros {id}`, `SET idx:isbn:{isbn} {id}`. En ChromaDB: `upsert(ids, documents=[sinopsis], metadatas, embeddings)`.

## 3. Importación por lote (CSV o JSON)

1. `VistaLibros.importar` abre un diálogo para elegir el archivo, que parte de `datos/`.
2. `[Tareas] servicio.importar_archivo(ruta, progreso)`: `leer_archivo_libros` detecta si el CSV usa `,` o `;` y admite JSON como lista o como `{"libros": [...]}`.
3. `importar_lote` valida **cada fila** con `validar_libro` y rechaza los ids o ISBN repetidos dentro del archivo o ya existentes en la base.
4. Las filas válidas se indexan en Chroma en lotes de 32, informando el progreso, y después se escriben en Redis con `CatalogoRedis.guardar_lote`, una única transacción `MULTI`.
5. Si Redis falla, se borran de Chroma los ids recién insertados.
6. La vista muestra un `Dialogo` con el total, los importados y los rechazados, cada uno con su fila, id y motivos.

## 4. Catálogo, filtros y ficha

```mermaid
sequenceDiagram
    participant V as VistaLibros
    participant S as Servicio
    participant C as Catálogo (Redis)
    participant P as Préstamos (Redis)
    participant I as Índice
    V->>S: catalogo_libros() [hilo de la UI]
    S->>C: listar() (SMEMBERS libros + HGETALL en pipeline)
    S->>P: activos() → libros prestados y a quién
    S-->>V: libros con estado y prestado_a
    V->>S: filtrar_catalogo(libros, texto, genero, idioma, estado)
    V->>V: Tabla.cargar (orden natural, se reordena por columna)
    V->>S: [Tareas] obtener_libro(id)
    S->>C: obtener(id)
    S->>I: obtener(id) → sinopsis
    S->>P: activo_de_libro(id)
    S-->>V: ficha con sinopsis, estado y préstamo
```

## 5. Búsqueda semántica

```mermaid
sequenceDiagram
    participant V as VistaBusqueda
    participant S as Servicio
    participant I as Índice
    participant MOD as ModeloEmbeddings
    participant CH as ChromaDB
    participant C as Catálogo (Redis)
    V->>S: [Tareas] buscar_libros(texto, cantidad, solo_disponibles)
    S->>I: buscar(texto, cantidad × 3 si solo disponibles)
    I->>MOD: embeber_consulta(texto) → vector [1024]
    I->>CH: query(query_embeddings, n_results, include=[documents, metadatas, distances])
    CH-->>I: ids, sinopsis, metadatos, distancias
    I-->>S: similitud = 1 − distancia
    S->>C: obtener_varios(ids) (Redis manda)
    S->>S: _prestados() · _estado_libro() · filtrar disponibles
    S-->>V: lista ordenada por similitud
```

«Buscar similares», desde la ficha del catálogo, reutiliza este flujo con la sinopsis del libro como consulta y lo excluye de los resultados.

## 6. Actualización de un libro

1. `VistaLibros.editar` → `[Tareas] obtener_libro(id)` → el formulario se abre con los datos. El `id` queda bloqueado, y `disponible` también si el libro está prestado.
2. `[Tareas] actualizar_libro(id, datos)`:
   - Si el libro tiene un préstamo activo, fuerza `disponible=False`.
   - Valida los datos y comprueba que el ISBN no pertenezca a otro libro.
   - Guarda una **copia previa** en Chroma con `obtener(id, con_embedding=True)`.
   - Ejecuta `GestorLibros.actualizar(libro, recalcular_embedding=sinopsis_cambió)`. Si la sinopsis no cambió, solo actualiza los metadatos.
   - Ejecuta `CatalogoRedis.guardar(libro, nuevo=False)`, que actualiza el HASH y, si cambió el ISBN, mueve el índice `idx:isbn`.
   - Si falla Redis, `GestorLibros.restaurar(copia)`.

## 7. Eliminación de un libro

1. `VistaLibros.eliminar`: si el libro está prestado, informa y no continúa; si no, pide confirmación.
2. `[Tareas] eliminar_libro(id)`: comprueba que no tenga un préstamo activo, toma una copia previa con su embedding, borra el documento de Chroma y después el registro de Redis (`DEL libro:{id}`, `SREM libros`, `DEL idx:isbn`). Si Redis falla, reinserta la copia en Chroma.
3. **El historial de préstamos se conserva**, porque cada préstamo guarda una copia del título y del autor.

## 8. Alta y actualización de personas

```mermaid
sequenceDiagram
    participant V as VistaPersonas
    participant S as Servicio
    participant P as Personas
    participant Ci as Cifrador
    participant R as Redis
    V->>S: registrar_persona(datos) [hilo de la UI, solo Redis]
    S->>P: registrar(datos)
    P->>P: validar_persona: formatos, listas, aviso aceptado
    P->>Ci: hash_indice(correo)
    P->>R: EXISTS idx:correo:{hmac}
    P->>R: INCR persona:contador → P0001
    P->>R: SET idx:correo:{hmac} P0001 NX
    P->>Ci: cifrar(campo, "persona:P0001:campo") × 13
    P->>R: HSET persona:P0001 · SADD personas
    P->>R: actividad: persona_alta
    S-->>V: "P0001"
```

**Actualización** (`actualizar_persona`, que rectifica los datos):

- Valida los datos de nuevo.
- Si cambió el correo, reserva el nuevo índice con `SET NX` y borra el anterior.
- Vuelve a cifrar los 13 campos.
- Conserva la fecha del aviso original (`HSETNX fecha_aviso`) y actualiza `fecha_actualizacion`.

**Catálogo de personas** (`buscar_personas`):

- Lee todas las personas con un *pipeline* (`HGETALL` + `SCARD` de los préstamos activos de cada una).
- Las descifra y filtra en memoria por id, nombre completo, tipo, ocupación, ciudad y estado.
- La vista **enmascara** el correo y el teléfono antes de mostrarlos.

## 9. Préstamo de libros

```mermaid
sequenceDiagram
    participant V as VistaPrestamos
    participant T as Tareas
    participant S as Servicio
    participant PR as GestorPrestamos
    participant R as Redis
    participant I as Índice (Chroma)
    V->>T: prestar(persona_id, [libro_ids])
    T->>S: prestar(...)
    S->>PR: prestar(persona_id, libro_ids)
    PR->>R: WATCH persona, sus préstamos activos, libros, prestamo_activo, contador
    PR->>R: EXISTS persona · SCARD activos (cupo ≤ 3) · HGETALL libro · EXISTS prestamo_activo
    alt no cumple
        PR-->>V: ValueError (no se presta ninguno)
    end
    PR->>R: MULTI: INCRBY contador · HSET prestamo:PR… · SET libro:{id}:prestamo_activo · HSET libro disponible 0 · SADD/ZADD índices · EXEC
    S->>I: actualizar_metadatos(id, {disponible: False}) por libro
    alt falla Chroma
        S->>R: SADD sync:pendientes id
    end
    S-->>V: préstamos creados (fecha_limite = hoy + 14 días)
```

`fecha_limite` se calcula con `BIBLIOTECA_DIAS_PRESTAMO` (14 por defecto). Un préstamo se considera **vencido** cuando sigue activo y `fecha_limite` es anterior a la fecha de hoy; ese estado se calcula al leer, no se guarda.

## 10. Devolución

1. `VistaPrestamos.devolver` usa los préstamos seleccionados; `devolver_todos` pide confirmación y envía `None`, que significa todos.
2. `[Tareas] servicio.devolver(persona_id, prestamo_ids)` → `GestorPrestamos.devolver`: `WATCH` sobre el conjunto de préstamos activos y cada préstamo. Comprueba que todos sigan activos y pertenezcan a la persona, y en `MULTI`:
   - `HSET prestamo:{id} estado=devuelto, fecha_devolucion=<ahora>`
   - `DEL libro:{id}:prestamo_activo`
   - `HSET libro:{id} disponible 1`, si el libro aún existe
   - `SREM` de los conjuntos de préstamos activos; `SREM personas_con_prestamo` si ya no le quedan préstamos
3. Copia de la disponibilidad a Chroma, con anotación en `sync:pendientes` si falla.
4. **El historial no se borra**: `persona:{id}:historial` y `prestamos:todos` conservan cada préstamo.

## 11. Personas con préstamos

1. `VistaPersonasConPrestamo.refrescar` → `[Tareas] personas_con_prestamos()`: agrupa `prestamos.activos()` por persona y descifra solo a esas personas (`personas.listar(ids=…)`).
2. La vista arma un árbol de personas y sus préstamos con el correo y el teléfono **enmascarados**. «Mostrar contacto» los revela solo para la persona seleccionada durante 20 segundos.

## 12. Cambio de modelo y sincronización

- **Cambio de modelo** (`cambiar_modelo`): toma las sinopsis del índice actual y los metadatos de Redis, abre o crea la colección del nuevo modelo y la sincroniza (`_sincronizar_coleccion`): la colección conserva lo que ya procesó: compara por sinopsis y solo calcula los vectores de los libros nuevos o con la sinopsis editada, reutiliza el resto y elimina los que ya no existen. Si la colección se calculó con otra revisión del modelo, recalcula todo una vez. Solo entonces cambia el modelo activo, guarda `modelo_activo.txt` y deja en `resumen_ultimo_cambio` cuántos libros reutilizó, calculó y eliminó. Si algo falla, el modelo anterior sigue activo y lo avanzado queda guardado para el siguiente intento.
- **Revisar sincronización**: compara los ids de Redis con los de Chroma, los metadatos (con tolerancia en los números con decimales) y `sync:pendientes`.
- **Reparar**: copia a Chroma los metadatos de Redis de los libros desfasados o pendientes.
- **Importar huérfanos**: valida y da de alta en Redis los documentos que solo existen en Chroma.

## 13. Portadas

Las portadas no pasan por Redis ni por ChromaDB: son archivos en `BIBLIOTECA_DIR_PORTADAS`.

1. **Ficha** (`VistaLibros._cargar_detalle`): en una tarea se piden `obtener_libro(id)`, que incluye `portada` con el origen, y `portada_libro(id, ancho, alto)`, que devuelve un PNG ajustado al marco. La interfaz lo muestra con `tk.PhotoImage` (componente `Portada`), sin Pillow.
2. **Elegir imagen…** (`asignar_portada`): comprueba que el libro existe en Redis, lee el archivo (máximo 15 MB), lo valida y lo convierte a JPEG de 600×900 como máximo (`normalizar_imagen`) y lo guarda de forma atómica como `{id}.jpg`, con `{id}.json` (origen y fecha). Registra el evento en la bitácora.
3. **Buscar en internet** (`buscar_portada`, en un hilo independiente): `ClienteOpenLibrary.buscar` consulta `/isbn/{isbn}.json` y acepta la edición solo si su título coincide con el del libro; si no, busca en `/search.json` por título y autor. Descarga la imagen de `covers.openlibrary.org`. Entre peticiones hay una pausa de 1 s y cada petición se reintenta una vez si falla la red.
4. **Alta de un libro**: al terminar, la vista lanza `buscar_portada` en segundo plano; si la encuentra, la ficha se actualiza sola.
5. **Descarga en lote** (Configuración › Sistema, `descargar_portadas`): recorre solo los libros sin portada, informa el progreso por libro y se detiene con `detener_descarga_portadas()`. Tras 3 fallos de red seguidos se interrumpe con `ErrorPortada`.
6. **Eliminación de un libro**: después de borrarlo de Redis y de Chroma, `eliminar_libro` borra también su portada.
