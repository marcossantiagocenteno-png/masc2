"""Migración 0011: recomendaciones de estructura. Aditiva, con historial inmutable y sin tocar datos existentes."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from alembic import command

from tests.test_migrations import _config


def _filas(db: Path, sql: str, params: tuple = ()) -> list[tuple]:
    with closing(sqlite3.connect(db)) as connection:
        return connection.execute(sql, params).fetchall()


def _ejecutar(db: Path, sql: str, params: tuple = ()) -> None:
    with closing(sqlite3.connect(db)) as connection:
        connection.execute(sql, params)
        connection.commit()


def test_0011_no_cambia_proyectos_ni_estructura_existente(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'legacy.sqlite'}"
    db = tmp_path / "legacy.sqlite"
    command.upgrade(_config(url), "0010_generos_y_directrices")
    _ejecutar(
        db,
        "INSERT INTO projects (name, status, created_at, updated_at, premise, structure_version) "
        "VALUES ('A', 'activo', '2026-01-01 10:00:00', '2026-01-01 10:00:00', 'Premisa A', 0)",
    )
    _ejecutar(
        db,
        "INSERT INTO structure_nodes (project_id, kind, position, estado, origen, title, created_at, updated_at) "
        "VALUES (1, 'acto', 0, 'provisional', 'autor', 'Acto antiguo', '2026-01-01 10:00:00', '2026-01-01 10:00:00')",
    )
    antes_proyectos = _filas(db, "SELECT id, name, premise, structure_version FROM projects ORDER BY id")
    antes_nodos = _filas(db, "SELECT id, title, estado, origen FROM structure_nodes ORDER BY id")

    command.upgrade(_config(url), "head")

    assert _filas(db, "SELECT id, name, premise, structure_version FROM projects ORDER BY id") == antes_proyectos
    assert _filas(db, "SELECT id, title, estado, origen FROM structure_nodes ORDER BY id") == antes_nodos
    assert _filas(db, "SELECT COUNT(*) FROM structure_model_choices") == [(0,)]
    assert _filas(db, "SELECT COUNT(*) FROM structure_proposals") == [(0,)]


def test_0011_el_historial_de_modelos_no_se_modifica_ni_se_borra(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'nuevo.sqlite'}"
    command.upgrade(_config(url), "head")
    db = tmp_path / "nuevo.sqlite"
    _ejecutar(db, "INSERT INTO projects (name, status, created_at, updated_at, structure_version) VALUES ('A', 'activo', '2026-01-01 10:00:00', '2026-01-01 10:00:00', 0)")
    _ejecutar(db, "INSERT INTO structure_model_choices (project_id, model_key, created_at) VALUES (1, 'freytag', '2026-01-01 10:00:00')")

    with pytest.raises(sqlite3.IntegrityError, match="inmutable"):
        _ejecutar(db, "UPDATE structure_model_choices SET model_key = 'save_the_cat'")
    with pytest.raises(sqlite3.IntegrityError, match="inmutable"):
        _ejecutar(db, "DELETE FROM structure_model_choices")
    assert _filas(db, "SELECT model_key FROM structure_model_choices") == [("freytag",)]


def test_0011_una_propuesta_no_se_borra(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'propuestas.sqlite'}"
    command.upgrade(_config(url), "head")
    db = tmp_path / "propuestas.sqlite"
    _ejecutar(db, "INSERT INTO projects (name, status, created_at, updated_at, structure_version) VALUES ('A', 'activo', '2026-01-01 10:00:00', '2026-01-01 10:00:00', 0)")
    _ejecutar(
        db,
        "INSERT INTO structure_proposals (project_id, lote, model_key, position, title, funcion, pregunta, base_tipo, entradas, estado, created_at, updated_at) "
        "VALUES (1, 1, 'freytag', 0, 'Exposición', 'f', 'p?', 'pregunta_pendiente', '{}', 'pendiente', '2026-01-01 10:00:00', '2026-01-01 10:00:00')",
    )
    with pytest.raises(sqlite3.IntegrityError, match="no se borra"):
        _ejecutar(db, "DELETE FROM structure_proposals")


def test_0011_no_permite_dos_propuestas_con_la_misma_posicion_en_un_lote(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'unicas.sqlite'}"
    command.upgrade(_config(url), "head")
    db = tmp_path / "unicas.sqlite"
    _ejecutar(db, "INSERT INTO projects (name, status, created_at, updated_at, structure_version) VALUES ('A', 'activo', '2026-01-01 10:00:00', '2026-01-01 10:00:00', 0)")
    fila = (
        "INSERT INTO structure_proposals (project_id, lote, model_key, position, title, funcion, pregunta, base_tipo, entradas, estado, created_at, updated_at) "
        "VALUES (1, 1, 'freytag', 0, 'x', 'f', 'p?', 'pregunta_pendiente', '{}', 'pendiente', '2026-01-01 10:00:00', '2026-01-01 10:00:00')"
    )
    _ejecutar(db, fila)
    with pytest.raises(sqlite3.IntegrityError):
        _ejecutar(db, fila)


def test_0011_la_bajada_no_es_automatica(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'bajada.sqlite'}"
    command.upgrade(_config(url), "head")
    with pytest.raises(NotImplementedError):
        command.downgrade(_config(url), "0010_generos_y_directrices")
