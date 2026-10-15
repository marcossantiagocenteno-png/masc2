"""Migración 0010: géneros seleccionables y directrices. Conserva proyectos, sinopsis, género y textos existentes."""

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


def test_0010_copia_el_genero_de_texto_sin_tocar_el_proyecto(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'legacy.sqlite'}"
    db = tmp_path / "legacy.sqlite"
    command.upgrade(_config(url), "0009_escritura_escenas")

    with closing(sqlite3.connect(db)) as connection:
        connection.execute(
            "INSERT INTO projects (name, status, created_at, updated_at, premise, synopsis, genre, tone, structure_version) "
            "VALUES ('A', 'activo', '2026-01-01 10:00:00', '2026-01-01 10:00:00', 'Premisa A', 'Sinopsis que no se borra', 'Misterio', 'sobrio', 0)"
        )
        connection.execute(
            "INSERT INTO projects (name, status, created_at, updated_at, genre, structure_version) "
            "VALUES ('B', 'activo', '2026-01-01 10:00:00', '2026-01-01 10:00:00', 'Gótico y costumbrista', 0)"
        )
        connection.execute(
            "INSERT INTO projects (name, status, created_at, updated_at, genre, structure_version) "
            "VALUES ('C', 'activo', '2026-01-01 10:00:00', '2026-01-01 10:00:00', '   ', 0)"
        )
        connection.execute(
            "INSERT INTO manuscripts (title, created_at) VALUES ('Manuscrito', '2026-01-01 10:00:00')"
        )
        connection.commit()
    antes = _filas(db, "SELECT id, name, premise, synopsis, genre, tone FROM projects ORDER BY id")
    manuscritos_antes = _filas(db, "SELECT id, title FROM manuscripts")

    command.upgrade(_config(url), "head")

    assert _filas(db, "SELECT id, name, premise, synopsis, genre, tone FROM projects ORDER BY id") == antes
    assert _filas(db, "SELECT id, title FROM manuscripts") == manuscritos_antes
    generos = _filas(db, "SELECT project_id, genre_key, custom_label, activo FROM project_genres ORDER BY project_id")
    # «Misterio» coincide con la clave del catálogo; el texto libre sin coincidencia se conserva como «otro».
    assert generos == [(1, "misterio", None, 1), (2, "otro", "Gótico y costumbrista", 1)]


def test_0010_crea_directrices_vacias_y_no_bloquea_la_bajada_automatica(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'nuevo.sqlite'}"
    command.upgrade(_config(url), "head")
    db = tmp_path / "nuevo.sqlite"
    assert _filas(db, "SELECT COUNT(*) FROM narrative_directives") == [(0,)]
    with pytest.raises(NotImplementedError):
        command.downgrade(_config(url), "0009_escritura_escenas")
