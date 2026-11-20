"""Validación y normalización de libros y personas.

Cada función `validar_*` regresa (datos_limpios, lista_de_errores).
"""
import re
import unicodedata
from datetime import date, datetime

ESTADOS_MEXICO = [
    "Aguascalientes", "Baja California", "Baja California Sur", "Campeche", "Chiapas",
    "Chihuahua", "Ciudad de México", "Coahuila", "Colima", "Durango", "Estado de México",
    "Guanajuato", "Guerrero", "Hidalgo", "Jalisco", "Michoacán", "Morelos", "Nayarit",
    "Nuevo León", "Oaxaca", "Puebla", "Querétaro", "Quintana Roo", "San Luis Potosí",
    "Sinaloa", "Sonora", "Tabasco", "Tamaulipas", "Tlaxcala", "Veracruz", "Yucatán",
    "Zacatecas",
]
GENEROS_PERSONA = ["Femenino", "Masculino", "No binario", "Otro", "Prefiero no decir"]
OCUPACIONES = ["Estudiante", "Docente", "Empleado", "Otro"]
TIPOS_USUARIO = ["Alumno", "Profesor", "Externo"]
TIPOS_PASTA = ["blanda", "dura", "digital"]

CAMPOS_LIBRO = ["id", "sinopsis", "isbn", "titulo", "autor", "anio", "editorial", "genero",
                "tema", "idioma", "pasta", "paginas", "calificacion", "disponible"]
CAMPOS_METADATOS_LIBRO = [c for c in CAMPOS_LIBRO if c not in ("id", "sinopsis")]
CAMPOS_TEXTO_LIBRO = ["titulo", "autor", "editorial", "genero", "tema"]

CAMPOS_PERSONA = ["nombre", "apellido_paterno", "apellido_materno", "fecha_nacimiento",
                  "genero", "correo", "telefono", "calle_numero", "colonia", "ciudad",
                  "estado", "codigo_postal", "ocupacion", "tipo_usuario",
                  "acepta_aviso_privacidad"]

RE_ID_LIBRO = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
RE_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
RE_TELEFONO = re.compile(r"^\d{10}$")
RE_CP = re.compile(r"^\d{5}$")
RE_IDIOMA = re.compile(r"^[a-z]{2,3}$")
RE_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")

LONGITUD_MAXIMA = {"titulo": 200, "autor": 200, "editorial": 120, "genero": 60, "tema": 80,
                   "sinopsis": 5000, "nombre": 80, "apellido_paterno": 80,
                   "apellido_materno": 80, "calle_numero": 120, "colonia": 80, "ciudad": 80}


def a_bool(valor) -> bool:
    if isinstance(valor, bool):
        return valor
    return str(valor).strip().lower() in ("true", "1", "si", "sí", "verdadero", "yes", "y")


def normalizar_texto(texto: str) -> str:
    """Minúsculas y sin acentos, para comparar y buscar."""
    descompuesto = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in descompuesto if not unicodedata.combining(c)).lower().strip()


def clave_natural(texto) -> tuple:
    """Clave de orden que compara los números por su valor: libro9 < libro10 < libro100."""
    return tuple(int(parte) if parte.isdigit() else parte.lower()
                 for parte in re.split(r"(\d+)", str(texto)) if parte)


def calcular_edad(fecha_nacimiento: str) -> int:
    nacimiento = datetime.strptime(fecha_nacimiento, "%Y-%m-%d").date()
    hoy = date.today()
    return hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))


def normalizar_isbn(isbn: str) -> str:
    return re.sub(r"[\s-]", "", str(isbn or "")).upper()


def isbn_valido(isbn: str) -> bool:
    """Comprueba longitud y dígito de control de un ISBN-10 o ISBN-13."""
    digitos = normalizar_isbn(isbn)
    if len(digitos) == 13 and digitos.isdigit():
        suma = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(digitos))
        return suma % 10 == 0
    if len(digitos) == 10 and digitos[:9].isdigit() and (digitos[9].isdigit() or digitos[9] == "X"):
        suma = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(digitos))
        return suma % 11 == 0
    return False


def digito_control_isbn13(primeros_12: str) -> str:
    suma = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(primeros_12))
    return str((10 - suma % 10) % 10)


def _texto(valor) -> str:
    return "" if valor is None else str(valor).strip()


def _revisar_longitud(datos: dict, campos, errores: list):
    for campo in campos:
        maximo = LONGITUD_MAXIMA.get(campo)
        if maximo and len(datos.get(campo, "")) > maximo:
            errores.append(f"El campo '{campo}' admite como máximo {maximo} caracteres.")


def validar_libro(datos: dict):
    errores = []
    limpio = {campo: _texto(datos.get(campo)) for campo in CAMPOS_LIBRO if campo != "disponible"}

    for campo in ["id", "sinopsis", "isbn", "titulo", "autor", "editorial", "genero", "tema",
                  "idioma", "pasta"]:
        if not limpio[campo]:
            errores.append(f"El campo '{campo}' es obligatorio.")

    if limpio["id"] and not RE_ID_LIBRO.match(limpio["id"]):
        errores.append("El id solo admite letras, números, guion y guion bajo (máx. 40).")

    if limpio["isbn"] and not isbn_valido(limpio["isbn"]):
        errores.append("ISBN inválido: debe ser ISBN-10 o ISBN-13 con dígito de control correcto.")

    try:
        limpio["anio"] = int(limpio["anio"])
        if not 0 < limpio["anio"] <= date.today().year + 1:
            errores.append("El año debe estar entre 1 y el año próximo.")
    except ValueError:
        errores.append("El año debe ser un número entero.")

    try:
        limpio["paginas"] = int(limpio["paginas"])
        if limpio["paginas"] <= 0:
            errores.append("Las páginas deben ser mayores a 0.")
    except ValueError:
        errores.append("Las páginas deben ser un número entero.")

    try:
        limpio["calificacion"] = round(float(limpio["calificacion"]), 2)
        if not 0 <= limpio["calificacion"] <= 5:
            errores.append("La calificación debe estar entre 0 y 5.")
    except ValueError:
        errores.append("La calificación debe ser un número (ej. 4.3).")

    limpio["pasta"] = limpio["pasta"].lower()
    if limpio["pasta"] and limpio["pasta"] not in TIPOS_PASTA:
        errores.append(f"La pasta debe ser una de: {', '.join(TIPOS_PASTA)}.")

    limpio["idioma"] = limpio["idioma"].lower()
    if limpio["idioma"] and not RE_IDIOMA.match(limpio["idioma"]):
        errores.append("El idioma debe ser un código de 2 o 3 letras (ej. es, en).")

    limpio["genero"] = limpio["genero"].lower()
    disponible = datos.get("disponible", True)
    limpio["disponible"] = True if disponible in (None, "") else a_bool(disponible)
    _revisar_longitud(limpio, CAMPOS_TEXTO_LIBRO + ["sinopsis"], errores)
    return limpio, errores


def validar_persona(datos: dict):
    errores = []
    limpio = {}
    for campo in CAMPOS_PERSONA:
        valor = datos.get(campo, "")
        limpio[campo] = valor if isinstance(valor, bool) else _texto(valor)

    if not limpio["nombre"]:
        errores.append("El nombre es obligatorio.")
    if not limpio["apellido_paterno"]:
        errores.append("El apellido paterno es obligatorio.")

    if not RE_FECHA.match(limpio["fecha_nacimiento"]):
        errores.append("La fecha de nacimiento debe tener formato AAAA-MM-DD (ej. 2004-08-15).")
    else:
        try:
            edad = calcular_edad(limpio["fecha_nacimiento"])
            if not 0 <= edad <= 120:
                errores.append("La fecha de nacimiento no es válida.")
        except ValueError:
            errores.append("La fecha de nacimiento no existe en el calendario.")

    if limpio["genero"] not in GENEROS_PERSONA:
        errores.append("Selecciona un género de la lista.")

    limpio["correo"] = limpio["correo"].lower()
    if not RE_CORREO.match(limpio["correo"]):
        errores.append("El correo debe tener @ y un punto después (ej. ana@mail.com).")

    limpio["telefono"] = re.sub(r"[\s\-()]", "", limpio["telefono"])
    if not RE_TELEFONO.match(limpio["telefono"]):
        errores.append("El teléfono debe tener exactamente 10 dígitos.")

    if not RE_CP.match(limpio["codigo_postal"]):
        errores.append("El código postal debe tener 5 dígitos.")
    if limpio["estado"] not in ESTADOS_MEXICO:
        errores.append("Selecciona un estado de la lista.")
    if limpio["ocupacion"] not in OCUPACIONES:
        errores.append("Selecciona una ocupación de la lista.")
    if limpio["tipo_usuario"] not in TIPOS_USUARIO:
        errores.append("Selecciona un tipo de usuario de la lista.")

    _revisar_longitud(limpio, ["nombre", "apellido_paterno", "apellido_materno",
                               "calle_numero", "colonia", "ciudad"], errores)

    limpio["acepta_aviso_privacidad"] = a_bool(datos.get("acepta_aviso_privacidad", False))
    if not limpio["acepta_aviso_privacidad"]:
        errores.append("Debe aceptar el aviso de privacidad para poder guardar sus datos.")
    return limpio, errores
