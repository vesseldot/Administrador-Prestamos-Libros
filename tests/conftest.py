import os
import sys
from pathlib import Path

# Las pruebas leen valores finales de la interfaz: sin animaciones el resultado es inmediato y determinista.
os.environ.setdefault("BIBLIOTECA_SIN_ANIMACIONES", "1")

import chromadb
import fakeredis
import pytest
from chromadb.config import Settings

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db_libros import GestorLibros  # noqa: E402
from db_redis import Llaves  # noqa: E402
from modelo_simulado import fabrica_simulada  # noqa: E402
from seguridad import Cifrador  # noqa: E402
from servicios import ServicioBiblioteca  # noqa: E402


@pytest.fixture(autouse=True)
def portadas_aisladas(tmp_path, monkeypatch):
    """Ninguna prueba escribe en la carpeta real de portadas ni consulta Open Library."""
    import config
    import portadas
    monkeypatch.setattr(config, "DIR_PORTADAS", tmp_path / "portadas")
    monkeypatch.setattr(portadas.ClienteOpenLibrary, "_abrir_url", lambda self, url: None)
    monkeypatch.setattr(portadas.ClienteOpenLibrary.__init__, "__defaults__", (0, 20, None))


@pytest.fixture
def redis_falso():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def cifrador():
    return Cifrador(llave_maestra=b"k" * 32)


@pytest.fixture
def indice(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "ARCHIVO_MODELO_ACTIVO", tmp_path / "modelo_activo.txt")
    cliente = chromadb.PersistentClient(path=str(tmp_path / "chroma"),
                                        settings=Settings(anonymized_telemetry=False))
    return GestorLibros(clave_modelo="paraphrase-multilingual-MiniLM-L12-v2",
                        fabrica_modelo=fabrica_simulada, cliente=cliente)


@pytest.fixture
def servicio(redis_falso, indice, cifrador):
    return ServicioBiblioteca.crear(r=redis_falso, indice=indice, cifrador=cifrador,
                                    llaves=Llaves("test:"))


def libro_ejemplo(numero=1, **cambios):
    datos = {
        "id": f"libro{numero:02d}", "sinopsis": f"Un astronauta queda solo en Marte numero {numero}",
        "isbn": isbn_valido(numero), "titulo": f"Libro {numero}", "autor": "Autora Prueba",
        "anio": 2011, "editorial": "Editorial", "genero": "ciencia ficcion", "tema": "marte",
        "idioma": "es", "pasta": "blanda", "paginas": 300, "calificacion": 4.5, "disponible": True,
    }
    datos.update(cambios)
    return datos


def isbn_valido(numero: int) -> str:
    from validaciones import digito_control_isbn13
    base = f"978000{numero:06d}"
    return base + digito_control_isbn13(base)


def persona_ejemplo(**cambios):
    datos = {
        "nombre": "Ana", "apellido_paterno": "López", "apellido_materno": "Ruiz",
        "fecha_nacimiento": "2002-05-14", "genero": "Femenino", "correo": "ana.lopez@mail.com",
        "telefono": "5512345678", "calle_numero": "Av. Juárez 10", "colonia": "Centro",
        "ciudad": "Puebla", "estado": "Puebla", "codigo_postal": "72000",
        "ocupacion": "Estudiante", "tipo_usuario": "Alumno", "acepta_aviso_privacidad": True,
    }
    datos.update(cambios)
    return datos
