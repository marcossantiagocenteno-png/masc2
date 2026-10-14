"""Nombres de archivo, manifiestos, bloqueo, marcador de ejecución y registro operativo.

El registro nunca contiene texto de manuscritos, comentarios ni claves: solo
eventos, nombres de archivo, recuentos, hashes y tipos de error.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

Clock = Callable[[], datetime]

COPY_PREFIX = "novel_engine-"
PREVENTIVE_PREFIX = "preventiva-"
LOCK_NAME = ".backup.lock"
LOG_NAME = "operaciones.jsonl"
MARKER_NAME = ".app-running"
STALE_LOCK_AFTER = timedelta(hours=2)

_NAME_RE = re.compile(r"^(novel_engine|preventiva)-(\d{8}T\d{12})Z\.sqlite$")
logger = logging.getLogger("novel_engine.backups")


def utc_clock() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def stamp(now: datetime) -> str:
    return now.strftime("%Y%m%dT%H%M%S") + f"{now.microsecond:06d}"


def backup_name(now: datetime, preventive: bool = False) -> str:
    prefix = PREVENTIVE_PREFIX if preventive else COPY_PREFIX
    return f"{prefix}{stamp(now)}Z.sqlite"


def free_path(directory: Path, now: datetime, preventive: bool = False) -> Path:
    """Nombre libre para una copia nueva. Si ya existe uno con esa marca, avanza un microsegundo.

    Nunca se sobrescribe una copia existente: dos copias en el mismo instante no pueden
    compartir nombre.
    """
    moment = now
    while True:
        path = directory / backup_name(moment, preventive=preventive)
        if not path.exists():
            return path
        moment += timedelta(microseconds=1)


def manifest_path(backup: Path) -> Path:
    return backup.with_suffix(".json")


def parse_name(name: str) -> datetime | None:
    match = _NAME_RE.match(name)
    if match is None:
        return None
    return datetime.strptime(match.group(2), "%Y%m%dT%H%M%S%f")


def list_backups(directory: Path, preventive: bool = False) -> list[Path]:
    """Copias del tipo pedido, de la más reciente a la más antigua. Ignora cualquier otro archivo."""
    if not directory.is_dir():
        return []
    wanted = PREVENTIVE_PREFIX if preventive else COPY_PREFIX
    found: list[tuple[datetime, Path]] = []
    for path in directory.iterdir():
        if not path.name.startswith(wanted):
            continue
        created = parse_name(path.name)
        if created is not None and path.is_file():
            found.append((created, path))
    found.sort(key=lambda item: item[0], reverse=True)
    return [path for _, path in found]


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def read_manifest(backup: Path) -> dict[str, Any] | None:
    path = manifest_path(backup)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


class BackupLock:
    """Bloqueo de la carpeta de copias. Impide dos copias o una copia y una restauración a la vez.

    Usa creación exclusiva de archivo, que funciona igual en Linux y en Windows. Un
    bloqueo más antiguo que ``STALE_LOCK_AFTER`` se considera abandonado y se retira.
    """

    def __init__(self, directory: Path, clock: Clock, stale_after: timedelta = STALE_LOCK_AFTER) -> None:
        self._path = directory / LOCK_NAME
        self._clock = clock
        self._stale_after = stale_after
        self._held = False

    def acquire(self) -> bool:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._create():
            return True
        if self._is_stale():
            record(self._path.parent, self._clock, "bloqueo_obsoleto_retirado")
            self._path.unlink(missing_ok=True)
            return self._create()
        return False

    def release(self) -> None:
        if self._held:
            self._path.unlink(missing_ok=True)
            self._held = False

    def _create(self) -> bool:
        try:
            descriptor = os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"pid": os.getpid(), "desde": self._clock().isoformat()}, handle)
        self._held = True
        return True

    def _is_stale(self) -> bool:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            since = datetime.fromisoformat(data["desde"])
        except (OSError, ValueError, KeyError, TypeError):
            return True
        return self._clock() - since > self._stale_after


def write_marker(directory: Path, clock: Clock) -> None:
    """Marca que el backend está en marcha. La restauración se niega mientras exista."""
    directory.mkdir(parents=True, exist_ok=True)
    write_json_atomic(directory / MARKER_NAME, {"pid": os.getpid(), "desde": clock().isoformat()})


def remove_marker(directory: Path) -> None:
    (directory / MARKER_NAME).unlink(missing_ok=True)


def marker_present(directory: Path) -> bool:
    return (directory / MARKER_NAME).exists()


def record(directory: Path, clock: Clock, event: str, level: int = logging.INFO, **fields: Any) -> None:
    """Añade una línea al registro operativo y la emite por logging."""
    directory.mkdir(parents=True, exist_ok=True)
    line = {"ts": clock().isoformat(timespec="seconds"), "evento": event, **fields}
    with (directory / LOG_NAME).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(line, ensure_ascii=False) + "\n")
    logger.log(level, "%s %s", event, json.dumps(fields, ensure_ascii=False))


def read_log(directory: Path, limit: int = 50) -> list[dict[str, Any]]:
    path = directory / LOG_NAME
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines[-limit:]]
