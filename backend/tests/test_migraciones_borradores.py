"""Migración 0005: borradores y puntos de recuperación.

Comprueba que la migración crea las tablas y los triggers, que conserva los datos
existentes y que no se revierte automáticamente.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from alembic import command

from tests.test_migrations import EXPECTED_TABLES, EXPECTED_TRIGGERS, _config, _names

DRAFT_TABLES = {"manuscript_drafts", "draft_recovery_points"}
DRAFT_TRIGGERS = {
    "trg_draft_recovery_points_no_update",
    "trg_draft_recovery_points_no_delete",
}


def test_upgrade_crea_tablas_de_borradores_y_triggers_de_puntos(database_url: str) -> None:
    db_path = Path(database_url.removeprefix("sqlite:///"))
    assert DRAFT_TABLES <= _names(db_path, "table")
    assert DRAFT_TRIGGERS <= _names(db_path, "trigger")
    assert EXPECTED_TABLES <= _names(db_path, "table")
    assert EXPECTED_TRIGGERS <= _names(db_path, "trigger")


def test_puntos_de_recuperacion_son_inmutables(database_url: str) -> None:
    db_path = Path(database_url.removeprefix("sqlite:///"))
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute(
            "INSERT INTO manuscripts (title, created_at) VALUES ('Novela', '2026-01-01 10:00:00')"
        )
        connection.execute(
            "INSERT INTO draft_recovery_points "
            "(manuscript_id, reason, content, char_count, sha256, draft_revision, created_at) "
            "VALUES (1, 'periodico', 'Texto', 5, 'h', 1, '2026-01-01 10:00:00')"
        )
        connection.commit()
        with pytest.raises(sqlite3.DatabaseError, match="inmutable"):
            connection.execute("UPDATE draft_recovery_points SET content = 'otro'")
        with pytest.raises(sqlite3.DatabaseError, match="inmutable"):
            connection.execute("DELETE FROM draft_recovery_points")


def test_upgrade_con_datos_existentes_no_toca_versiones_ni_proyectos(tmp_path: Path) -> None:
    """Base con datos reales (hasta 0004) migrada a la cabeza: los datos siguen igual."""
    url = f"sqlite:///{(tmp_path / 'con_datos.sqlite').as_posix()}"
    db_path = Path(url.removeprefix("sqlite:///"))
    command.upgrade(_config(url), "0004_proyectos")
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("INSERT INTO projects (name, status, created_at, updated_at) VALUES ('P', 'activo', '2026-01-01 10:00:00', '2026-01-01 10:00:00')")
        connection.execute(
            "INSERT INTO manuscripts (title, created_at, project_id) VALUES ('Novela', '2026-01-01 10:00:00', 1)"
        )
        connection.execute(
            "INSERT INTO manuscript_versions (manuscript_id, number, content, sha256, char_count, created_at) "
            "VALUES (1, 1, 'Texto formal', 'hash', 12, '2026-01-01 10:00:00')"
        )
        connection.commit()

    command.upgrade(_config(url), "head")

    with closing(sqlite3.connect(db_path)) as connection:
        versiones = connection.execute("SELECT number, content FROM manuscript_versions").fetchall()
        proyectos = connection.execute("SELECT name, status FROM projects").fetchall()
        manuscritos = connection.execute("SELECT title, project_id FROM manuscripts").fetchall()
        borradores = connection.execute("SELECT COUNT(*) FROM manuscript_drafts").fetchone()[0]
    assert versiones == [(1, "Texto formal")]
    assert proyectos == [("P", "activo")]
    assert manuscritos == [("Novela", 1)]
    assert borradores == 0
    assert DRAFT_TABLES <= _names(db_path, "table")


def test_bajar_0005_no_es_automatico_y_no_borra_nada(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'bajada.sqlite').as_posix()}"
    db_path = Path(url.removeprefix("sqlite:///"))
    command.upgrade(_config(url), "head")
    with pytest.raises(NotImplementedError, match="Restaura la copia"):
        command.downgrade(_config(url), "0004_proyectos")
    assert DRAFT_TABLES <= _names(db_path, "table")
