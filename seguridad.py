"""Protección de datos personales y control de acceso del operador.

- Cifrado autenticado AES-256-GCM por campo, con datos asociados (AAD) que ligan
  cada valor cifrado a su registro y a su campo.
- Llaves derivadas con HKDF-SHA256 a partir de una llave maestra de 256 bits
  que se obtiene de BIBLIOTECA_AES_KEY o de secrets/biblioteca_aes.key.
- Índice ciego HMAC-SHA256 para detectar correos duplicados sin descifrar.
- Hash scrypt para la contraseña del operador.
- Lectura de valores heredados cifrados con Fernet (clave.key), solo lectura.
"""
import base64
import binascii
import hashlib
import hmac
import os
import secrets
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

import config

PREFIJO_TOKEN = "v2:"
LONGITUD_NONCE = 12
LONGITUD_LLAVE = 32


class ErrorCifrado(Exception):
    """El valor no se pudo descifrar: llave incorrecta o dato alterado."""


class ErrorLlave(Exception):
    """La llave maestra no existe o tiene un formato inválido."""


def _b64(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).decode("ascii")


def _desde_b64(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto.encode("ascii"))


def _escribir_secreto(ruta: Path, contenido: str):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="ascii") as archivo:
        archivo.write(contenido)


def generar_llave_maestra() -> str:
    return _b64(secrets.token_bytes(LONGITUD_LLAVE))


def _decodificar_llave(texto: str, origen: str) -> bytes:
    try:
        llave = _desde_b64(texto.strip())
    except (binascii.Error, ValueError) as error:
        raise ErrorLlave(f"La llave de {origen} no es base64 válido.") from error
    if len(llave) != LONGITUD_LLAVE:
        raise ErrorLlave(f"La llave de {origen} debe tener {LONGITUD_LLAVE} bytes.")
    return llave


def cargar_llave_maestra(crear_si_falta: bool = True) -> bytes:
    """Obtiene la llave maestra de la variable de entorno o del archivo de secretos."""
    desde_entorno = os.environ.get("BIBLIOTECA_AES_KEY")
    if desde_entorno:
        return _decodificar_llave(desde_entorno, "BIBLIOTECA_AES_KEY")
    ruta = config.ARCHIVO_LLAVE_AES
    if ruta.exists():
        return _decodificar_llave(ruta.read_text(encoding="ascii"), str(ruta.name))
    if not crear_si_falta:
        raise ErrorLlave("No existe la llave maestra de cifrado.")
    texto = generar_llave_maestra()
    _escribir_secreto(ruta, texto)
    return _desde_b64(texto)


def cargar_llave_legada() -> bytes | None:
    """Llave Fernet del esquema anterior, solo para leer datos heredados."""
    desde_entorno = os.environ.get("BIBLIOTECA_KEY")
    if desde_entorno:
        return desde_entorno.encode("ascii")
    if config.ARCHIVO_LLAVE_LEGADA.exists():
        return config.ARCHIVO_LLAVE_LEGADA.read_bytes().strip()
    return None


def _derivar(llave_maestra: bytes, proposito: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=LONGITUD_LLAVE, salt=None,
                info=proposito).derive(llave_maestra)


class Cifrador:
    """Cifra y descifra campos de texto con AES-256-GCM."""

    def __init__(self, llave_maestra: bytes | None = None, llave_legada: bytes | None = None):
        llave_maestra = llave_maestra or cargar_llave_maestra()
        self._aes = AESGCM(_derivar(llave_maestra, b"biblioteca/datos-personales/v2"))
        self._llave_indice = _derivar(llave_maestra, b"biblioteca/indice-correo/v2")
        self._fernet = None
        if llave_legada:
            from cryptography.fernet import Fernet
            self._fernet = Fernet(llave_legada)

    def cifrar(self, texto: str, contexto: str) -> str:
        nonce = os.urandom(LONGITUD_NONCE)
        cifrado = self._aes.encrypt(nonce, str(texto).encode("utf-8"), contexto.encode("utf-8"))
        return PREFIJO_TOKEN + _b64(nonce + cifrado)

    def descifrar(self, token: str, contexto: str) -> str:
        if not token:
            return ""
        if token.startswith(PREFIJO_TOKEN):
            try:
                crudo = _desde_b64(token[len(PREFIJO_TOKEN):])
                nonce, cifrado = crudo[:LONGITUD_NONCE], crudo[LONGITUD_NONCE:]
                return self._aes.decrypt(nonce, cifrado, contexto.encode("utf-8")).decode("utf-8")
            except (InvalidTag, binascii.Error, ValueError) as error:
                raise ErrorCifrado("Dato alterado o llave incorrecta.") from error
        if self._fernet is not None:
            from cryptography.fernet import InvalidToken
            try:
                return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
            except (InvalidToken, ValueError) as error:
                raise ErrorCifrado("Dato heredado ilegible con la llave anterior.") from error
        raise ErrorCifrado("Formato de cifrado desconocido.")

    @staticmethod
    def es_heredado(token: str) -> bool:
        return bool(token) and not token.startswith(PREFIJO_TOKEN)

    def hash_indice(self, texto: str) -> str:
        normalizado = texto.strip().lower().encode("utf-8")
        return hmac.new(self._llave_indice, normalizado, hashlib.sha256).hexdigest()


PARAMETROS_SCRYPT = {"n": 2 ** 15, "r": 8, "p": 1}
MEMORIA_SCRYPT = 64 * 1024 * 1024


def hash_contrasena(contrasena: str) -> str:
    sal = os.urandom(16)
    derivada = hashlib.scrypt(contrasena.encode("utf-8"), salt=sal, dklen=32,
                              maxmem=MEMORIA_SCRYPT, **PARAMETROS_SCRYPT)
    p = PARAMETROS_SCRYPT
    return f"scrypt${p['n']}${p['r']}${p['p']}${_b64(sal)}${_b64(derivada)}"


def verificar_contrasena(contrasena: str, almacenado: str) -> bool:
    try:
        algoritmo, n, r, p, sal, esperado = almacenado.strip().split("$")
        if algoritmo != "scrypt":
            return False
        derivada = hashlib.scrypt(contrasena.encode("utf-8"), salt=_desde_b64(sal), dklen=32,
                                  n=int(n), r=int(r), p=int(p), maxmem=MEMORIA_SCRYPT)
        return hmac.compare_digest(derivada, _desde_b64(esperado))
    except (ValueError, binascii.Error):
        return False


def leer_hash_operador() -> str | None:
    desde_entorno = os.environ.get("BIBLIOTECA_OPERADOR_HASH")
    if desde_entorno:
        return desde_entorno.strip()
    if config.ARCHIVO_HASH_OPERADOR.exists():
        return config.ARCHIVO_HASH_OPERADOR.read_text(encoding="ascii").strip() or None
    return None


def guardar_hash_operador(contrasena: str):
    if len(contrasena) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres.")
    _escribir_secreto(config.ARCHIVO_HASH_OPERADOR, hash_contrasena(contrasena))


class ControlAcceso:
    """Autenticación del operador: verificación, intentos fallidos y espera tras bloqueo.

    `leer_hash` y `guardar_hash` permiten sustituir el almacenamiento del hash
    (por ejemplo, en memoria para el modo de demostración).
    """

    def __init__(self, maximo_intentos: int = config.MAX_INTENTOS_ACCESO,
                 espera_segundos: int = config.SEGUNDOS_ESPERA_TRAS_FALLOS,
                 leer_hash=None, guardar_hash=None):
        self.maximo = maximo_intentos
        self.espera = espera_segundos
        self.fallos = 0
        self.bloqueado_hasta = 0.0
        self._leer_hash = leer_hash or leer_hash_operador
        self._guardar_hash = guardar_hash or (lambda contrasena: guardar_hash_operador(contrasena))

    def configurado(self) -> bool:
        return self._leer_hash() is not None

    def segundos_restantes(self) -> int:
        import time
        return max(0, int(self.bloqueado_hasta - time.monotonic() + 0.999))

    def intentar(self, contrasena: str) -> tuple[bool, str]:
        """Regresa (correcto, mensaje_para_el_usuario)."""
        import time
        if self.segundos_restantes():
            return False, f"Demasiados intentos. Espera {self.segundos_restantes()} s."
        almacenado = self._leer_hash()
        if almacenado and verificar_contrasena(contrasena, almacenado):
            self.fallos = 0
            return True, ""
        self.fallos += 1
        if self.fallos >= self.maximo:
            self.fallos = 0
            self.bloqueado_hasta = time.monotonic() + self.espera
            return False, f"Demasiados intentos. Espera {self.espera} s."
        return False, f"Contraseña incorrecta ({self.maximo - self.fallos} intento(s) restante(s))."

    def crear_contrasena(self, contrasena: str, repetida: str):
        """Primer uso. Lanza ValueError si no coinciden o si es demasiado corta."""
        if contrasena != repetida:
            raise ValueError("Las contraseñas no coinciden.")
        self._guardar_hash(contrasena)

    def cambiar_contrasena(self, actual: str, nueva: str, repetida: str):
        """Lanza ValueError con un mensaje para el usuario si algo no es válido."""
        correcto, mensaje = self.intentar(actual)
        if not correcto:
            raise ValueError(mensaje)
        if nueva != repetida:
            raise ValueError("Las contraseñas nuevas no coinciden.")
        self._guardar_hash(nueva)


def enmascarar_correo(correo: str) -> str:
    if "@" not in (correo or ""):
        return "***"
    usuario, dominio = correo.split("@", 1)
    return (usuario[:2] + "***@" + dominio) if len(usuario) > 2 else ("***@" + dominio)


def enmascarar_telefono(telefono: str) -> str:
    return "******" + telefono[-4:] if len(telefono or "") >= 4 else "****"


AVISO_PRIVACIDAD = """AVISO DE PRIVACIDAD SIMPLIFICADO

La Biblioteca (el "Responsable") recaba sus datos personales para:
  • Registrarle como usuario de la biblioteca.
  • Administrar los préstamos y devoluciones de libros.
  • Contactarle en caso de retraso en la devolución.

Datos que se recaban: nombre, apellidos, fecha de nacimiento, género, correo,
teléfono, domicilio, ocupación y tipo de usuario. No se recaban datos personales
sensibles.

Medidas de seguridad: sus datos se almacenan cifrados (AES-256-GCM), se muestran
parcialmente ocultos y solo el personal autorizado, identificado con contraseña,
puede consultarlos. No se transfieren a terceros.

Derechos ARCO: usted puede solicitar en cualquier momento el Acceso, la
Rectificación, la Cancelación o la Oposición al tratamiento de sus datos
acudiendo al mostrador de la biblioteca. La cancelación procede cuando no tenga
préstamos pendientes; el historial de préstamos se conserva de forma seudónima
(solo con su identificador) para el control del acervo.

Fundamento: Ley Federal de Protección de Datos Personales en Posesión de los
Particulares (LFPDPPP), publicada en el DOF el 20 de marzo de 2025. La autoridad
encargada de vigilar su cumplimiento es la Secretaría Anticorrupción y Buen Gobierno.

Al marcar la casilla "Acepto el aviso de privacidad" usted otorga su consentimiento.
"""
