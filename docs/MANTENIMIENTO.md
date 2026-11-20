# Mantenimiento y diagnóstico

Herramientas y procedimientos para diagnosticar y resolver problemas. Antes que nada, ejecuta:

```powershell
python verificar.py
```

Revisa la versión de Python, las dependencias, la configuración (`config.validar()`), la conexión a Redis y si la base está libre de llaves ajenas, el dispositivo y el modelo descargado, y la existencia de la llave AES y de la contraseña del operador.

## 1. Fuentes de información

| Fuente | Contenido | Ubicación |
|---|---|---|
| `biblioteca.log` | Arranque, cierre, errores con su traza técnica. **Sin datos personales.** | Raíz del proyecto; rota al llegar a 1 MB y conserva 2 copias (`RotatingFileHandler`). |
| Bitácora de actividad | Últimos 100 eventos de negocio (altas, préstamos, devoluciones…). | Redis `bib:actividad`; se muestra en el Dashboard. |
| Configuración › Sistema | Redis, prefijo, esquema, colección, documentos, modelo, GPU y versiones. | Dentro de la aplicación. |
| Configuración › Sincronización | Diferencias entre Redis y Chroma. | Dentro de la aplicación. |
| `gestionar_modelos.py estado` | Modelos descargados, revisión y ubicación. | Terminal. |
| `gestionar_secretos.py estado` | Si existen la llave, la contraseña y la llave heredada, sin mostrarlas. | Terminal. |

## 2. Python y dependencias

| Problema | Diagnóstico | Solución |
|---|---|---|
| `ModuleNotFoundError` | `python -c "import sys; print(sys.executable)"` muestra un Python fuera de `.venv`. | Activa `.venv` o selecciona su intérprete; `main.py` intenta relanzarse con él. |
| Falta Tkinter | `python -m tkinter` falla. | Reinstala Python con Tcl/Tk. |
| Versión incompatible | `python verificar.py` marca la versión de Python. | Usa Python 3.10 o superior. |
| PyTorch sin CUDA | `python -c "import torch; print(torch.cuda.is_available())"` devuelve `False`. | Reinstala torch con el índice de tu CUDA o trabaja en CPU. |
| Actualizar dependencias | — | `pip install -U -r requirements.txt` y después `python -m pytest tests`. |

## 3. Redis

| Problema | Diagnóstico | Solución |
|---|---|---|
| Sin conexión | `redis-cli -h HOST -p PUERTO ping` | Inicia el servicio; revisa `REDIS_HOST`, `REDIS_PORT` y el firewall. |
| Autenticación | Error «Redis rechazó la conexión». | Revisa `REDIS_USUARIO` y `REDIS_PASSWORD`. |
| Base ocupada | `redis-cli -n 2 --scan \| findstr /v /b "bib:"` muestra llaves ajenas. | Usa otra `REDIS_DB` vacía. **No borres** datos de otros proyectos. |
| Cuántas llaves tiene la aplicación | `redis-cli -n 2 --scan --pattern "bib:*"` | — |
| Inspeccionar un libro | `redis-cli -n 2 HGETALL bib:libro:libro09` | — |
| Inspeccionar un préstamo | `redis-cli -n 2 HGETALL bib:prestamo:PR000001` | — |
| Ver la versión del servidor | `redis-cli INFO server` | Algunos servidores bloquean `INFO`; la aplicación muestra entonces «desconocida». |

> **Advertencia.** Los campos de `bib:persona:*` están cifrados (`v2:…`) y no se pueden leer desde `redis-cli`. **Nunca** modifiques a mano los HASH de personas: el cifrado está ligado al id y al campo, y un valor copiado o editado se marcará como dato con error de integridad.

**Persistencia y respaldo**: dependen de la configuración de tu servidor Redis (RDB y AOF). Con Docker Compose, los datos están en el volumen `redis_datos` con AOF activo. Para respaldar, ejecuta `redis-cli BGSAVE` y copia el archivo `dump.rdb` del directorio de datos del servidor, o respalda el volumen de Docker.

## 4. ChromaDB

| Problema | Diagnóstico | Solución |
|---|---|---|
| Libros sin búsqueda | Configuración › Sincronización › Revisar: «Libros en Redis sin documento en Chroma». | Edita esos libros con su sinopsis o vuelve a darlos de alta. |
| Documentos huérfanos | La misma revisión muestra «Documentos en Chroma sin registro en Redis». | **Importar documentos huérfanos**; nunca se borran automáticamente. |
| Metadatos distintos | La revisión los lista. | **Reparar metadatos** (copia de Redis a Chroma). |
| «Error in compaction» u otros errores internos | `biblioteca.log` | Cierra la aplicación, respalda `chroma_db/` y vuelve a abrir. Si persiste, restaura el respaldo. Se observó una vez en pruebas, con archivos temporales en Windows. |
| Empezar de cero | — | Cierra la aplicación, borra `chroma_db/` y `modelo_activo.txt`, y vuelve a importar. Los libros de Redis quedarían sin sinopsis: haz el borrado junto con el de Redis, o reimporta los CSV. |

**Respaldo**: copia la carpeta `BIBLIOTECA_CHROMA_PATH` con la aplicación cerrada.

## 5. Modelo semántico

| Problema | Diagnóstico | Solución |
|---|---|---|
| «Modelo no disponible» | `python gestionar_modelos.py estado` | `python gestionar_modelos.py descargar` |
| Descarga interrumpida | — | Repite la descarga: solo se bajan los archivos faltantes. |
| Archivos corruptos | `python gestionar_modelos.py validar` falla. | Borra la carpeta `models--Qwen--Qwen3-Embedding-0.6B` de la caché y vuelve a descargar. |
| Sin conexión o detrás de un proxy | Mensaje `SinConexion`. | Revisa la red y el proxy (`HTTPS_PROXY`), y que `HF_HUB_OFFLINE` no esté definida. |
| Memoria GPU insuficiente | `CUDA out of memory` en `biblioteca.log`. | `BIBLIOTECA_DISPOSITIVO=cpu` o cierra otras aplicaciones que usen la GPU. |
| Calidad de búsqueda | `python evaluar_busqueda.py` | Compara con los valores de referencia de [PRUEBAS.md](../PRUEBAS.md). |

## 6. Cifrado y secretos

| Problema | Diagnóstico | Solución |
|---|---|---|
| «Llave de cifrado inválida» | `BIBLIOTECA_AES_KEY` no es base64 o no mide 32 bytes. | Corrígela o déjala vacía para usar `secrets/biblioteca_aes.key`. |
| Personas con «datos ilegibles» o fila en rojo | La llave cambió o el dato se alteró. | Restaura el respaldo de `secrets/biblioteca_aes.key`. Sin la llave original, los datos no se recuperan. |
| Contraseña de operador olvidada | — | `python gestionar_secretos.py contrasena` (no afecta a los datos cifrados). |
| Demasiados intentos | Mensaje «Espera 30 s». | Espera; el contador se reinicia. |
| Datos del esquema anterior (Fernet) | Configuración › Seguridad indica cuántos hay. | **Migrar cifrado heredado** (requiere `clave.key`). |

## 7. Interfaz

| Problema | Diagnóstico | Solución |
|---|---|---|
| Texto borroso o cortado | Escala de Windows al 125–150 %. | Ejecuta con `python main.py`, que activa el modo de alta densidad. |
| Iconos como cuadros | Linux o macOS sin Segoe Fluent Icons. | Es normal: se usan símbolos Unicode de respaldo. |
| La ventana no responde | Una operación pesada se ejecutó en el hilo de la interfaz. | Toda llamada que toque Chroma o el modelo debe ir en `self.tarea(...)` ([INTEGRACION.md](../INTEGRACION.md)). |
| «Error inesperado» | `biblioteca.log` contiene la traza. | Reproduce el problema con `python demo_interfaz.py` y ábrelo como issue. |
| Sesión bloqueada | Pasaron `BIBLIOTECA_MINUTOS_BLOQUEO` minutos sin actividad. | Vuelve a introducir la contraseña. |

### Portadas

| Problema | Diagnóstico | Solución |
|---|---|---|
| «No hay conexión con Open Library» | Error de la categoría `red`. | Revisa la red y el proxy; se puede reintentar más tarde, porque solo se buscan las portadas que faltan. |
| Un libro no encuentra portada | Open Library no la tiene o el título no coincide. | Usa **Elegir imagen…** en la ficha del libro. |
| Portada equivocada | Open Library devolvió la edición de otro libro con título parecido. | **Quitar portada** y elige la imagen a mano. |
| «Buscar en internet» deshabilitado | `BIBLIOTECA_DESCARGAR_PORTADAS=0`. | Cambia la variable a `1` o elige imágenes del equipo. |
| Empezar de cero | — | Cierra la aplicación y borra la carpeta `portadas/`; no afecta a Redis ni a ChromaDB. |

## 8. Configuración

`config.validar()` informa de cada problema por su nombre de variable. Los más comunes son un `REDIS_PORT` no numérico, un `REDIS_DB` fuera de 0–15, un `REDIS_PREFIJO` sin `:` final, un `BIBLIOTECA_DISPOSITIVO` distinto de `auto`, `cuda` o `cpu`, un `BIBLIOTECA_MODELO` inexistente, un `BIBLIOTECA_PERMITIR_DESCARGA` distinto de 1 o 0, y carpetas sin permiso de escritura. Si falta `.env`, se usan los valores por defecto y `verificar.py` lo avisa.

## 9. Git y GitHub

| Problema | Solución |
|---|---|
| `push` rechazado en `main` o `develop` | Si el mensaje habla de *non-fast-forward*, alguien subió cambios antes: `git pull` y vuelve a subir. Si dice *protected branch*, intentaste un *force push* o borrar la rama, que están bloqueados. |
| `push` bloqueado por *push protection* | Has incluido algo que parece un secreto: quítalo del commit (`git reset HEAD~1`, corrige y vuelve a confirmar) y cambia ese secreto. |
| Conflictos | Ver [CONTRIBUCION.md](CONTRIBUCION.md), sección 5. |
| Rama desactualizada | `git fetch origin` y `git merge origin/develop`. |
| Avisos LF/CRLF | `.gitattributes` normaliza a LF en el repositorio; los avisos son informativos. |

## 10. Pruebas de regresión

```powershell
python -m pytest tests                                         # rápido, sin servicios externos
$env:BIBLIOTECA_PRUEBAS_REALES="1"; python -m pytest tests     # con Redis, Chroma y el modelo reales
python -m pytest tests/test_arquitectura.py                    # contrato frontend ↔ backend
```

En Windows se han observado fallos intermitentes del entorno, como Tk sin poder leer `init.tcl` en un momento puntual. `tests/test_interfaz.py` reintenta crear la ventana. Si una prueba falla una sola vez, repítela antes de investigar.
