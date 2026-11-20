from datetime import date

from conftest import libro_ejemplo, persona_ejemplo
from validaciones import (calcular_edad, isbn_valido, normalizar_texto, validar_libro,
                          validar_persona)


def test_isbn_13_y_10_con_digito_de_control():
    assert isbn_valido("978-84-376-0494-7")
    assert isbn_valido("0-306-40615-2")
    assert isbn_valido("080442957X")
    assert not isbn_valido("978-84-376-0494-8")
    assert not isbn_valido("12345")


def test_libro_valido_convierte_tipos():
    limpio, errores = validar_libro({**libro_ejemplo(), "anio": "2011", "paginas": "300",
                                     "calificacion": "4.5", "disponible": "True"})
    assert errores == []
    assert limpio["anio"] == 2011 and isinstance(limpio["paginas"], int)
    assert limpio["calificacion"] == 4.5 and limpio["disponible"] is True


def test_libro_todos_los_campos_obligatorios():
    _, errores = validar_libro({"id": "x1"})
    texto = " ".join(errores)
    for campo in ("sinopsis", "isbn", "titulo", "autor", "editorial", "genero", "tema"):
        assert campo in texto


def test_libro_rangos_y_formatos():
    _, errores = validar_libro(libro_ejemplo(calificacion=7, paginas=0, pasta="cartón",
                                             idioma="español", id="mal id"))
    assert len(errores) == 5


def test_persona_valida_y_reglas():
    limpio, errores = validar_persona(persona_ejemplo(telefono="55 1234-5678", correo="ANA@MAIL.COM"))
    assert errores == []
    assert limpio["telefono"] == "5512345678" and limpio["correo"] == "ana@mail.com"


def test_persona_requiere_aviso_y_formatos():
    _, errores = validar_persona(persona_ejemplo(acepta_aviso_privacidad=False, correo="sin-arroba",
                                                 telefono="123", codigo_postal="1234",
                                                 estado="Texas", fecha_nacimiento="14/05/2002"))
    assert len(errores) == 6


def test_apellido_materno_opcional():
    _, errores = validar_persona(persona_ejemplo(apellido_materno=""))
    assert errores == []


def test_edad_derivada():
    hoy = date.today()
    assert calcular_edad(f"{hoy.year - 20}-01-01") in (19, 20)


def test_normalizar_texto():
    assert normalizar_texto("  Gabriel GARCÍA Márquez ") == "gabriel garcia marquez"
