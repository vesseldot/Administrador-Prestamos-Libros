import time

import pytest

from conftest import libro_ejemplo, persona_ejemplo

tk = pytest.importorskip("tkinter")


def _hay_pantalla():
    try:
        raiz = tk.Tk()
        raiz.destroy()
        return True
    except tk.TclError:
        return False


pytestmark = pytest.mark.skipif(not _hay_pantalla(), reason="requiere entorno gráfico")


@pytest.fixture
def app(servicio, monkeypatch):
    import ui.vistas.libros as vista_libros
    import ui.vistas.personas as vista_personas
    import ui.vistas.prestamos as vista_prestamos
    from ui.app import AplicacionBiblioteca
    from ui.componentes import Formulario
    for modulo in (vista_libros, vista_personas, vista_prestamos):
        monkeypatch.setattr(modulo, "confirmar", lambda *a, **k: True, raising=False)
    for intento in range(3):
        try:
            aplicacion = AplicacionBiblioteca(servicio)
            break
        except tk.TclError:
            if intento == 2:
                raise
            time.sleep(1)
    errores = []
    aplicacion.manejar_error = errores.append
    aplicacion.errores = errores
    for hijo in aplicacion.winfo_children():
        if hijo.__class__.__name__ == "PantallaAcceso":
            hijo.destroy()
    aplicacion._al_entrar(primera_vez=True)
    esperar(aplicacion)
    aplicacion.Formulario = Formulario
    yield aplicacion
    esperar(aplicacion)
    aplicacion.tareas.cerrar(esperar=True)
    aplicacion.destroy()


def esperar(app, limite=20.0):
    inicio = time.monotonic()
    while True:
        app.update()
        if not app.tareas.ocupado:
            app.update()
            if not app.tareas.ocupado:
                return
        if time.monotonic() - inicio > limite:
            raise TimeoutError("La tarea en segundo plano no terminó")
        time.sleep(0.01)


def formularios(app):
    encontrados, pendientes = [], list(app.winfo_children())
    while pendientes:
        widget = pendientes.pop()
        if isinstance(widget, app.Formulario):
            encontrados.append(widget)
        pendientes.extend(widget.winfo_children())
    return encontrados


def test_navegacion_por_todas_las_secciones(app):
    for seccion in ("dashboard", "libros", "busqueda", "personas", "prestamos", "con_prestamo", "configuracion"):
        app.navegar(seccion)
        esperar(app)
    vista = app._vistas["configuracion"]
    for indice in range(4):
        vista.pestanas.select(indice)
        app.update()
        esperar(app)
    assert app.errores == []


def test_flujo_completo_desde_la_interfaz(app, servicio):
    app.navegar("libros")
    vista = app._vistas["libros"]
    vista.alta()
    app.update()
    formulario = formularios(app)[-1]
    for clave, valor in libro_ejemplo(1, titulo="El marciano", sinopsis="Un astronauta abandonado en Marte").items():
        widget, tipo = formulario.widgets[clave]
        if tipo == "texto":
            widget.insert("1.0", valor)
        elif tipo == "combo":
            widget.set(valor)
        elif tipo == "check":
            widget.variable.set(valor)
        else:
            widget.delete(0, "end")
            widget.insert(0, str(valor))
    formulario._guardar()
    esperar(app)
    assert servicio.catalogo.existe("libro01")
    assert not formularios(app)

    vista.alta()
    app.update()
    incompleto = formularios(app)[-1]
    incompleto._guardar()
    app.update()
    assert "obligatorio" in incompleto._errores.cget("text")
    incompleto.destroy()

    servicio.importar_lote([libro_ejemplo(n) for n in range(2, 6)])
    vista.refrescar()
    assert len(vista.tabla.filas) == 5
    vista.texto.insert(0, "Libro 3")
    vista._filtrar()
    assert [f["id"] for f in vista.tabla.filas] == ["libro03"]
    vista._limpiar()

    app.navegar("busqueda")
    busqueda = app._vistas["busqueda"]
    busqueda.consulta.insert(0, "astronauta marte")
    busqueda.buscar()
    esperar(app)
    assert busqueda.tabla.filas[0]["id"] == "libro01"

    persona_id = servicio.personas.registrar(persona_ejemplo())
    app.navegar("prestamos", persona_id=persona_id)
    prestamos = app._vistas["prestamos"]
    prestamos.tabla_disponibles.tree.selection_set(["libro01", "libro02"])
    app.update()
    prestamos.prestar()
    esperar(app)
    assert len(servicio.prestamos.activos_de(persona_id)) == 2
    assert len(prestamos.tabla_activos.filas) == 2

    app.navegar("con_prestamo")
    esperar(app)
    vista_con = app._vistas["con_prestamo"]
    assert vista_con.tabla.tree.exists(persona_id)
    vista_con.tabla.tree.selection_set(persona_id)
    vista_con.mostrar_contacto()
    assert vista_con.tabla.tree.set(persona_id, "telefono") == "5512345678"
    vista_con._ocultar()
    assert vista_con.tabla.tree.set(persona_id, "telefono") == "******5678"

    app.navegar("prestamos", persona_id=persona_id)
    primero = prestamos.tabla_activos.filas[0]["id"]
    prestamos.tabla_activos.tree.selection_set([primero])
    app.update()
    prestamos.devolver()
    esperar(app)
    assert len(servicio.prestamos.activos_de(persona_id)) == 1
    prestamos.devolver_todos()
    esperar(app)
    assert servicio.prestamos.activos_de(persona_id) == []
    assert len(servicio.prestamos.historial_de(persona_id)) == 2

    app.navegar("libros", seleccionar="libro05")
    esperar(app)
    vista.eliminar()
    esperar(app)
    assert not servicio.catalogo.existe("libro05") and servicio.indice.obtener("libro05") is None

    app.navegar("dashboard")
    esperar(app)
    tablero = app._vistas["dashboard"]
    assert tablero.indicadores["libros"]._valor.cget("text") == "4"
    assert tablero.tabla_actividad.filas
    assert app.errores == []


def test_bloqueo_de_sesion(app):
    app.bloquear()
    app.update()
    pantallas = [w for w in app.winfo_children() if w.__class__.__name__ == "PantallaAcceso"]
    assert pantallas and app._bloqueado
    app.navegar("personas")
    assert app._actual != "personas"
