"""Marcador de ejecución: latido, distinción entre marcador activo y abandonado, y restauración.

Las pruebas controlan el reloj y el comportamiento de «¿existe el proceso?» mediante
inyección, salvo una que comprueba un PID real de un proceso que ya ha terminado.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

from app.backups import files
from app.backups.restore import restore_backup
from app.backups.service import BackupService
from app.config import Settings
from tests.backup_fakes import FakeClock, populate, sha


def _live(settings: Settings) -> Path:
    return Path(settings.database_url.removeprefix("sqlite:///"))


def _backup(settings: Settings, directory: Path, clock: FakeClock) -> Path:
    outcome = BackupService(
        source=_live(settings), directory=directory, clock=clock, keep=5, min_keep=1, max_age=timedelta(days=30)
    ).run()
    assert outcome.path is not None
    return outcome.path


def _write_marker_by_other(directory: Path, pid: int, heartbeat: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / files.MARKER_NAME).write_text(
        json.dumps({"pid": pid, "inicio": heartbeat, "latido": heartbeat}), encoding="utf-8"
    )


def test_el_latido_mantiene_el_marcador_activo(tmp_path: Path) -> None:
    clock = FakeClock()
    files.write_marker(tmp_path, clock)
    clock.advance(seconds=30)
    files.beat(tmp_path, clock)
    state, _ = files.classify_marker(tmp_path, clock, alive=lambda pid: None)
    assert state == files.ACTIVE
    assert files.read_marker(tmp_path)["latido"] == clock.now.isoformat()


def test_el_latido_no_adopta_marcadores_de_otro_proceso(tmp_path: Path) -> None:
    clock = FakeClock()
    _write_marker_by_other(tmp_path, pid=os.getpid() + 100000, heartbeat=clock.now.isoformat())
    before = (tmp_path / files.MARKER_NAME).read_text(encoding="utf-8")
    files.beat(tmp_path, clock)
    assert (tmp_path / files.MARKER_NAME).read_text(encoding="utf-8") == before


def test_marcador_sin_latido_y_proceso_inexistente_es_abandonado(tmp_path: Path) -> None:
    clock = FakeClock()
    _write_marker_by_other(tmp_path, pid=4242, heartbeat=clock.now.isoformat())
    clock.advance(minutes=10)
    state, explanation = files.classify_marker(tmp_path, clock, alive=lambda pid: False)
    assert state == files.ABANDONED
    assert "ya no existe" in explanation


def test_marcador_sin_latido_pero_con_proceso_vivo_sigue_activo(tmp_path: Path) -> None:
    clock = FakeClock()
    _write_marker_by_other(tmp_path, pid=4242, heartbeat=clock.now.isoformat())
    clock.advance(minutes=10)
    state, _ = files.classify_marker(tmp_path, clock, alive=lambda pid: True)
    assert state == files.ACTIVE


def test_sin_forma_de_comprobar_el_proceso_el_estado_es_desconocido(tmp_path: Path) -> None:
    clock = FakeClock()
    _write_marker_by_other(tmp_path, pid=4242, heartbeat=clock.now.isoformat())
    clock.advance(minutes=10)
    state, _ = files.classify_marker(tmp_path, clock, alive=lambda pid: None)
    assert state == files.UNKNOWN


def test_marcador_ilegible_es_desconocido(tmp_path: Path) -> None:
    (tmp_path / files.MARKER_NAME).write_text("no es json", encoding="utf-8")
    state, _ = files.classify_marker(tmp_path, FakeClock(), alive=lambda pid: False)
    assert state == files.UNKNOWN


def test_un_proceso_real_que_ya_termino_se_reconoce_como_inexistente() -> None:
    """Comprobación real con el sistema operativo: el PID de un proceso terminado no está vivo."""
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    assert files.process_alive(child.pid) is False


def test_un_proceso_real_en_curso_se_reconoce_como_existente() -> None:
    assert files.process_alive(os.getpid()) is True


def test_restaurar_con_marcador_abandonado_procede_y_no_borra_el_marcador(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    populate(settings, clock)
    directory = tmp_path / "copias"
    backup = _backup(settings, directory, clock)
    _write_marker_by_other(directory, pid=4242, heartbeat=clock.now.isoformat())
    clock.advance(minutes=10)

    outcome = restore_backup(_live(settings), directory, backup, clock, alive=lambda pid: False)

    assert outcome.status == "restaurada"
    assert (directory / files.MARKER_NAME).exists()  # la restauración nunca borra el marcador


def test_restaurar_con_marcador_activo_se_niega_aunque_el_proceso_no_se_pueda_comprobar(
    tmp_path: Path, settings: Settings
) -> None:
    clock = FakeClock()
    populate(settings, clock)
    directory = tmp_path / "copias"
    backup = _backup(settings, directory, clock)
    _write_marker_by_other(directory, pid=4242, heartbeat=clock.now.isoformat())
    clock.advance(minutes=10)
    before = sha(_live(settings))

    outcome = restore_backup(_live(settings), directory, backup, clock, alive=lambda pid: None)

    assert outcome.status == "rechazada"
    assert "no se puede restaurar" in outcome.message
    assert sha(_live(settings)) == before


def test_con_latido_reciente_se_niega_la_restauracion(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    populate(settings, clock)
    directory = tmp_path / "copias"
    backup = _backup(settings, directory, clock)
    files.write_marker(directory, clock)  # latido reciente

    outcome = restore_backup(_live(settings), directory, backup, clock, alive=lambda pid: False)

    assert outcome.status == "rechazada"
    assert "latido reciente" in outcome.message
