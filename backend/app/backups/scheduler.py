"""Frecuencia de copias automáticas mientras corre el backend.

``tick`` contiene toda la lógica y no usa hilos: las pruebas la llaman directamente
con un reloj controlado. ``start`` solo arranca un hilo que llama a ``tick`` cada
``CHECK_SECONDS``. Una copia fallida cuenta como intento: se reintenta tras el
intervalo, no en bucle.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import datetime, timedelta

from app.backups.files import Clock
from app.backups.service import BackupOutcome

CHECK_SECONDS = 60.0
logger = logging.getLogger("novel_engine.backups")


class BackupScheduler:
    def __init__(
        self,
        run: Callable[[], BackupOutcome],
        interval: timedelta,
        clock: Clock,
    ) -> None:
        self._run = run
        self._interval = interval
        self._clock = clock
        self._last_attempt: datetime | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def tick(self) -> BackupOutcome | None:
        """Ejecuta una copia si toca. Devuelve ``None`` si aún no toca."""
        now = self._clock()
        if self._last_attempt is not None and now - self._last_attempt < self._interval:
            return None
        self._last_attempt = now
        return self._run()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, name="novel-engine-backups", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=10)
            self._thread = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as error:  # El planificador no debe morir por un fallo inesperado.
                logger.error("planificador de copias: error inesperado (%s)", type(error).__name__)
            self._stop.wait(CHECK_SECONDS)
