"""Restauración administrativa de una copia sobre la base activa.

Esto no se ejecuta desde la interfaz. Es un procedimiento de línea de comandos que
requiere la aplicación detenida. Orden de operaciones:

1. Rechazar si el marcador ``.app-running`` existe (el backend parece en marcha).
2. Tomar el bloqueo de la carpeta de copias.
3. Verificar la copia de origen: integridad, esquema conocido, hash del manifiesto.
   Una copia de esquema anterior exige ``allow_older_schema``. No se migra nada.
4. Tomar un bloqueo exclusivo sobre la base activa. Si otro proceso la usa, rechazar.
5. Guardar una copia preventiva de la base activa y verificarla. Si no se puede, rechazar.
6. Crear un temporal desde la copia y verificarlo (integridad y conteos).
7. Liberar el bloqueo, reemplazar la base activa con el temporal, y verificarla.
8. Si la verificación posterior falla, restaurar la copia preventiva. El resultado es ``revertida``.

Antes del paso 7 no se ha cambiado nada: cualquier rechazo deja la base activa intacta.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import uuid
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from app.backups import files
from app.backups.files import BackupLock, Clock, read_manifest, record
from app.backups.verify import SchemaOrder, Verification, read_only_connection, schema_order, verify_sqlite


@dataclass(frozen=True)
class RestoreOutcome:
    """``restaurada``, ``rechazada`` (la base activa no se ha tocado) o ``revertida`` (se ha vuelto a la preventiva)."""

    status: str
    message: str
    preventive: Path | None = None
    schema_status: str | None = None


def _exclusive_connection(path: Path) -> sqlite3.Connection | None:
    """Bloqueo exclusivo de escritura y lectura. ``None`` si otro proceso usa la base."""
    connection = sqlite3.connect(path, timeout=0, isolation_level=None)
    try:
        connection.execute("BEGIN EXCLUSIVE")
    except sqlite3.OperationalError:
        connection.close()
        return None
    return connection


def _replace_with_file(source: Path, destination: Path) -> None:
    """Sustituye ``destination`` por una copia byte a byte de ``source``, de forma atómica."""
    temporary = destination.with_name(f".revert-{uuid.uuid4().hex}.sqlite")
    shutil.copyfile(source, temporary)
    os.replace(temporary, destination)


def restore_backup(
    active: Path,
    directory: Path,
    backup: Path,
    clock: Clock,
    allow_older_schema: bool = False,
    ignore_running_marker: bool = False,
    after_replace: Callable[[Path], None] | None = None,
    order: SchemaOrder | None = None,
) -> RestoreOutcome:
    """Restaura ``backup`` sobre ``active``. Nunca lanza excepción: devuelve el resultado.

    ``after_replace`` es un gancho de prueba que se ejecuta justo después de reemplazar
    la base activa, para simular una restauración que no supera la verificación.
    """

    def refuse(reason: str) -> RestoreOutcome:
        record(directory, clock, "restauracion_rechazada", level=30, motivo=reason)
        return RestoreOutcome("rechazada", reason)

    if not ignore_running_marker and files.marker_present(directory):
        return refuse("el backend parece estar en marcha (marcador .app-running). Deténlo antes de restaurar.")

    lock = BackupLock(directory, clock)
    if not lock.acquire():
        return refuse("ya hay una copia o una restauración en curso")

    locked: sqlite3.Connection | None = None
    preventive: Path | None = None
    temporary: Path | None = None
    replaced = False
    try:
        order = order or schema_order()
        source = verify_sqlite(backup, order)
        if not source.ok:
            return refuse("la copia no supera la verificación: " + "; ".join(source.problems))
        if source.schema_status == "anterior" and not allow_older_schema:
            return refuse(
                f"la copia es de una versión de esquema anterior ({source.revision}). "
                "Repite con --permitir-esquema-anterior y ejecuta después «alembic upgrade head»."
            )
        manifest = read_manifest(backup)
        if manifest is not None and manifest.get("sha256") != source.sha256:
            return refuse("el hash de la copia no coincide con su manifiesto: el archivo ha cambiado")

        record(directory, clock, "restauracion_inicio", archivo=backup.name, sha256=source.sha256)
        now = clock()
        if active.exists():
            locked = _exclusive_connection(active)
            if locked is None:
                return refuse("la base activa está en uso por otro proceso")
            preventive = files.free_path(directory, now, preventive=True)
            # Con el bloqueo exclusivo no hay escritores ni diario pendiente: el archivo es consistente
            # y basta una copia de bytes. No se usa la API de backup desde esta conexión (ver service.py).
            shutil.copyfile(active, preventive)
            saved = verify_sqlite(preventive, order)
            if not saved.ok:
                preventive.unlink(missing_ok=True)
                return refuse("no se pudo guardar la copia preventiva: " + "; ".join(saved.problems))
            record(directory, clock, "preventiva_creada", archivo=preventive.name, sha256=saved.sha256)
            locked.execute("ROLLBACK")
            locked.close()
            locked = None

        if active.with_name(active.name + "-journal").exists():
            return refuse("hay un diario de transacción pendiente junto a la base activa; no se restaura")

        temporary = active.parent / f".restore-{uuid.uuid4().hex}.sqlite"
        with closing(read_only_connection(backup)) as origin, closing(sqlite3.connect(temporary)) as destination:
            origin.backup(destination)
        prepared = verify_sqlite(temporary, order)
        if not prepared.ok or prepared.counts != source.counts:
            return refuse("el temporal de restauración no coincide con la copia de origen")

        os.replace(temporary, active)
        temporary = None
        replaced = True
        if after_replace is not None:
            after_replace(active)
        final = verify_sqlite(active, order)
        if not final.ok or final.counts != source.counts:
            return _revert(active, preventive, directory, clock, order, final)

        record(
            directory,
            clock,
            "restauracion_correcta",
            archivo=backup.name,
            estado_esquema=final.schema_status,
            revision=final.revision,
            tablas=final.counts,
            preventiva=preventive.name if preventive else None,
        )
        return RestoreOutcome(
            "restaurada",
            f"Restaurada la copia {backup.name}. Si su esquema es anterior, ejecuta «alembic upgrade head».",
            preventive=preventive,
            schema_status=final.schema_status,
        )
    except Exception as error:
        message = str(error) or type(error).__name__
        record(directory, clock, "restauracion_fallida", level=40, error=type(error).__name__, detalle=message[:300])
        if replaced:
            return _revert(active, preventive, directory, clock, order or schema_order(), None)
        return RestoreOutcome("rechazada", f"La restauración no se ha completado: {message}", preventive)
    finally:
        if locked is not None:
            locked.close()
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        lock.release()


def _revert(
    active: Path,
    preventive: Path | None,
    directory: Path,
    clock: Clock,
    order: SchemaOrder,
    failed: Verification | None,
) -> RestoreOutcome:
    """Devuelve la base activa a su estado previo a la restauración."""
    reason = "la base restaurada no supera la verificación" if failed is None else (
        "la base restaurada no supera la verificación: " + "; ".join(failed.problems or ("conteos distintos",))
    )
    if preventive is None:
        active.unlink(missing_ok=True)  # No había base previa: lo restaurado es lo único que se ha creado.
        record(directory, clock, "restauracion_revertida", level=40, motivo=reason, preventiva=None)
        return RestoreOutcome("revertida", reason + ". No había base previa; el archivo restaurado se ha retirado.")
    _replace_with_file(preventive, active)
    restored = verify_sqlite(active, order)
    record(
        directory,
        clock,
        "restauracion_revertida",
        level=40,
        motivo=reason,
        preventiva=preventive.name,
        verificada=restored.ok,
    )
    if not restored.ok:
        return RestoreOutcome(
            "revertida",
            reason + ". La reversión tampoco verifica: la copia preventiva está en " + preventive.name,
            preventive,
        )
    return RestoreOutcome("revertida", reason + ". La base activa se ha devuelto a su estado anterior.", preventive)
