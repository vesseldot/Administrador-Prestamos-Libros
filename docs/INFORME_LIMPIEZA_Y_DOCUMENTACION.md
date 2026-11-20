# Informe de limpieza y documentación

**Fase 12**: limpieza profesional del código, documentación técnica y guía de estudio

| Dato | Valor |
|---|---|
| Fecha | 19 de noviembre de 2026 |
| Rama de trabajo | `docs/limpieza-y-guias`, creada desde `develop` |
| Estado de referencia | Commit `9624f94` (`develop`, con el árbol de trabajo limpio al empezar) |
| Commits y publicación | **Ninguno.** Todos los cambios quedan sin confirmar para que el responsable los revise. |

---

## 1. Resumen

| Aspecto | Resultado |
|---|---|
| Archivos Python examinados | 49 (7 669 líneas) |
| Comentarios eliminados | 0: no había comentarios innecesarios (en una directiva se quitó el `F401`, que ocultaba una importación sin uso) |
| Comentarios conservados | 19 directivas `# noqa` y 92 docstrings |
| Archivos de código modificados | 12 (+45 / −23 líneas), solo legibilidad y registro de un error que antes se ignoraba en silencio |
| Lógica de negocio, Redis, ChromaDB y modelo | Sin cambios |
| Documentos nuevos | 11 Markdown, 3 PDF y el generador de PDF |
| Diagramas Mermaid | 21 |
| Pruebas | 123 superadas y 1 omitida (sin servicios); 124 superadas con Redis, ChromaDB y Qwen reales |

---

## 2. Parte I: limpieza del código

### 2.1 Método

1. Se comprobó `git status` (árbol limpio en `develop`, commit `9624f94`) y se creó la rama `docs/limpieza-y-guias` como referencia del estado inicial.
2. Se inventariaron los comentarios con el tokenizador de Python (`tokenize`) y los docstrings con `ast`, en lugar de con búsquedas de texto, para no confundir comentarios con texto dentro de cadenas.
3. Se revisaron el estilo (PEP 8 con 120 caracteres), las importaciones y el manejo de excepciones de cada archivo.
4. Se hicieron cambios pequeños y se ejecutaron las pruebas después de cada grupo.

### 2.2 Archivos examinados

Los 49 archivos `.py` versionados:

| Grupo | Archivos |
|---|---|
| Núcleo (13) | `main.py`, `config.py`, `validaciones.py`, `seguridad.py`, `modelos.py`, `gestor_modelos.py`, `modelo_simulado.py`, `db_redis.py`, `db_catalogo.py`, `db_personas.py`, `db_prestamos.py`, `db_libros.py`, `servicios.py` |
| Herramientas (6) | `demo_interfaz.py`, `verificar.py`, `gestionar_modelos.py`, `gestionar_secretos.py`, `evaluar_busqueda.py`, `comparar_modelos.py` |
| Interfaz (17) | `ui/__init__.py`, `ui/app.py`, `ui/acceso.py`, `ui/componentes.py`, `ui/descarga_modelo.py`, `ui/iconos.py`, `ui/tareas.py`, `ui/tema.py`, `ui/vistas/__init__.py`, `ui/vistas/base.py`, `ui/vistas/configuracion.py`, `ui/vistas/dashboard.py`, `ui/vistas/libros.py`, `ui/vistas/busqueda.py`, `ui/vistas/personas.py`, `ui/vistas/personas_prestamos.py`, `ui/vistas/prestamos.py` |
| Pruebas (13) | `tests/conftest.py` y los 12 archivos `tests/test_*.py` |

### 2.3 Comentarios

**Eliminados: ninguno.** El código no contenía comentarios explicativos redundantes ni código comentado; la documentación interna está en docstrings.

**Conservados (19)**, todos directivas para herramientas de análisis:

| Directiva | Cantidad | Motivo |
|---|---:|---|
| `# noqa: BLE001` | 9 | Capturas genéricas intencionadas en los límites. En `gestor_modelos.py` (3) el error se reclasifica o se convierte en `ErrorDescarga` y se relanza. En `ui/app.py`, `ui/tareas.py`, `ui/vistas/libros.py` y `ui/vistas/personas.py` (5) se registra o se muestra con `manejar_error`. En `verificar.py` (1) se informa como diagnóstico. |
| `# noqa: E402` | 10 | Importaciones que deben ir después de preparar el entorno: 5 en `main.py` (después de `asegurar_entorno()`, que relanza con `.venv`) y 5 en `tests/conftest.py` (después de añadir la raíz del proyecto a `sys.path`). |

Una de las directivas de `tests/conftest.py` era `# noqa: E402,F401`: el `F401` ocultaba la importación sin uso de `ModeloSimulado`. Se quitó esa importación y la directiva quedó en `# noqa: E402`. Un análisis de AST de todo el código confirma que no quedan importaciones sin uso.

**Docstrings conservados: 92**, en módulos, clases y funciones públicas o complejas.

### 2.4 Cambios de legibilidad

Ninguno modifica el comportamiento. Todos los textos visibles para el usuario se conservan carácter por carácter.

| Archivo | Cambio |
|---|---|
| `db_redis.py` | Se añadió un registrador (`logging`). `RegistroActividad.registrar` ahora deja un aviso en `biblioteca.log` (tipo de evento y clase del error, sin datos personales) si falla la escritura de la bitácora, en lugar de ignorarlo en silencio. La operación principal sigue sin interrumpirse. |
| `ui/vistas/configuracion.py` | Se eliminó una importación sin uso (`from ui import tema`). La función auxiliar `lista()` usa un retorno anticipado. Se partieron líneas largas. |
| `tests/conftest.py` | Importaciones ordenadas alfabéticamente y eliminada la importación sin uso de `ModeloSimulado`. |
| `evaluar_busqueda.py`, `main.py`, `servicios.py`, `verificar.py`, `ui/acceso.py`, `ui/descarga_modelo.py`, `ui/vistas/dashboard.py`, `ui/vistas/personas.py`, `ui/vistas/personas_prestamos.py` | Líneas de más de 120 caracteres partidas, a veces con una variable intermedia con nombre descriptivo (`ruta_consultas`, `nombre_gpu`, `filtrando`). |

Resultado: ninguna línea del código supera los 120 caracteres.

### 2.5 Excepciones revisadas

Se conservaron, por ser correctos, los bloques que ignoran una excepción a propósito:

| Ubicación | Situación | Por qué es correcto |
|---|---|---|
| `db_libros.py:22` (`leer_modelo_activo`) | `OSError` al leer `modelo_activo.txt` | Si el archivo no existe o no se puede leer, se usa el modelo por defecto. |
| `evaluar_busqueda.py:56` y `:66` | `ImportError` de `torch` | La medición de memoria de la GPU es opcional. |
| `main.py:64` (`activar_alta_densidad`) | `AttributeError` u `OSError` | La función de Windows no existe en otros sistemas. |
| `modelos.py:135` (`liberar`) | `ImportError` de `torch` | Sin PyTorch no hay memoria de la GPU que liberar. |
| `ui/tareas.py:76` (`_revisar`) | `queue.Empty` | Es la condición normal de fin del bucle que vacía la cola. |

### 2.6 Verificación de la limpieza

- `git diff --stat 9624f94 -- '*.py'`: 12 archivos, 45 inserciones y 23 eliminaciones.
- Sin cambios en `modelos.py`, `gestor_modelos.py`, `db_libros.py`, `db_catalogo.py`, `db_personas.py`, `db_prestamos.py`, `seguridad.py`, `validaciones.py` ni `config.py`. Es decir, ni el modelo semántico, ni las estructuras de Redis y ChromaDB, ni el cifrado cambiaron.
- `python -m pytest tests`: 123 superadas y 1 omitida, la de integración real, que solo se ejecuta si se pide.

---

## 3. Parte II: documentación

### 3.1 Documentos creados

| Archivo | Contenido |
|---|---|
| `docs/GUIA_TECNICA_COLABORADORES.md` | Manual principal en 15 capítulos. |
| `docs/GUIA_ESTUDIO_PROYECTO.md` | Guía de estudio en 13 capítulos: 45 preguntas de defensa y 10 ejercicios resueltos. |
| `docs/ARQUITECTURA.md` | Capas, dependencias, modelo de datos de Redis y ChromaDB, consistencia, concurrencia y migración. Sustituye al archivo de la raíz, ampliado. |
| `docs/FLUJOS_DATOS.md` | Recorrido de cada funcionalidad, con 7 diagramas de secuencia. |
| `docs/MODELO_SEMANTICO.md` | Modelo de embeddings: descarga, carga, búsqueda, calidad medida y alternativas. |
| `docs/SEGURIDAD.md` | Cifrado, llaves, control de acceso, ARCO, riesgos y LFPDPPP. Sustituye al archivo de la raíz, ampliado. |
| `docs/INSTALACION.md` | Instalación paso a paso en Windows. |
| `docs/CONTRIBUCION.md` | Git, GitHub, revisión de Pull Requests, conflictos y normas de desarrollo. |
| `docs/MANTENIMIENTO.md` | Diagnóstico y solución de problemas por área. |
| `docs/INFORME_LIMPIEZA_Y_DOCUMENTACION.md` | Este informe. |
| `docs/herramientas/LEEME.md` | Cómo regenerar los PDF. |
| `docs/herramientas/generar_pdf.py` | Generador de los PDF. |
| `docs/herramientas/requisitos.txt` | Dependencias del generador (`pypdf`, `websocket-client`). |

### 3.2 Documentos modificados, movidos o eliminados

| Archivo | Cambio |
|---|---|
| `ARQUITECTURA.md` y `SEGURIDAD.md` (raíz) | Eliminados después de comprobar que todas sus secciones están en `docs/`. |
| `README.md` | Reescrito de forma concisa (de 393 a 94 líneas): características, arquitectura, instalación rápida, demostración, pruebas, tabla de documentación con los PDF, datos de ejemplo, colaboración y licencia. Los detalles que solo estaban en el README se trasladaron a `docs/INSTALACION.md`. |
| `CONTRIBUTING.md`, `ANALISIS_PROYECTO.md`, `GITHUB_PUBLICACION.md`, `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/nueva_funcionalidad.md` | Enlaces y referencias actualizados a `docs/`. En `ANALISIS_PROYECTO.md` se conservan las menciones históricas del plan original. |
| `.gitattributes` | Se añadió `*.pdf binary`. |

### 3.3 Diagramas

| Documento | Diagramas |
|---|---|
| `GUIA_TECNICA_COLABORADORES.md` | 4: capas, arranque (dos partes) y modelo de hilos |
| `ARQUITECTURA.md` | 2: módulos y dependencias, y diagrama entidad-relación |
| `FLUJOS_DATOS.md` | 7 diagramas de secuencia |
| `MODELO_SEMANTICO.md` | 1: descarga del modelo |
| `SEGURIDAD.md` | 2: derivación de llaves y registro de una persona |
| `CONTRIBUCION.md` | 1: flujo de ramas (gitGraph) |
| `GUIA_ESTUDIO_PROYECTO.md` | 4: tecnologías, módulos, préstamo y mapa conceptual |

Todos están escritos en Mermaid dentro del Markdown (se ven en GitHub) y se dibujan en los PDF.

### 3.4 PDF generados

| PDF | Páginas | Diagramas | Entradas del índice |
|---|---:|---:|---:|
| `docs/GUIA_TECNICA_COLABORADORES.pdf` (guía y anexos A–H) | 85 | 17 | 119 |
| `docs/GUIA_ESTUDIO_PROYECTO.pdf` | 41 | 4 | 95 |
| `docs/INFORME_LIMPIEZA_Y_DOCUMENTACION.pdf` | 16 | 0 | 20 |

**Características:**

- Portada.
- Índice con números de página.
- Encabezado con el título del documento y el proyecto, y pie con autoría y «Página X de Y».
- Marcadores de navegación.
- Tamaño carta y tipografía Segoe UI, con Cascadia Mono o Consolas para el código.
- Código con resaltado de sintaxis.
- Tablas con encabezado repetido en cada página.
- Notas y advertencias destacadas.
- Soluciones de los ejercicios en recuadros.
- Texto seleccionable.

**Proceso:** pandoc 3.8 → HTML; Chrome 157 sin ventana con mermaid 11.4.1 (huella SHA-256 verificada) → PDF; pypdf 7.1.1 une la portada y el cuerpo. Detalle en `docs/herramientas/LEEME.md`.

### 3.5 Correcciones hechas al contrastar la documentación con el código

| Aspecto | Corrección |
|---|---|
| Ejemplo de `libro09` | El ISBN y la sinopsis se tomaron de `datos/libros_lote.csv`. |
| Ejercicio 7 de la guía de estudio | `libro_ejemplo` y `persona_ejemplo` son funciones de `conftest.py`, no fixtures. La prueba se ejecutó y pasa. |
| Ejercicios 2, 3 y 7 | Los mensajes de error y el cálculo del ISBN se comprobaron ejecutando el código. |
| Tiempo por consulta con la instrucción de libros | 51 ms, según `PRUEBAS.md`. |
| Diagrama de arranque | `revisar_sincronizacion()` se ejecuta **después** de `precargar_modelo()`, no a la vez. |
| Versiones de la tabla de tecnologías | Comprobadas con `pip` y con el servidor Redis (8.10.1). |
| Protección de GitHub | El escaneo de secretos y la protección al subir cambios se comprobaron activos con la API de GitHub (solo lectura). |

---

## 4. Verificación final

| Comprobación | Resultado |
|---|---|
| Pruebas sin servicios externos (`python -m pytest tests`) | **123 superadas y 1 omitida** |
| Pruebas con servicios reales (`BIBLIOTECA_PRUEBAS_REALES=1`) | **124 superadas** (Redis 8.10.1, ChromaDB y Qwen3-Embedding-0.6B reales) |
| Datos reales de Redis | Base 2: 403 llaves `bib:` antes y después. La prueba real usa el prefijo `prueba_integracion:` y no dejó llaves. |
| ChromaDB real (solo lectura) | Colección `libros_qwen3_embedding_0_6b` con 200 documentos y 1024 dimensiones. |
| Modelo semántico | `gestionar_modelos.py estado`: Qwen3-Embedding-0.6B descargado en la revisión `97b0c614be`, activo. `modelos.py` sin cambios. |
| Interfaz | `tests/test_interfaz.py` crea la ventana real de Tkinter, recorre las 7 secciones, hace un flujo completo y prueba el bloqueo de sesión: superadas. `tests/test_demo.py`: superadas. **No se hizo una revisión visual manual de la interfaz en esta fase.** |
| Funciones citadas en la documentación | Nombres, firmas, mensajes y fragmentos de código comparados con el código actual. Los fragmentos se copiaron del repositorio. |
| Enlaces | Ningún enlace relativo roto en los 18 Markdown del repositorio. Todos los enlaces internos de los PDF tienen destino (el generador lo comprueba). |
| Diagramas | 21 dibujados sin errores. Ninguno reducido por debajo del 61 % de su tamaño. |
| Texto seleccionable | Todas las páginas de los tres PDF contienen texto extraíble (pypdf). |
| Revisión visual de los PDF | Todas las páginas se renderizaron a imagen y se revisaron. No hay texto ni diagramas cortados. |
| Secretos y datos personales | Se buscaron en los Markdown y en el texto de los PDF los valores reales de la llave AES, del hash del operador, de la llave heredada y de `.env`, la contraseña del operador, el correo personal y patrones de llaves en base64: **ninguna coincidencia**. Las únicas apariciones de `scrypt$` son la descripción del formato y la línea de código que lo construye. |
| Rutas | Las rutas de la documentación corresponden a archivos existentes. Las variables de entorno citadas son las que lee `config.py`. |

---

## 5. Problemas encontrados y resueltos

- **Diagramas demasiado pequeños en el PDF.** Los diagramas anchos (muchos participantes o mensajes largos) se reducían hasta el 30 %. Se reorganizaron sin cambiar su contenido: el arranque se dividió en dos, los rombos se cambiaron por cajas con flechas etiquetadas y se agruparon módulos. Además, el generador parte los mensajes largos por los espacios.
- **Palabras partidas en tablas estrechas** (por ejemplo, «STRIN G»). Se corrigió con puntos de corte solo dentro del código en línea (después de `:`, `_`, `/`, `.` y `,`).
- **Enlaces entre documentos** al unir los anexos en un solo PDF. Los identificadores se prefijan por anexo y los enlaces se reescriben.
- **Un comando de diagnóstico de `docs/MANTENIMIENTO.md`** se ajustó para usar `findstr`, disponible en Windows.

---

## 6. Funcionalidades incompletas (documentadas como no implementadas)

- No existe un ejecutable ni un empaquetado: la aplicación se ejecuta con `python main.py`.
- La rotación de la llave AES con datos existentes no está implementada; solo la migración de Fernet a AES-GCM.
- No hay cuentas individuales por operador ni roles: hay una sola contraseña de operador.
- No hay bitácora de quién consulta cada ficha personal.
- No hay un procedimiento para menores de edad ni un aviso de privacidad integral, que requieren una revisión legal.
- Las pruebas de GitHub Actions todavía no son obligatorias para integrar.

---

## 7. Riesgos

| Riesgo | Mitigación |
|---|---|
| Los PDF pueden quedar desactualizados respecto a los Markdown. | Regenerarlos en el mismo commit (`docs/herramientas/LEEME.md`). |
| Los enlaces de los PDF a archivos fuera del documento apuntan a la rama `develop` de GitHub. | Funcionarán cuando estos cambios se integren en `develop`. |
| El generador depende de pandoc, de Chrome o Edge y, la primera vez, de descargar mermaid de jsDelivr. | Versión fijada y huella SHA-256 comprobada. Si falla, los Markdown siguen siendo la fuente válida. |
| Avisos LF/CRLF al confirmar. | `.gitattributes` normaliza a LF; son informativos. |
| `pypdf` se instaló en el entorno virtual local para generar los PDF. | Está declarado en `docs/herramientas/requisitos.txt` y no afecta a la aplicación. |

---

## 8. Pendientes para el responsable

1. Revisar los cambios (`git status`, `git diff`) en la rama `docs/limpieza-y-guias`.
2. Confirmarlos por separado si se desea mantener aparte limpieza y documentación. Por ejemplo, un commit `refactor:` con los 12 archivos `.py` y otro `docs:` con la documentación.
3. Abrir el Pull Request hacia `develop`. @miasmee será revisora automática de los cambios en `ui/` por CODEOWNERS.
4. Opcional: añadir a la integración continua una comprobación de que los PDF están al día.

---

## 9. Rutas de los documentos

Todas las rutas son relativas a la raíz del repositorio.

| Documento | Ruta |
|---|---|
| Guía técnica (fuente) | `docs/GUIA_TECNICA_COLABORADORES.md` |
| Guía técnica (PDF) | `docs/GUIA_TECNICA_COLABORADORES.pdf` |
| Guía de estudio (fuente) | `docs/GUIA_ESTUDIO_PROYECTO.md` |
| Guía de estudio (PDF) | `docs/GUIA_ESTUDIO_PROYECTO.pdf` |
| Informe (fuente) | `docs/INFORME_LIMPIEZA_Y_DOCUMENTACION.md` |
| Informe (PDF) | `docs/INFORME_LIMPIEZA_Y_DOCUMENTACION.pdf` |
| Arquitectura | `docs/ARQUITECTURA.md` |
| Flujos de datos | `docs/FLUJOS_DATOS.md` |
| Modelo semántico | `docs/MODELO_SEMANTICO.md` |
| Seguridad | `docs/SEGURIDAD.md` |
| Instalación | `docs/INSTALACION.md` |
| Contribución | `docs/CONTRIBUCION.md` |
| Mantenimiento | `docs/MANTENIMIENTO.md` |
| Generador de PDF | `docs/herramientas/generar_pdf.py`, `docs/herramientas/LEEME.md`, `docs/herramientas/requisitos.txt` |
| Contrato de la API | `INTEGRACION.md` |
| Resultados de las pruebas | `PRUEBAS.md` |
