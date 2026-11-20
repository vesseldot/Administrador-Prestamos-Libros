# Guía para colaborar

## Responsabilidades del equipo

| Área | Responsable | Alcance |
|---|---|---|
| **Frontend** (interfaz Tkinter) | @miasmee | Experiencia visual: diseño, componentes, vistas, navegación, accesibilidad y mensajes. |
| **Backend e integración** | @vesseldot | Lógica de negocio, Redis, ChromaDB, modelo semántico, seguridad, validaciones, configuración e integración. |

[`.github/CODEOWNERS`](.github/CODEOWNERS) solicita automáticamente la revisión del responsable de cada área en los Pull Requests.

El frontend puede desarrollarse **de forma independiente** mientras respete el contrato de [INTEGRACION.md](INTEGRACION.md): la interfaz solo usa la API pública de `ServicioBiblioteca` y las pocas funciones puras permitidas. La prueba `tests/test_arquitectura.py` lo comprueba en cada ejecución de las pruebas y en cada Pull Request.

### Qué puede modificar la responsable del frontend

| Archivos | Notas |
|---|---|
| `ui/tema.py`, `ui/iconos.py`, `ui/componentes.py` | Libre: paleta, tipografía, iconos, componentes, nuevos widgets. |
| `ui/vistas/*.py` (las 7 secciones y `base.py`) | Libre: distribución, tablas, formularios, nuevas vistas o pestañas, textos. |
| `ui/acceso.py`, `ui/descarga_modelo.py` | Libre en la **presentación**. La lógica de contraseñas vive en `seguridad.ControlAcceso` y la de descarga en el backend. |
| `ui/app.py` | Libre en el menú lateral, la cabecera, la barra de estado y la navegación. **Coordinar** antes de cambiar `manejar_error`, el bloqueo por inactividad (`bloquear`, `_revisar_inactividad`) o la precarga del modelo (`_precargar_modelo`, `ofrecer_descarga`). |
| `tests/test_interfaz.py` | Libre: añadir o actualizar pruebas de interfaz. |
| Imágenes o recursos visuales nuevos (por ejemplo, `ui/recursos/`) | Libre. Que sean livianos y con licencia compatible. |

### Qué no debe modificarse sin coordinación

| Archivos | Motivo |
|---|---|
| `ui/tareas.py` | Garantiza que Chroma y el modelo nunca se usen desde dos hilos. Un error aquí congela la interfaz o corrompe datos. |
| `servicios.py` | Contrato con el frontend y lógica de negocio. Si falta una función, se pide (ver abajo). |
| `db_redis.py`, `db_catalogo.py`, `db_personas.py`, `db_prestamos.py`, `db_libros.py` | Estructuras de Redis y ChromaDB. Un cambio exige migración. |
| `modelos.py`, `gestor_modelos.py`, `modelo_simulado.py` | Modelo semántico y su revisión fijada. |
| `seguridad.py`, `validaciones.py` | Cifrado, control de acceso y reglas de datos (LFPDPPP). |
| `config.py`, `.env.example`, `requirements.txt`, `docker-compose.yml`, `main.py` | Configuración y arranque compartidos. |
| `datos/`, `tests/` salvo `test_interfaz.py`, `tests/test_arquitectura.py` | Datos de prueba y protección de la arquitectura. |

«Coordinar» significa abrir un issue o comentar en el PR **antes** de hacer el cambio y pedir la revisión del responsable de backend.

### Cómo pedir una función nueva al backend

1. Abre un issue con la plantilla *Nueva funcionalidad* y la etiqueta `backend`. Indica qué dato u operación necesita la interfaz, con qué parámetros y qué esperas recibir.
2. Backend la implementa en la sección de API de `servicios.py`, con su prueba en `tests/test_api_interfaz.py` y su documentación en `INTEGRACION.md`.
3. Mientras tanto, la interfaz puede preparar la vista con datos de ejemplo del modo de demostración.

**Nunca** se accede a Redis, a ChromaDB ni al modelo desde `ui/` «de forma temporal»: la prueba de arquitectura lo rechaza.

### Cómo probar la interfaz sin tocar datos reales

```bash
python demo_interfaz.py                      # datos de ejemplo en memoria, contraseña demo1234
python -m pytest tests/test_interfaz.py tests/test_arquitectura.py
```

Detalle en [INTEGRACION.md › Probar la interfaz](INTEGRACION.md#6-probar-la-interfaz-sin-tocar-datos-reales).

### Flujo recomendado para el frontend

```bash
git switch develop && git pull
git switch -c feature/ui-rediseno-catalogo
python demo_interfaz.py                      # iterar sobre el diseño
python -m pytest tests                       # antes de cada commit
git add ui/vistas/libros.py ui/componentes.py
git commit -m "feat(ui): tarjetas de libro en el catálogo"
git push -u origin feature/ui-rediseno-catalogo
```

En el PR, adjunta capturas tomadas con el modo de demostración y marca la casilla «Respeta el contrato de INTEGRACION.md».

## Organización de ramas

| Rama | Propósito | Quién integra |
|---|---|---|
| `main` | Versión estable y demostrable. Solo recibe merges desde `develop` (o `fix/*` urgentes). | Responsable del repositorio, tras revisión. |
| `develop` | Integración de los cambios terminados. Base de todas las ramas de trabajo. | Mediante Pull Request revisado. |
| `feature/<tema>` | Nuevas funcionalidades. Ej.: `feature/reporte-vencidos`. | Se abre PR hacia `develop`. |
| `fix/<tema>` | Correcciones. Ej.: `fix/isbn-guiones`. | PR hacia `develop` (o hacia `main` si es urgente). |

En GitHub, `main` y `develop` están protegidas: los cambios entran solo por Pull Request con al menos una aprobación, no se permite reescribir el historial (*force push*) ni borrar la rama, y las conversaciones deben quedar resueltas. Las pruebas automáticas (`.github/workflows/pruebas.yml`) se ejecutan en cada Pull Request.

## Flujo de trabajo

### 1. Clonar el repositorio (una sola vez)

```bash
git clone https://github.com/<usuario>/<repositorio>.git
cd <repositorio>
git switch develop
```

Después sigue la [instalación rápida](README.md#instalación-rápida-para-colaboradores).

### 2. Crear una rama

```bash
git switch develop
git pull origin develop
git switch -c feature/nombre-corto
```

### 3. Realizar cambios

- Ejecuta las pruebas antes de confirmar: `python -m pytest tests`.
- Si cambias el comportamiento, agrega o actualiza las pruebas en `tests/`.
- Mantén la documentación al día (README, ARQUITECTURA, SEGURIDAD) cuando corresponda.
- **Nunca** incluyas `.env`, `secrets/`, `chroma_db/`, modelos, registros ni datos personales reales. Revisa siempre `git status` antes de confirmar.

### 4. Crear commits descriptivos

Formato recomendado (*Conventional Commits*, en español):

```
<tipo>(<ámbito opcional>): <resumen en imperativo, máx. 72 caracteres>

<detalle opcional: qué y por qué>
```

| Tipo | Uso |
|---|---|
| `feat` | Nueva funcionalidad. |
| `fix` | Corrección de un error. |
| `docs` | Solo documentación. |
| `test` | Pruebas. |
| `refactor` | Cambio interno sin alterar el comportamiento. |
| `style` | Formato, sin cambio de lógica. |
| `chore` | Mantenimiento (dependencias, configuración). |

Ejemplos:

```bash
git add ui/vistas/prestamos.py tests/test_prestamos.py
git commit -m "feat(prestamos): permitir renovar un préstamo antes de su vencimiento"
git commit -m "fix(catalogo): aceptar ISBN con espacios al importar CSV"
```

Haz commits pequeños y con un solo propósito. Usa `git add <archivos>` en lugar de `git add .` para no incluir archivos por accidente.

### 5. Subir la rama

```bash
git push -u origin feature/nombre-corto
```

### 6. Crear un Pull Request

1. En GitHub aparecerá **Compare & pull request**. La base es `develop` y la rama de comparación es la tuya.
2. Completa la plantilla: qué cambia, cómo se probó y la lista de verificación.
3. Asigna al menos un revisor.

### 7. Revisar cambios

Quien revisa:

- Descarga la rama y la prueba localmente:
  ```bash
  git fetch origin
  git switch feature/nombre-corto
  python -m pytest tests
  python main.py
  ```
- Comprueba que no se suban secretos ni datos personales, que las pruebas pasen y que el código siga las convenciones.
- Comenta en GitHub. Usa **Request changes** si hay que corregir algo y **Approve** cuando esté listo.

Quien hizo el cambio atiende los comentarios con nuevos commits en la misma rama (`git push` actualiza el PR).

### 8. Integrar modificaciones

- Con el PR aprobado y las pruebas en verde, integra con **Squash and merge** (un commit limpio en `develop`) y borra la rama.
- Actualiza tu copia local:
  ```bash
  git switch develop
  git pull origin develop
  git branch -d feature/nombre-corto
  ```
- Para publicar una versión estable: crea un PR de `develop` hacia `main` y, tras integrarlo, etiqueta la versión:
  ```bash
  git switch main && git pull
  git tag -a v1.0.0 -m "Versión 1.0.0"
  git push origin v1.0.0
  ```

### Mantener tu rama al día

```bash
git fetch origin
git rebase origin/develop      # o: git merge origin/develop
python -m pytest tests
git push --force-with-lease    # solo si hiciste rebase de una rama que ya habías subido
```

## Convenciones de código

- Python 3.10+, nombres descriptivos en español, igual que el resto del proyecto.
- Sin comentarios que expliquen lo obvio; docstrings en las interfaces públicas y en los componentes complejos.
- Configuración solo en `config.py` y `.env`; nada de valores importantes dispersos por el código.
- Los datos personales nunca deben llegar a los registros (`log`) ni a la bitácora de actividad.
- La interfaz no debe hacer trabajo pesado (Chroma, modelo) en el hilo de Tkinter: usa `app.tareas.ejecutar(...)`.

## Datos y privacidad

- Usa únicamente los datos de ejemplo de `datos/` o personas ficticias.
- No compartas tu `secrets/`, tu `.env`, tu `chroma_db/` ni volcados de Redis con otros integrantes: cada uno genera los suyos.
- Si por error subes un secreto, **avisa de inmediato** al responsable: hay que cambiar ese secreto y limpiar el historial.
