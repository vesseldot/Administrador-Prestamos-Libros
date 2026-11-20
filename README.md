# Administrador de Préstamos de Libros

Aplicación de escritorio en **Python + Tkinter** para administrar el acervo, los usuarios y los préstamos de una biblioteca. Incluye **búsqueda semántica** de libros por el significado de su sinopsis y **protección de datos personales** inspirada en la LFPDPPP.

> Proyecto académico de la materia de Bases de Datos NoSQL: combina un almacén clave-valor (**Redis**) con una base vectorial (**ChromaDB**) y un modelo de embeddings multilingüe (**Qwen3-Embedding-0.6B**) que se ejecuta en local.

## Características

- **Dashboard** con indicadores, actividad reciente y próximos vencimientos.
- **Libros**: catálogo con filtros, alta validada (ISBN con dígito de control), importación por lote desde CSV o JSON, edición, eliminación y «Buscar similares».
- **Portadas**: se buscan en Open Library por ISBN o por título, o se eligen del equipo. Se guardan en `portadas/`, fuera de Git, porque tienen derechos de sus editoriales.
- **Búsqueda semántica** en lenguaje natural, con la opción «solo disponibles».
- **Personas**: alta con aviso de privacidad y derechos ARCO (ficha, exportación, rectificación y cancelación).
- **Préstamos** de 1 a 3 libros por persona, devoluciones parciales o totales e historial permanente.
- **Configuración**: descarga y cambio del modelo, sincronización Redis ↔ ChromaDB, seguridad y estado del sistema.
- **Seguridad**: AES-256-GCM por campo, contraseña de operador con scrypt y bloqueo por inactividad.

## Arquitectura

```text
Interfaz Tkinter (ui/) ──► servicios.py ──┬─► db_catalogo · db_personas · db_prestamos ──► Redis
                                          └─► db_libros ──► modelos.py / gestor_modelos.py ──► ChromaDB
```

Redis es la fuente de verdad (libros, personas cifradas, préstamos y bitácora). ChromaDB guarda las sinopsis con sus embeddings de 1024 dimensiones. La interfaz solo usa la API pública de `ServicioBiblioteca`. Detalle en [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

## Instalación rápida

Requisitos: Python 3.10 o superior con Tkinter, Git y **un servidor Redis 6 o superior** (el que tengas instalado; Docker es opcional). La guía completa para Windows está en [docs/INSTALACION.md](docs/INSTALACION.md).

```bash
git clone https://github.com/vesseldot/Administrador-Prestamos-Libros.git
cd Administrador-Prestamos-Libros
python -m venv .venv
# Windows:  .\.venv\Scripts\Activate.ps1      Linux/macOS:  source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu   # o el índice de tu versión de CUDA
pip install -r requirements.txt
cp .env.example .env              # Windows: copy .env.example .env
redis-cli ping                    # → PONG
redis-cli -n 2 DBSIZE             # → 0  (si no, elige otra REDIS_DB vacía en .env)
python verificar.py               # diagnóstico del entorno
python main.py
```

En el primer uso:

1. Crea la contraseña del operador.
2. Acepta la descarga del modelo (~1.2 GB, una sola vez).
3. Carga los 200 libros de ejemplo desde **Configuración › Sistema**.

Cada instalación genera su propia llave de cifrado y usa su propio Redis y su propia ChromaDB. Desde la misma pestaña se pueden descargar las portadas que falten.

## Modo de demostración

```bash
python demo_interfaz.py
```

Abre la aplicación completa con datos de ejemplo **en memoria**. No necesita Redis ni GPU y no toca datos reales. La contraseña es `demo1234`. Las opciones `--sin-datos` y `--modelo-real` están descritas en [docs/INSTALACION.md](docs/INSTALACION.md#12-modo-de-demostración).

## Apariencia y animaciones

La interfaz usa la paleta índigo del proyecto, tipografía con serifa para los títulos (Cambria, Georgia u otra disponible en el sistema) y la fuente sans del sistema para la lectura. Las animaciones (contadores del dashboard, transiciones de botones, avisos y el fondo de la pantalla de acceso) son breves y no bloquean la ventana ni las tareas en curso. Para desactivarlas, define la variable de entorno `BIBLIOTECA_SIN_ANIMACIONES=1` antes de ejecutar; las pruebas ya la activan por sí solas.

## Pruebas

```bash
python -m pytest tests                                  # sin servicios externos
BIBLIOTECA_PRUEBAS_REALES=1 python -m pytest tests      # + Redis, ChromaDB y el modelo reales
```

En PowerShell, la segunda línea es `$env:BIBLIOTECA_PRUEBAS_REALES="1"; python -m pytest tests`. Los resultados y la calidad medida de la búsqueda están en [PRUEBAS.md](PRUEBAS.md).

## Documentación

| Documento | Para qué |
|---|---|
| [Guía técnica para colaboradores](docs/GUIA_TECNICA_COLABORADORES.md) · [PDF](docs/GUIA_TECNICA_COLABORADORES.pdf) | Manual de referencia: estructura, arquitectura, Redis, ChromaDB, modelo, seguridad, interfaz, funcionalidades, instalación, Git y mantenimiento. El PDF incluye los documentos complementarios como anexos. |
| [Guía de estudio del proyecto](docs/GUIA_ESTUDIO_PROYECTO.md) · [PDF](docs/GUIA_ESTUDIO_PROYECTO.pdf) | Explicación didáctica con código real, preguntas de defensa y ejercicios resueltos. |
| [Informe de limpieza y documentación](docs/INFORME_LIMPIEZA_Y_DOCUMENTACION.md) · [PDF](docs/INFORME_LIMPIEZA_Y_DOCUMENTACION.pdf) | Cambios de legibilidad en el código y verificación de la documentación. |
| [ARQUITECTURA](docs/ARQUITECTURA.md) · [FLUJOS_DATOS](docs/FLUJOS_DATOS.md) · [MODELO_SEMANTICO](docs/MODELO_SEMANTICO.md) · [SEGURIDAD](docs/SEGURIDAD.md) | Documentos técnicos complementarios. |
| [INSTALACION](docs/INSTALACION.md) · [MANTENIMIENTO](docs/MANTENIMIENTO.md) | Instalación en Windows, diagnóstico y solución de problemas. |
| [INTEGRACION.md](INTEGRACION.md) | Contrato de la API entre la interfaz y el backend. |
| [CONTRIBUTING.md](CONTRIBUTING.md) · [docs/CONTRIBUCION.md](docs/CONTRIBUCION.md) | Roles del equipo, ramas, Pull Requests y normas de desarrollo. |
| [PRUEBAS.md](PRUEBAS.md) · [ANALISIS_PROYECTO.md](ANALISIS_PROYECTO.md) · [GITHUB_PUBLICACION.md](GITHUB_PUBLICACION.md) | Resultados de las pruebas, análisis inicial y preparación para GitHub. |

Los archivos Markdown son las fuentes editables. Los PDF se regeneran con `python docs/herramientas/generar_pdf.py` (ver [docs/herramientas/LEEME.md](docs/herramientas/LEEME.md)).

## Datos de ejemplo

`datos/` contiene 200 libros en tres CSV y 60 consultas etiquetadas para evaluar la búsqueda. Título, autor, año y argumento corresponden a las obras reales; las sinopsis son de redacción propia. En `libros_catalogo_ampliado.csv`, el ISBN, la editorial, las páginas y la calificación son ilustrativos. El repositorio **no contiene datos personales**.

## Colaborar

Los colaboradores con permiso de escritura pueden subir directamente a `main` y `develop` (sin *force push* ni borrado de ramas). Para cambios grandes conviene una rama `feature/*` o `fix/*` y un Pull Request hacia `develop`. Los roles, los archivos de cada área y las normas están en [CONTRIBUTING.md](CONTRIBUTING.md) y [docs/CONTRIBUCION.md](docs/CONTRIBUCION.md).

## Licencia

Código distribuido bajo la licencia **MIT** (ver [LICENSE](LICENSE)), © 2026 Vessel-dot. El modelo Qwen3-Embedding-0.6B no forma parte del repositorio: se descarga por separado desde Hugging Face y se rige por su propia licencia Apache-2.0.
