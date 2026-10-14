"""Integración con el arranque del backend: marcador de ejecución y copias automáticas."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from app.backups import files
from app.backups.scheduler import BackupScheduler
from app.backups.service import BackupService
from app.backups.verify import sqlite_path
from app.config import Settings


def start_background(settings: Settings, clock: files.Clock) -> BackupScheduler | None:
    """Marca el backend como en marcha y arranca las copias automáticas si están activas.

    No hace nada si ``backup_dir`` no está configurado o la base no es un archivo SQLite.
    """
    if settings.backup_dir is None:
        return None
    source = sqlite_path(settings.database_url)
    if source is None:
        return None
    directory = Path(settings.backup_dir)
    files.write_marker(directory, clock)
    if settings.backup_interval_minutes <= 0:
        return None
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
    return scheduler


def stop_background(settings: Settings, scheduler: BackupScheduler | None) -> None:
    if scheduler is not None:
        scheduler.stop()
    if settings.backup_dir is not None:
        files.remove_marker(Path(settings.backup_dir))
