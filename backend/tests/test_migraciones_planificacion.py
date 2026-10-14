"""Migración 0006: planificación narrativa. Conserva proyectos, manuscritos y versiones existentes."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from alembic import command

from tests.test_migrations import _config, _names

PLANNING_TABLES = {
    "characters",
    "places",
    "plot_elements",
    "timeline_events",
    "structure_nodes",
    "narrative_links",
    "narrative_decisions",
}


def test_upgrade_con_datos_existentes_conserva_proyectos_manuscritos_y_versiones(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'con_datos.sqlite').as_posix()}"
    db_path = Path(url.removeprefix("sqlite:///"))
    command.upgrade(_config(url), "0005_borradores_y_recuperacion")
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("INSERT INTO projects (name, status, created_at, updated_at) VALUES ('Novela previa', 'activo', '2026-01-01 10:00:00', '2026-01-01 10:00:00')")
        connection.execute("INSERT INTO manuscripts (title, created_at, project_id) VALUES ('Manuscrito', '2026-01-01 10:00:00', 1)")
        connection.execute(
            "INSERT INTO manuscript_versions (manuscript_id, number, content, sha256, char_count, created_at) "
            "VALUES (1, 1, 'Texto formal intacto', 'hash', 19, '2026-01-01 10:00:00')"
        )
        connection.commit()

    command.upgrade(_config(url), "head")

    assert PLANNING_TABLES <= _names(db_path, "table")
    with closing(sqlite3.connect(db_path)) as connection:
        project = connection.execute("SELECT name, status, premise, genre, development_status FROM projects").fetchone()
        versions = connection.execute("SELECT number, content FROM manuscript_versions").fetchall()
        manuscripts = connection.execute("SELECT title, project_id FROM manuscripts").fetchall()
    assert project == ("Novela previa", "activo", None, None, None)
    assert versions == [(1, "Texto formal intacto")]
    assert manuscripts == [("Manuscrito", 1)]


def test_las_decisiones_son_inmutables_tras_la_migracion(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'inmutable.sqlite').as_posix()}"
    db_path = Path(url.removeprefix("sqlite:///"))
    command.upgrade(_config(url), "head")
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("INSERT INTO projects (name, status, created_at, updated_at) VALUES ('P', 'activo', '2026-01-01', '2026-01-01')")
        connection.execute(
            "INSERT INTO narrative_decisions (project_id, element_kind, element_id, accion, created_at) "
            "VALUES (1, 'personaje', 1, 'aprobar_canon', '2026-01-01')"
        )
        connection.commit()
        with pytest.raises(sqlite3.DatabaseError, match="inmutable"):
            connection.execute("UPDATE narrative_decisions SET accion = 'otra'")


def test_bajar_0006_no_es_automatico_y_no_borra_nada(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'bajada.sqlite').as_posix()}"
    db_path = Path(url.removeprefix("sqlite:///"))
    command.upgrade(_config(url), "head")
    with pytest.raises(NotImplementedError, match="Restaura la copia"):
        command.downgrade(_config(url), "0005_borradores_y_recuperacion")
    assert PLANNING_TABLES <= _names(db_path, "table")
