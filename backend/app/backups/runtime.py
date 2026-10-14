"""Integración con el arranque del backend: marcador de ejecución y copias automáticas."""

from __future__ import annotations

import threading
from datetime import timedelta
from pathlib import Path

from app.backups import files
from app.backups.scheduler import BackupScheduler
from app.backups.service import BackupService
from app.backups.verify import sqlite_path
from app.config import Settings


class Heartbeat:
    """Renueva el latido del marcador mientras el backend corre."""

    def __init__(self, directory: Path, clock: files.Clock, every_seconds: float) -> None:
        self._directory = directory
        self._clock = clock
        self._every = every_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="novel-engine-heartbeat", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=10)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                files.beat(self._directory, self._clock)
            except OSError:
                pass  # Un fallo puntual de escritura no debe tumbar el backend; el latido se reintenta.
            self._stop.wait(self._every)


class Background:
    """Hilos de fondo del backend: latido y, si está activado, copias periódicas."""

    def __init__(self, heartbeat: Heartbeat, scheduler: BackupScheduler | None) -> None:
        self._heartbeat = heartbeat
        self._scheduler = scheduler

    def stop(self) -> None:
        if self._scheduler is not None:
            self._scheduler.stop()
        self._heartbeat.stop()


def start_background(settings: Settings, clock: files.Clock) -> Background | None:
    """Marca el backend como en marcha, con latido, y arranca las copias automáticas si están activas.

    No hace nada si ``backup_dir`` no está configurado o la base no es un archivo SQLite.
    """
    if settings.backup_dir is None:
        return None
    source = sqlite_path(settings.database_url)
    if source is None:
        return None
    directory = Path(settings.backup_dir)
    files.write_marker(directory, clock)
    heartbeat = Heartbeat(directory, clock, files.MARKER_HEARTBEAT_SECONDS)
    heartbeat.start()
    if settings.backup_interval_minutes <= 0:
        return Background(heartbeat, None)
    service = BackupService(
        source=source,
        directory=directory,
        clock=clock,
        keep=settings.backup_keep,
        min_keep=settings.backup_min_keep,
        max_age=timedelta(days=settings.backup_max_age_days),
    )
    scheduler = BackupScheduler(
        run=service.run,
        interval=timedelta(minutes=settings.backup_interval_minutes),
        clock=clock,
    )
    scheduler.start()
    return Background(heartbeat, scheduler)


def stop_background(settings: Settings, background: Background | None) -> None:
    """Para los hilos y retira el marcador: es el cierre limpio del propio backend."""
    if background is not None:
        background.stop()
    if settings.backup_dir is not None:
        files.remove_marker(Path(settings.backup_dir))
