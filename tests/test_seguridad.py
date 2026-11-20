import pytest
from cryptography.fernet import Fernet

import seguridad
from seguridad import Cifrador, ErrorCifrado, ErrorLlave


def test_cifrado_ida_y_vuelta(cifrador):
    token = cifrador.cifrar("Ana López", "persona:P0001:nombre")
    assert token.startswith("v2:") and "Ana" not in token
    assert cifrador.descifrar(token, "persona:P0001:nombre") == "Ana López"


def test_nonce_distinto_en_cada_cifrado(cifrador):
    assert cifrador.cifrar("x", "c") != cifrador.cifrar("x", "c")


def test_contexto_distinto_impide_intercambiar_campos(cifrador):
    token = cifrador.cifrar("5512345678", "persona:P0001:telefono")
    with pytest.raises(ErrorCifrado):
        cifrador.descifrar(token, "persona:P0002:telefono")


def test_dato_alterado_se_detecta(cifrador):
    token = cifrador.cifrar("dato", "c")
    alterado = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    with pytest.raises(ErrorCifrado):
        cifrador.descifrar(alterado, "c")


def test_llave_incorrecta_no_descifra(cifrador):
    token = cifrador.cifrar("dato", "c")
    with pytest.raises(ErrorCifrado):
        Cifrador(llave_maestra=b"z" * 32).descifrar(token, "c")


def test_lectura_de_datos_heredados_fernet():
    llave_legada = Fernet.generate_key()
    token_viejo = Fernet(llave_legada).encrypt("Juan".encode()).decode()
    cifrador = Cifrador(llave_maestra=b"k" * 32, llave_legada=llave_legada)
    assert cifrador.es_heredado(token_viejo)
    assert cifrador.descifrar(token_viejo, "cualquier") == "Juan"


def test_indice_ciego_determinista_y_sin_texto(cifrador):
    h1 = cifrador.hash_indice(" Ana@Mail.com ")
    assert h1 == cifrador.hash_indice("ana@mail.com")
    assert "ana" not in h1 and len(h1) == 64


def test_contrasena_scrypt():
    almacenado = seguridad.hash_contrasena("Una-Clave-Segura")
    assert almacenado.startswith("scrypt$")
    assert seguridad.verificar_contrasena("Una-Clave-Segura", almacenado)
    assert not seguridad.verificar_contrasena("otra", almacenado)
    assert not seguridad.verificar_contrasena("x", "basura")


def test_llave_de_entorno_invalida(monkeypatch):
    monkeypatch.setenv("BIBLIOTECA_AES_KEY", "corta")
    with pytest.raises(ErrorLlave):
        seguridad.cargar_llave_maestra()


def test_llave_se_crea_en_archivo_de_secretos(tmp_path, monkeypatch):
    import config
    monkeypatch.delenv("BIBLIOTECA_AES_KEY", raising=False)
    monkeypatch.setattr(config, "ARCHIVO_LLAVE_AES", tmp_path / "secrets" / "aes.key")
    llave = seguridad.cargar_llave_maestra()
    assert len(llave) == 32
    assert seguridad.cargar_llave_maestra() == llave


def test_enmascarar():
    assert seguridad.enmascarar_correo("ana.lopez@mail.com") == "an***@mail.com"
    assert seguridad.enmascarar_telefono("5512345678") == "******5678"
