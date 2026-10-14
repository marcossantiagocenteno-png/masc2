"""Migraciones Alembic: subir, bajar y esquema resultante."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

from tests.conftest import BACKEND_DIR

EXPECTED_TABLES = {"manuscripts", "manuscript_versions", "editorial_reviews", "review_items"}
EXPECTED_TRIGGERS = {
    f"trg_{table}_no_{action}"
    for table in ("manuscript_versions", "editorial_reviews", "review_items")
    for action in ("update", "delete")
}


def _config(url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["database_url"] = url
    return config


def _names(db_path: Path, kind: str) -> set[str]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = ?", (kind,)
        ).fetchall()
    return {row[0] for row in rows}


def test_upgrade_crea_tablas_y_triggers(database_url: str) -> None:
    db_path = Path(database_url.removeprefix("sqlite:///"))
    assert EXPECTED_TABLES <= _names(db_path, "table")
    assert EXPECTED_TRIGGERS <= _names(db_path, "trigger")


def test_downgrade_elimina_tablas_y_triggers(database_url: str) -> None:
    db_path = Path(database_url.removeprefix("sqlite:///"))
    command.downgrade(_config(database_url), "base")
    assert not (EXPECTED_TABLES & _names(db_path, "table"))
    assert not (EXPECTED_TRIGGERS & _names(db_path, "trigger"))


def test_upgrade_puede_repetirse_tras_downgrade(database_url: str) -> None:
    db_path = Path(database_url.removeprefix("sqlite:///"))
    command.downgrade(_config(database_url), "base")
    command.upgrade(_config(database_url), "head")
    assert EXPECTED_TABLES <= _names(db_path, "table")
