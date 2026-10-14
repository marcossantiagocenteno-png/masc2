"""Migración 0007: actor y resultado en las decisiones, y validación de vínculos en la base."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from alembic import command

from tests.test_migrations import _config, _names


def _url(tmp_path: Path, name: str) -> tuple[str, Path]:
    url = f"sqlite:///{(tmp_path / name).as_posix()}"
    return url, Path(url.removeprefix("sqlite:///"))


def _seed_0006(db: Path) -> None:
    """Dos proyectos, un personaje y una escena en el primero, y una decisión previa a 0007."""
    with closing(sqlite3.connect(db)) as connection:
        connection.executescript(
            """
            INSERT INTO projects (name, status, created_at, updated_at) VALUES ('P1', 'activo', '2026-01-01', '2026-01-01');
            INSERT INTO projects (name, status, created_at, updated_at) VALUES ('P2', 'activo', '2026-01-01', '2026-01-01');
            INSERT INTO characters (project_id, name, estado, origen, created_at, updated_at) VALUES (1, 'Ana', 'canonico', 'autor', '2026-01-01', '2026-01-01');
            INSERT INTO structure_nodes (project_id, kind, position, title, estado, origen, created_at, updated_at) VALUES (1, 'escena', 0, 'E', 'provisional', 'autor', '2026-01-01', '2026-01-01');
            INSERT INTO narrative_decisions (project_id, element_kind, element_id, accion, estado_previo, estado_nuevo, snapshot, created_at)
              VALUES (1, 'personaje', 1, 'aprobar_canon', 'provisional', 'canonico', '{}', '2026-01-01');
            INSERT INTO narrative_links (project_id, source_kind, source_id, target_kind, target_id, relation, estado, origen, created_at, updated_at)
              VALUES (1, 'personaje', 1, 'escena', 1, 'participa_en', 'provisional', 'autor', '2026-01-01', '2026-01-01');
            """
        )
        connection.commit()


def test_la_migracion_conserva_los_vinculos_validos_y_atribuye_las_decisiones_previas_al_autor(tmp_path: Path) -> None:
    url, db = _url(tmp_path, "valida.sqlite")
    command.upgrade(_config(url), "0006_planificacion_narrativa")
    _seed_0006(db)

    command.upgrade(_config(url), "head")

    with closing(sqlite3.connect(db)) as connection:
        links = connection.execute("SELECT source_kind, source_id, target_kind, target_id, relation FROM narrative_links").fetchall()
        decision = connection.execute("SELECT actor, resultado FROM narrative_decisions").fetchone()
    assert links == [("personaje", 1, "escena", 1, "participa_en")]
    assert decision == ("autor", None)  # decisión anterior: sin resultado registrado
    assert {"trg_narrative_links_check_insert", "trg_narrative_links_check_update"} <= _names(db, "trigger")


def test_una_migracion_con_vinculos_invalidos_no_se_aplica_y_no_toca_nada(tmp_path: Path) -> None:
    """Un vínculo de otra novela que se insertó antes de la regla bloquea la migración: no se borra ni se corrige."""
    url, db = _url(tmp_path, "invalida.sqlite")
    command.upgrade(_config(url), "0006_planificacion_narrativa")
    _seed_0006(db)
    with closing(sqlite3.connect(db)) as connection:
        connection.execute(
            "INSERT INTO narrative_links (project_id, source_kind, source_id, target_kind, target_id, relation, estado, origen, created_at, updated_at) "
            "VALUES (2, 'personaje', 1, 'escena', 1, 'participa_en', 'provisional', 'autor', '2026-01-01', '2026-01-01')"
        )
        connection.commit()

    with pytest.raises(RuntimeError, match="no cumplen la regla"):
        command.upgrade(_config(url), "head")

    with closing(sqlite3.connect(db)) as connection:
        version = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        count = connection.execute("SELECT COUNT(*) FROM narrative_links").fetchone()[0]
        columns = {row[1] for row in connection.execute("PRAGMA table_info(narrative_decisions)")}
    assert version == "0006_planificacion_narrativa"
    assert count == 2  # el vínculo inválido sigue ahí: no se ha corregido nada
    assert "actor" not in columns
    assert "trg_narrative_links_check_insert" not in _names(db, "trigger")
