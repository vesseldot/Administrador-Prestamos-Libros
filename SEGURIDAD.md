# Seguridad y protección de datos personales

> Este documento describe **medidas técnicas**. Implementar cifrado y controles de acceso **no basta para afirmar que el sistema cumple la LFPDPPP**. El cumplimiento depende también de medidas administrativas, físicas y de procedimientos del responsable, que deben revisarse con asesoría legal (ver sección 6).

## 1. Datos que se tratan

| Dato | Clasificación | Almacenamiento |
|---|---|---|
| Nombre, apellidos, fecha de nacimiento, género, correo, teléfono, domicilio (calle, colonia, ciudad, estado, C.P.), ocupación | Personales | Cifrados por campo en Redis. |
| Tipo de usuario (Alumno, Profesor o Externo) | Personal no identificativo, necesario para filtrar | En claro. |
| Edad | Derivada | **No se almacena**: se calcula al mostrar. |
| Aceptación del aviso y sus fechas | Prueba del consentimiento | En claro. |
| Catálogo de libros | Público | Redis y Chroma, sin cifrar. |

No se recaban datos personales sensibles. El catálogo y los datos personales están separados: Chroma solo contiene información de libros.

## 2. Medidas técnicas implementadas

### Cifrado autenticado
- **AES-256-GCM** (`cryptography.hazmat.primitives.ciphers.aead.AESGCM`) con un nonce aleatorio de 96 bits por valor. Formato: `v2:` + base64(nonce ‖ cifrado ‖ etiqueta).
- **Datos asociados (AAD)** = `persona:{id}:{campo}`. Si alguien copia el teléfono de una persona en el campo de otra, o intercambia campos, la verificación falla. Así se detectan tanto las alteraciones como los intercambios de valores.
- Si el descifrado falla, el campo se muestra vacío, el registro se marca con un aviso de integridad y el error se informa sin exponer el dato.

### Gestión de llaves
- Llave maestra de 256 bits tomada de la variable de entorno `BIBLIOTECA_AES_KEY` o del archivo `secrets/biblioteca_aes.key`, que se genera la primera vez.
- `secrets/`, `.env`, `*.key` y `clave.key` están en `.gitignore`. Ninguna llave ni contraseña aparece en el código.
- **HKDF-SHA256** deriva dos llaves independientes a partir de la maestra: una para cifrar y otra para el índice ciego.
- La llave heredada (`clave.key`, Fernet) **solo se lee** para descifrar datos del esquema anterior; no se modifica.

### Índice ciego del correo
Se guarda un **HMAC-SHA256** del correo normalizado para detectar duplicados sin guardar el correo en claro y sin descifrar a todas las personas. La reserva usa `SET NX`, de modo que dos altas simultáneas no pueden quedarse con el mismo correo.

### Control de acceso
- **Contraseña de operador** guardada solo como hash **scrypt** (N=2¹⁵, r=8, p=1, sal aleatoria de 16 bytes) y comparada en tiempo constante.
- Tras **5 intentos fallidos** el acceso queda en espera **30 segundos**.
- **Bloqueo automático** tras 15 minutos de inactividad (configurable) y botón «Bloquear sesión». La pantalla de bloqueo cubre toda la ventana y cierra los diálogos abiertos.
- La contraseña se cambia desde **Configuración › Seguridad** o con `python gestionar_secretos.py contrasena`.
- La lógica de autenticación (verificación, intentos y espera) vive en `seguridad.ControlAcceso`, en el backend. La interfaz solo la presenta, así que un rediseño visual no puede debilitarla por accidente.
- Redis admite autenticación por contraseña o por usuario ACL (`REDIS_USUARIO`, `REDIS_PASSWORD`) y conexión TLS (`REDIS_SSL=1`) para servidores remotos.

### Minimización y visualización
- En los listados, el correo y el teléfono aparecen enmascarados (`an***@correo.mx`, `******4567`).
- En «Personas con préstamos», el contacto se revela solo para la persona seleccionada y durante 20 segundos, cuando hace falta para la operación.
- La búsqueda de personas solo usa nombre, apellidos, id, tipo, ocupación, ciudad y estado. **No se busca por correo ni por teléfono.**

### Registro de eventos
- La bitácora (`bib:actividad`) y el archivo `biblioteca.log` guardan **solo identificadores** (P0001, libro09, PR000001), nunca nombres, correos ni teléfonos.
- Los errores inesperados se registran con su tipo y traza técnica, sin incluir valores de campos.

### Derechos ARCO y consentimiento
| Derecho | Implementación |
|---|---|
| Consentimiento | Casilla obligatoria. No se guarda a nadie que no haya aceptado el aviso. Se registra la fecha de aceptación, que no se sobrescribe al rectificar. |
| Acceso | Ficha completa con el historial de préstamos y **exportación a JSON**. |
| Rectificación | Edición validada; se registra la fecha de la última rectificación. |
| Cancelación | Borra el registro y el índice del correo. Se bloquea si hay préstamos activos. El historial de préstamos se conserva **solo con el identificador** (seudonimizado) para el control del acervo. |
| Oposición | Se atiende en el mostrador (procedimiento administrativo); el sistema permite la cancelación. |

### Integridad del sistema
- Redis en una base dedicada con prefijo propio. La aplicación **se niega a arrancar** si la base contiene llaves ajenas.
- Transacciones `WATCH/MULTI` en préstamos, compensación entre Redis y Chroma, y reparación de la sincronización.
- Validación estricta de toda entrada: formatos, listas cerradas, longitudes máximas, ISBN con dígito de control y caracteres permitidos en los ids que forman parte de las llaves de Redis.

## 3. Secretos por instalación

Cada integrante genera **sus propios** secretos; el repositorio no contiene ninguno:

- `.env` (configuración local), `secrets/biblioteca_aes.key` (llave AES), `secrets/operador.hash` (hash de la contraseña) y `clave.key` (llave heredada del proyecto original) están en `.gitignore`.
- Los datos de cada instalación (Redis y ChromaDB) son locales y no se comparten. Por eso no hace falta compartir llaves entre integrantes.

## 3.1 Respaldo y rotación de la llave

1. **Respalda `secrets/biblioteca_aes.key` fuera del equipo** (por ejemplo, en un gestor de contraseñas). Sin ella, los datos personales son irrecuperables.
2. Para usar una variable de entorno en lugar del archivo, genera una llave con `python gestionar_secretos.py nueva-llave` y defínela en `BIBLIOTECA_AES_KEY`. Hazlo **antes** de registrar personas: cambiar la llave con datos existentes los vuelve ilegibles.
3. La rotación de llave con datos existentes (descifrar con la anterior y volver a cifrar con la nueva) **no está automatizada**. Queda como mejora pendiente; existe solo la migración de Fernet a AES-GCM.

## 4. Riesgos que no cubre esta versión

| Riesgo | Situación | Recomendación |
|---|---|---|
| Redis sin contraseña ni TLS | `docker-compose.yml` publica Redis solo en `127.0.0.1` y activa `requirepass` si se define `REDIS_PASSWORD`. Sin contraseña, cualquier proceso local puede leer la base (los datos personales siguen cifrados). No hay TLS. | Definir `REDIS_PASSWORD` y usar TLS (`rediss://`) si Redis está en otro equipo. |
| Persistencia de Redis | `docker-compose.yml` usa el volumen `redis_datos` con AOF. `docker compose down -v` borra los datos. | Respaldar el volumen o los archivos AOF/RDB periódicamente. |
| Secretos en disco | `secrets/` está en claro en el sistema de archivos. | Cifrado de disco (BitLocker), permisos restringidos o un gestor de secretos. |
| Un solo operador | No hay cuentas individuales ni roles. | Usuarios con roles y bitácora de accesos por operador. |
| Bitácora de consultas | Se registran altas y cambios, pero no cada consulta de una ficha. | Registrar los accesos a datos personales si la política interna lo exige. |
| Copias exportadas | El JSON de exportación ARCO queda en claro donde se guarde. | Entregarlo solo al titular y borrarlo después. |
| ChromaDB | Solo contiene datos del catálogo; no requiere cifrado. | — |

## 5. Alternativas consideradas

- **Fernet** (esquema anterior): AES-128-CBC + HMAC. Es seguro, pero se migró a AES-256-GCM a petición de la especificación y para ligar cada valor a su campo mediante AAD.
- **bcrypt/argon2**: adecuados para contraseñas; se eligió scrypt porque viene en la biblioteca estándar de Python y no añade dependencias. No sirven para datos que hay que volver a leer.
- **Cifrado de toda la persona como un solo bloque**: más simple, pero impide verificar campo por campo y obliga a reescribir todo en cada cambio.

## 6. Aspectos legales que requieren revisión

Lo siguiente **no** lo resuelve el software y debe validarse con el área jurídica responsable:

- **Aviso de privacidad**: el texto incluido es un aviso *simplificado* de ejemplo. Falta definir la identidad y el domicilio del responsable, el aviso integral, los medios para ejercer los derechos ARCO y el mecanismo para comunicar cambios del aviso.
- **Plazos y procedimiento ARCO**: los plazos de respuesta, los requisitos de identificación del titular y el registro de solicitudes deben ajustarse a la ley vigente (LFPDPPP publicada en el DOF el 20 de marzo de 2025) y a su reglamento.
- **Menores de edad**: la validación admite cualquier edad entre 0 y 120 años, y los alumnos pueden ser menores. El consentimiento de quien ejerce la patria potestad requiere un procedimiento que el sistema no implementa.
- **Conservación y supresión**: hay que definir cuánto tiempo se conserva el historial seudonimizado y los registros de personas inactivas, y el procedimiento de bloqueo previo a la supresión.
- **Responsable y encargados**: designar a la persona o al departamento de datos personales, documentar las medidas de seguridad administrativas y físicas y capacitar al personal.
- **Vulneraciones**: definir el procedimiento para notificar a los titulares en caso de una vulneración de seguridad.
- **Autoridad**: el aviso menciona a la Secretaría Anticorrupción y Buen Gobierno como autoridad de vigilancia según la ley de 2025. Debe confirmarse que esta referencia siga vigente al momento de usar el sistema.
