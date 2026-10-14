"""Restauración: estado esperado, rechazos sin tocar la base, reversión y esquema anterior."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import timedelta
from pathlib import Path

import pytest

from fastapi.testclient import TestClient
from alembic import command

from app.backups import files
from app.backups.restore import restore_backup
from app.backups.service import BackupService
from app.backups.verify import schema_order, verify_sqlite
from app.config import Settings
from app.drafts.service import DraftService
from app.main import create_app
from tests.backup_fakes import FakeClock, counts, populate, sha
from tests.test_migrations import _config, _names


def _live(settings: Settings) -> Path:
    return Path(settings.database_url.removeprefix("sqlite:///"))


def _backup(settings: Settings, directory: Path, clock: FakeClock) -> Path:
    service = BackupService(
        source=_live(settings),
        directory=directory,
        clock=clock,
        keep=14,
        min_keep=3,
        max_age=timedelta(days=30),
    )
    outcome = service.run()
    assert outcome.path is not None, outcome.message
    return outcome.path


def _restore(settings: Settings, directory: Path, backup: Path, clock: FakeClock, **options):  # type: ignore[no-untyped-def]
    return restore_backup(_live(settings), directory, backup, clock, **options)


# 7. Restauración devuelve el estado esperado y conserva los datos recuperables ---


def test_restaurar_devuelve_el_estado_de_la_copia_y_conserva_lo_posterior(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    manuscript_id = populate(settings, clock)
    directory = tmp_path / "copias"
    backup = _backup(settings, directory, clock)

    # Cambios posteriores a la copia: nuevo borrador y una versión formal nueva.
    with TestClient(create_app(settings)) as client:
        base = f"/projects/{client.get(f'/manuscripts/{manuscript_id}').json()['project_id']}/manuscripts/{manuscript_id}"
        # La revisión actual tras populate() es 2: el conflicto de populate() no la avanza.
        saved = client.put(
            base + "/draft",
            json={"content": "Cambio posterior a la copia.", "base_revision": 2},
        )
        assert saved.status_code == 200
        client.post(base + "/versions", json={"content": "Versión posterior."})

    outcome = _restore(settings, directory, backup, clock)

    assert outcome.status == "restaurada", outcome.message
    assert counts(_live(settings))["manuscript_versions"] == 2  # la versión posterior ya no está
    assert outcome.preventive is not None and outcome.preventive.exists()  # el estado posterior se conserva

    with TestClient(create_app(settings)) as client:
        draft = client.get(base + "/draft").json()
        points = client.get(base + "/recovery-points").json()
    assert draft["content"] == "Borrador con cambios."  # la restauración vuelve al estado de la copia
    assert {p["reason"] for p in points} >= {"periodico", "conflicto"}


def test_la_copia_preventiva_conserva_el_estado_que_se_reemplazo(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    manuscript_id = populate(settings, clock)
    directory = tmp_path / "copias"
    backup = _backup(settings, directory, clock)
    clock.advance(minutes=10)
    DraftService(_session(settings), settings.max_version_chars, clock).save(manuscript_id, "Trabajo no copiado.", 2)

    outcome = _restore(settings, directory, backup, clock)

    assert outcome.preventive is not None
    assert "Trabajo no copiado." in _read_draft(outcome.preventive)


# 8. Restauración fallida: la base activa queda intacta --------------------


def test_una_copia_corrupta_se_rechaza_sin_tocar_la_base(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    populate(settings, clock)
    corrupt = tmp_path / "corrupta.sqlite"
    corrupt.write_bytes(b"esto no es una base")
    before = sha(_live(settings))

    outcome = _restore(settings, tmp_path / "copias", corrupt, clock)

    assert outcome.status == "rechazada"
    assert sha(_live(settings)) == before
    assert list((tmp_path / "copias").glob("preventiva-*")) == []


def test_una_base_en_uso_impide_restaurar_sin_cambios(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    populate(settings, clock)
    directory = tmp_path / "copias"
    backup = _backup(settings, directory, clock)
    before = sha(_live(settings))

    holder = sqlite3.connect(_live(settings), isolation_level=None)
    try:
        holder.execute("BEGIN EXCLUSIVE")
        outcome = _restore(settings, directory, backup, clock)
    finally:
        holder.execute("ROLLBACK")
        holder.close()

    assert outcome.status == "rechazada"
    assert "en uso" in outcome.message
    assert sha(_live(settings)) == before
    assert list(directory.glob("preventiva-*")) == []


def test_con_el_marcador_de_backend_en_marcha_no_se_restaura(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    populate(settings, clock)
    directory = tmp_path / "copias"
    backup = _backup(settings, directory, clock)
    files.write_marker(directory, clock)
    before = sha(_live(settings))

    refused = _restore(settings, directory, backup, clock)
    assert refused.status == "rechazada"
    assert "en marcha" in refused.message
    assert sha(_live(settings)) == before

    forced = _restore(settings, directory, backup, clock, ignore_running_marker=True)
    assert forced.status == "restaurada"


def test_un_manifiesto_con_otro_hash_rechaza_la_copia(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    populate(settings, clock)
    directory = tmp_path / "copias"
    backup = _backup(settings, directory, clock)
    manifest = files.manifest_path(backup)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["sha256"] = "0" * 64
    manifest.write_text(json.dumps(data), encoding="utf-8")
    before = sha(_live(settings))

    outcome = _restore(settings, directory, backup, clock)

    assert outcome.status == "rechazada"
    assert "hash" in outcome.message
    assert sha(_live(settings)) == before


def test_si_la_verificacion_posterior_falla_se_revierte_a_la_preventiva(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    populate(settings, clock)
    directory = tmp_path / "copias"
    backup = _backup(settings, directory, clock)
    before = sha(_live(settings))

    def damage_after_replace(active: Path) -> None:
        active.write_text("daño posterior a la sustitución", encoding="utf-8")

    outcome = _restore(settings, directory, backup, clock, after_replace=damage_after_replace)

    assert outcome.status == "revertida"
    assert sha(_live(settings)) == before
    assert verify_sqlite(_live(settings), schema_order()).ok


# Esquema anterior ----------------------------------------------------------


def test_una_copia_de_esquema_anterior_exige_permiso_explicito(tmp_path: Path, settings: Settings) -> None:
    old_db = tmp_path / "antiguo.sqlite"
    command.upgrade(_config(f"sqlite:///{old_db.as_posix()}"), "0004_proyectos")
    clock = FakeClock()
    directory = tmp_path / "copias"
    old_backup = BackupService(
        source=old_db, directory=directory, clock=clock, keep=5, min_keep=1, max_age=timedelta(days=30)
    ).run().path
    assert old_backup is not None
    before = sha(_live(settings))

    refused = _restore(settings, directory, old_backup, clock)
    assert refused.status == "rechazada"
    assert "esquema anterior" in refused.message
    assert sha(_live(settings)) == before


def test_una_copia_antigua_se_restaura_migrada_y_la_base_activa_queda_en_la_revision_actual(tmp_path: Path, settings: Settings) -> None:
    """Antes: la base quedaba en esquema 0004 sin tablas nuevas. Ahora la copia se migra en un temporal primero."""
    old_db = tmp_path / "antiguo.sqlite"
    command.upgrade(_config(f"sqlite:///{old_db.as_posix()}"), "0004_proyectos")
    clock = FakeClock()
    directory = tmp_path / "copias"
    old_backup = BackupService(
        source=old_db, directory=directory, clock=clock, keep=5, min_keep=1, max_age=timedelta(days=30)
    ).run().path
    assert old_backup is not None
    backup_before = sha(old_backup)

    allowed = _restore(settings, directory, old_backup, clock, allow_older_schema=True)

    assert allowed.status == "restaurada", allowed.message
    assert allowed.schema_status == "actual"
    assert "migró" in allowed.message
    assert "scene_manuscripts" in _names(_live(settings), "table")  # la aplicación actual la necesita
    assert sha(old_backup) == backup_before  # la copia de origen no se ha modificado
    assert _names(_live(settings), "table") >= {"manuscript_drafts", "structure_nodes"}


def test_si_la_migracion_de_la_copia_antigua_falla_se_rechaza_y_la_base_activa_no_cambia(tmp_path: Path, settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.backups.restore as restore_module

    old_db = tmp_path / "antiguo.sqlite"
    command.upgrade(_config(f"sqlite:///{old_db.as_posix()}"), "0004_proyectos")
    clock = FakeClock()
    directory = tmp_path / "copias"
    old_backup = BackupService(
        source=old_db, directory=directory, clock=clock, keep=5, min_keep=1, max_age=timedelta(days=30)
    ).run().path
    assert old_backup is not None
    before = sha(_live(settings))

    monkeypatch.setattr(restore_module, "migrate_copy_to_head", lambda copy: "fallo simulado de migración")
    outcome = _restore(settings, directory, old_backup, clock, allow_older_schema=True)

    assert outcome.status == "rechazada"
    assert "fallo simulado de migración" in outcome.message
    assert "Procedimiento manual" in outcome.message
    assert sha(_live(settings)) == before
    assert not list(directory.glob(".restore-*.sqlite"))  # el temporal se retira


def test_una_restauracion_que_deja_la_base_en_esquema_anterior_se_revierte(tmp_path: Path, settings: Settings) -> None:
    """Si la base final no queda en la revisión actual, se revierte aunque sea legible."""
    old_db = tmp_path / "antiguo.sqlite"
    command.upgrade(_config(f"sqlite:///{old_db.as_posix()}"), "0004_proyectos")
    clock = FakeClock()
    directory = tmp_path / "copias"
    old_backup = BackupService(
        source=old_db, directory=directory, clock=clock, keep=5, min_keep=1, max_age=timedelta(days=30)
    ).run().path
    assert old_backup is not None
    before = sha(_live(settings))

    def drop_new_tables(active: Path) -> None:
        """Simula un fallo que deja la base sin las tablas de la revisión actual, después de sustituirla."""
        with closing(sqlite3.connect(active)) as connection:
            connection.execute("UPDATE alembic_version SET version_num = '0004_proyectos'")
            connection.commit()

    outcome = _restore(settings, directory, old_backup, clock, allow_older_schema=True, after_replace=drop_new_tables)
    assert outcome.status == "revertida"
    assert sha(_live(settings)) == before


# Ciclo de vida del backend -----------------------------------------------


def test_el_backend_marca_su_ejecucion_mientras_corre(tmp_path: Path, settings: Settings) -> None:
    directory = tmp_path / "copias"
    marked = Settings(**{**settings.__dict__, "backup_dir": str(directory), "backup_interval_minutes": 0})

    with TestClient(create_app(marked)):
        assert files.read_marker(directory) is not None
    assert files.read_marker(directory) is None


# Utilidades ----------------------------------------------------------------


def _session(settings: Settings):  # type: ignore[no-untyped-def]
    from app.db.session import create_engine_for, create_session_factory

    return create_session_factory(create_engine_for(settings.database_url))()


def _read_draft(path: Path) -> str:
    with closing(sqlite3.connect(path)) as connection:
        return connection.execute("SELECT content FROM manuscript_drafts").fetchone()[0]
