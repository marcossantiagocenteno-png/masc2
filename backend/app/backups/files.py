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


# --- Marcador de ejecución -------------------------------------------------
#
# El backend escribe ``.app-running`` al arrancar y lo renueva cada
# ``MARKER_HEARTBEAT_SECONDS`` (latido). Al cerrar limpiamente lo retira. Tras un cierre
# brusco queda un marcador con latido caducado. La restauración solo lo considera
# abandonado si el latido caducó Y el sistema confirma que el proceso ya no existe.
# Si no puede confirmarlo (p. ej. Windows sin verificar), lo trata como desconocido.
# Ninguna operación borra el marcador salvo el cierre limpio del propio backend.

MARKER_HEARTBEAT_SECONDS = 30.0
MARKER_STALE_AFTER = timedelta(minutes=3)

ABSENT = "ausente"
ACTIVE = "activo"
ABANDONED = "abandonado"
UNKNOWN = "desconocido"


def _marker_path(directory: Path) -> Path:
    return directory / MARKER_NAME


def write_marker(directory: Path, clock: Clock) -> None:
    """Crea o renueva el marcador de este proceso."""
    directory.mkdir(parents=True, exist_ok=True)
    now = clock().isoformat()
    write_json_atomic(_marker_path(directory), {"pid": os.getpid(), "inicio": now, "latido": now})


def beat(directory: Path, clock: Clock) -> None:
    """Renueva el latido del marcador de este proceso. No crea marcadores ajenos."""
    data = read_marker(directory)
    if data is None or int(data.get("pid", -1)) != os.getpid():
        return
    data["latido"] = clock().isoformat()
    write_json_atomic(_marker_path(directory), data)


def remove_marker(directory: Path) -> None:
    """Retira el marcador. Solo lo llama el propio backend al cerrar limpiamente."""
    _marker_path(directory).unlink(missing_ok=True)


def read_marker(directory: Path) -> dict[str, Any] | None:
    try:
        return json.loads(_marker_path(directory).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def process_alive(pid: int) -> bool | None:
    """``True`` si el proceso existe, ``False`` si consta que no existe, ``None`` si no se puede saber."""
    if os.name == "nt":
        return _windows_process_alive(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # Existe, pero es de otro usuario.
    except OSError:
        return None
    return True


def _windows_process_alive(pid: int) -> bool | None:
    """Comprobación con la API de Windows. No se ha ejecutado en Windows en este entorno."""
    import ctypes
    from ctypes import wintypes

    error_invalid_parameter = 87
    still_active = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        if ctypes.get_last_error() == error_invalid_parameter:
            return False
        return None
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return None
        return code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


def classify_marker(
    directory: Path,
    clock: Clock,
    alive: Callable[[int], bool | None] = process_alive,
) -> tuple[str, str]:
    """Estado del marcador y explicación. Nunca modifica nada."""
    path = _marker_path(directory)
    if not path.exists():
        return ABSENT, "no hay marcador"
    data = read_marker(directory)
    if data is None:
        return UNKNOWN, "el marcador existe pero no se puede leer"
    try:
        pid = int(data["pid"])
        heartbeat = datetime.fromisoformat(data["latido"])
    except (KeyError, TypeError, ValueError):
        return UNKNOWN, "el marcador tiene un formato no reconocido"
    if clock() - heartbeat <= MARKER_STALE_AFTER:
        return ACTIVE, f"latido reciente (pid {pid})"
    verdict = alive(pid)
    if verdict is False:
        return ABANDONED, f"sin latido desde {heartbeat.isoformat(timespec='seconds')} y el proceso {pid} ya no existe"
    if verdict is True:
        return ACTIVE, f"sin latido reciente, pero el proceso {pid} sigue existiendo"
    return UNKNOWN, f"sin latido reciente y no se puede comprobar el proceso {pid} en este sistema"


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
