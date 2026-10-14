"""Creación de copias verificadas y rotación.

Orden de una copia:

1. Se copia la base activa con la API de backup de SQLite, en pasos, a un archivo temporal.
   Es una copia consistente aunque haya escrituras durante la operación.
2. Se verifica el temporal (integridad, esquema conocido, tablas).
3. Solo si es válido, se renombra a su nombre definitivo y se escribe su manifiesto.
4. Solo después de todo lo anterior, se rota. Una copia fallida no elimina nada.

Cualquier fallo queda en el registro operativo y el resultado nunca se informa como éxito.
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app import __version__
from app.backups import files
from app.backups.files import Clock, backup_name, list_backups, manifest_path, record, write_json_atomic
from app.backups.verify import SchemaOrder, Verification, file_sha256, schema_order, verify_sqlite

class BackupError(Exception):
    """La copia no se ha podido crear o verificar."""


@dataclass(frozen=True)
class BackupOutcome:
    """Resultado de una ejecución. ``status`` vale ``creada``, ``fallida`` u ``omitida``."""

    status: str
    message: str
    path: Path | None = None
    verification: Verification | None = None
    rotated: tuple[str, ...] = field(default_factory=tuple)


def copy_database(
    source: Path,
    target: Path,
    on_step: Callable[[], None] | None = None,
) -> None:
    """Copia ``source`` a ``target`` con la API de backup de SQLite.

    La copia se hace dentro de una lectura abierta: todo el contenido corresponde a
    una única instantánea, y las escrituras concurrentes esperan a que termine (la
    copia dura lo que tarda en leerse la base; para bases de decenas de MB, milisegundos).

    No se copia por pasos: el módulo ``sqlite3`` reintenta indefinidamente los errores
    ``BUSY`` de la API, y un escritor que retuviera el bloqueo dejaría la copia colgada.
    ``on_step`` se llama con la instantánea ya abierta (lo usan las pruebas de consistencia).
    """
    if not source.is_file():
        raise BackupError("la base de datos activa no existe")
    source_connection = sqlite3.connect(source, timeout=30, isolation_level=None)
    target_connection = sqlite3.connect(target)
    try:
        source_connection.execute("BEGIN")
        source_connection.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()
        if on_step is not None:
            on_step()
        source_connection.backup(target_connection)
        source_connection.execute("COMMIT")
    except BaseException:
        if source_connection.in_transaction:
            source_connection.execute("ROLLBACK")
        raise
    finally:
        target_connection.close()
        source_connection.close()


class BackupService:
    """Crea copias verificadas de ``source`` en ``directory`` y aplica la rotación."""

    def __init__(
        self,
        source: Path,
        directory: Path,
        clock: Clock,
        keep: int,
        min_keep: int,
        max_age: timedelta,
        on_step: Callable[[], None] | None = None,
        after_copy: Callable[[Path], None] | None = None,
        order: SchemaOrder | None = None,
    ) -> None:
        if not 1 <= min_keep <= keep:
            raise ValueError("se exige 1 <= min_keep <= keep")
        self._source = source
        self._directory = directory
        self._clock = clock
        self._keep = keep
        self._min_keep = min_keep
        self._max_age = max_age
        self._on_step = on_step
        self._after_copy = after_copy  # Gancho de prueba: permite estropear el temporal antes de verificarlo.
        self._order = order

    @property
    def directory(self) -> Path:
        return self._directory

    def run(self) -> BackupOutcome:
        """Ejecuta una copia completa. Nunca lanza excepción: devuelve el resultado."""
        lock = files.BackupLock(self._directory, self._clock)
        if not lock.acquire():
            record(self._directory, self._clock, "omitida", motivo="ya hay una copia o restauración en curso")
            return BackupOutcome("omitida", "Ya hay una copia o una restauración en curso; no se ejecuta otra.")

        temporary: Path | None = None
        try:
            now = self._clock()
            order = self._order or schema_order()
            record(self._directory, self._clock, "inicio", origen=self._source.name)
            self._directory.mkdir(parents=True, exist_ok=True)

            temporary = self._directory / f".tmp-{uuid.uuid4().hex}.sqlite"
            copy_database(self._source, temporary, on_step=self._on_step)
            if self._after_copy is not None:
                self._after_copy(temporary)
            check = verify_sqlite(temporary, order)
            if not check.ok:
                raise BackupError("la copia no supera la verificación: " + "; ".join(check.problems))

            target = files.free_path(self._directory, now)
            os.replace(temporary, target)
            temporary = None
            final = verify_sqlite(target, order)
            if not final.ok:
                target.unlink(missing_ok=True)
                raise BackupError("el archivo final no supera la verificación: " + "; ".join(final.problems))

            self._write_manifest(target, now, final)
            record(
                self._directory,
                self._clock,
                "correcta",
                archivo=target.name,
                sha256=final.sha256,
                revision=final.revision,
                estado_esquema=final.schema_status,
                tablas=final.counts,
            )
        except Exception as error:  # Cualquier fallo se registra y se informa como fallo.
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            message = str(error) or type(error).__name__
            record(
                self._directory,
                self._clock,
                "fallida",
                level=40,  # logging.ERROR
                error=type(error).__name__,
                detalle=message[:300],
            )
            return BackupOutcome("fallida", f"La copia ha fallado: {message}")
        finally:
            lock.release()

        rotated: tuple[str, ...] = ()
        try:
            rotated = self.rotate(now)
        except OSError as error:
            # La copia nueva es válida: el fallo de rotación no la invalida, pero se registra.
            record(self._directory, self._clock, "rotacion_fallida", level=40, error=type(error).__name__)
        return BackupOutcome("creada", f"Copia creada: {target.name}", target, final, rotated)

    def rotate(self, now: datetime) -> tuple[str, ...]:
        """Borra copias antiguas: más allá de ``keep``, o más antiguas que ``max_age`` si quedan más de ``min_keep``.

        Solo se llama tras crear una copia válida. Nunca toca las copias preventivas.
        """
        removed: list[str] = []
        for index, path in enumerate(list_backups(self._directory)):
            created = files.parse_name(path.name)
            too_many = index >= self._keep
            too_old = index >= self._min_keep and created is not None and now - created > self._max_age
            if not (too_many or too_old):
                continue
            path.unlink()
            manifest_path(path).unlink(missing_ok=True)
            removed.append(path.name)
        if removed:
            record(self._directory, self._clock, "rotada", eliminadas=removed)
        return tuple(removed)

    def _write_manifest(self, target: Path, now: datetime, verification: Verification) -> None:
        data: dict[str, Any] = {
            "creada": now.isoformat(timespec="seconds"),
            "archivo": target.name,
            "sha256": verification.sha256,
            "tamano_bytes": verification.size_bytes,
            "revision_esquema": verification.revision,
            "estado_esquema": verification.schema_status,
            "tablas": verification.counts,
            "integridad": "ok",
            "version_app": __version__,
        }
        write_json_atomic(manifest_path(target), data)
