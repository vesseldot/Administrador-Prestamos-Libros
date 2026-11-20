"""Ejecución de trabajo pesado fuera del hilo de la interfaz.

Todas las tareas se ejecutan en un único hilo trabajador, en orden, de modo que
ChromaDB y el modelo de embeddings nunca se usan desde dos hilos a la vez. Los
resultados se entregan al hilo de Tkinter mediante una cola revisada con `after`.
"""
import logging
import queue
import threading
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger("biblioteca")


class GestorTareas:
    def __init__(self, raiz, al_cambiar_estado=None, manejar_error=None, intervalo_ms: int = 40):
        self.raiz = raiz
        self._cola: queue.Queue = queue.Queue()
        self._ejecutor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tareas")
        self._pendientes = 0
        self._al_cambiar_estado = al_cambiar_estado or (lambda pendientes, mensaje: None)
        self._manejar_error = manejar_error or (lambda error: log.error("Tarea fallida: %s", error))
        self._intervalo = intervalo_ms
        self._cerrado = False
        self.raiz.after(self._intervalo, self._revisar)

    @property
    def ocupado(self) -> bool:
        return self._pendientes > 0

    def ejecutar(self, trabajo, al_terminar=None, al_error=None, mensaje: str = "Procesando…",
                 independiente: bool = False):
        """Ejecuta `trabajo()` en segundo plano y llama a `al_terminar(resultado)` en la interfaz.

        Con `independiente=True` usa un hilo propio (para descargas largas que no deben
        bloquear la cola de trabajo de Chroma y del modelo).
        """
        if self._cerrado:
            return
        self._pendientes += 1
        self._al_cambiar_estado(self._pendientes, mensaje)

        def envoltura():
            try:
                self._cola.put(("fin", al_terminar, trabajo(), None, al_error))
            except Exception as error:  # noqa: BLE001
                log.exception("Error en tarea en segundo plano (%s)", type(error).__name__)
                self._cola.put(("fin", al_terminar, None, error, al_error))

        if independiente:
            threading.Thread(target=envoltura, name="tarea-independiente", daemon=True).start()
        else:
            self._ejecutor.submit(envoltura)

    def en_interfaz(self, funcion, *argumentos):
        """Programa una llamada en el hilo de la interfaz desde el hilo trabajador."""
        self._cola.put(("llamada", funcion, argumentos, None, None))

    def progreso(self, funcion):
        """Envuelve un callback de progreso para que se ejecute en la interfaz."""
        return lambda *argumentos: self.en_interfaz(funcion, *argumentos)

    def _revisar(self):
        try:
            while True:
                tipo, funcion, valor, error, al_error = self._cola.get_nowait()
                if tipo == "llamada":
                    self._llamar(funcion, *valor)
                    continue
                self._pendientes = max(self._pendientes - 1, 0)
                self._al_cambiar_estado(self._pendientes, "")
                if error is not None:
                    self._llamar(al_error or self._manejar_error, error)
                elif funcion:
                    self._llamar(funcion, valor)
        except queue.Empty:
            pass
        finally:
            if not self._cerrado:
                self.raiz.after(self._intervalo, self._revisar)

    def _llamar(self, funcion, *argumentos):
        try:
            funcion(*argumentos)
        except Exception as error:  # noqa: BLE001
            log.exception("Error al actualizar la interfaz (%s)", type(error).__name__)
            if funcion is not self._manejar_error:
                self._manejar_error(error)

    def cerrar(self, esperar: bool = False):
        """Cancela las tareas pendientes; con `esperar=True` espera a que termine la que está en curso."""
        self._cerrado = True
        self._ejecutor.shutdown(wait=esperar, cancel_futures=True)
