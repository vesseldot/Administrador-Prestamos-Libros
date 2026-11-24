"""Animaciones y fondos de la interfaz: terminan en el valor correcto y no bloquean la ventana."""
import time

import pytest

tk = pytest.importorskip("tkinter")


def _raiz():
    """Crea la ventana; en Windows Tk falla a veces de forma transitoria, así que se reintenta."""
    for intento in range(3):
        try:
            return tk.Tk()
        except tk.TclError:
            if intento < 2:
                time.sleep(1)
    pytest.skip("requiere entorno gráfico")


def _bombear(raiz, segundos):
    fin = time.monotonic() + segundos
    while time.monotonic() < fin:
        raiz.update()
        time.sleep(0.005)


def test_mezclar_y_suavizar():
    from ui.fondos import mezclar, suavizar
    assert mezclar("#000000", "#FFFFFF", 0) == "#000000"
    assert mezclar("#000000", "#FFFFFF", 1) == "#FFFFFF"
    assert mezclar("#000000", "#FFFFFF", 0.5) == "#808080"
    assert suavizar(0) == 0 and suavizar(1) == 1 and 0 < suavizar(0.5) < 1


def test_animacion_llega_al_final_y_no_bloquea(monkeypatch):
    from ui import fondos, tema
    monkeypatch.setattr(tema, "ANIMACIONES", True)
    raiz = _raiz()
    try:
        pasos, fin = [], []
        fondos.Animacion(raiz, 120, pasos.append, fin=lambda: fin.append(True))
        # Mientras anima, la ventana sigue atendiendo eventos (after programado desde fuera).
        atendido = []
        raiz.after(10, lambda: atendido.append(True))
        _bombear(raiz, 0.4)
        assert fin == [True] and pasos[-1] == 1.0 and len(pasos) > 2
        assert atendido == [True]
    finally:
        raiz.destroy()


def test_animacion_se_puede_cancelar(monkeypatch):
    from ui import fondos, tema
    monkeypatch.setattr(tema, "ANIMACIONES", True)
    raiz = _raiz()
    try:
        pasos = []
        animacion = fondos.Animacion(raiz, 300, pasos.append)
        animacion.cancelar()
        cantidad = len(pasos)
        _bombear(raiz, 0.2)
        assert len(pasos) == cantidad
    finally:
        raiz.destroy()


def test_sin_animaciones_aplica_el_estado_final(monkeypatch):
    from ui import fondos, tema
    monkeypatch.setattr(tema, "ANIMACIONES", False)
    raiz = _raiz()
    try:
        pasos = []
        fondos.Animacion(raiz, 500, pasos.append)
        assert pasos == [1.0]
    finally:
        raiz.destroy()


def test_contador_del_indicador_termina_en_su_valor(monkeypatch):
    from ui import componentes, tema
    monkeypatch.setattr(tema, "ANIMACIONES", True)
    raiz = _raiz()
    try:
        tema.aplicar_tema(raiz)
        indicador = componentes.Indicador(raiz, "Libros", "libros")
        indicador.pack(fill="x")
        indicador.actualizar(200, "detalle", 0.5)
        _bombear(raiz, 1.1)
        assert indicador._valor.cget("text") == "200"
        indicador.actualizar(7, "detalle")
        _bombear(raiz, 1.1)
        assert indicador._valor.cget("text") == "7"
        assert not indicador._barra.winfo_manager()
    finally:
        raiz.destroy()


def test_banda_y_escena_se_dibujan_sin_errores():
    from ui import fondos, tema
    raiz = _raiz()
    try:
        tema.aplicar_tema(raiz)
        raiz.geometry("1000x700")
        banda = fondos.BandaTitulo(raiz, "Libros", "Subtítulo de prueba")
        banda.pack(fill="x")
        escena = fondos.EscenaNocturna(raiz, "Biblioteca", ["Una línea.", "Otra línea."])
        escena.pack(fill="both", expand=True)
        _bombear(raiz, 0.3)
        banda.revelar()
        assert banda.find_withtag("texto") and escena.find_withtag("escena")
        _bombear(raiz, 0.3)
        escena.destroy()
        _bombear(raiz, 0.2)
    finally:
        raiz.destroy()
