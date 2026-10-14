"""Migraciones Alembic: subir, bajar y esquema resultante."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
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
    with closing(sqlite3.connect(db_path)) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = ?", (kind,)
        ).fetchall()
    return {row[0] for row in rows}


def test_upgrade_crea_tablas_y_triggers(database_url: str) -> None:
    db_path = Path(database_url.removeprefix("sqlite:///"))
    assert EXPECTED_TABLES <= _names(db_path, "table")
    assert EXPECTED_TRIGGERS <= _names(db_path, "trigger")


def _upgrade_to_0003(tmp_path: Path) -> str:
    """Base de datos migrada hasta 0003, para probar bajadas sin pasar por 0004."""
    url = f"sqlite:///{(tmp_path / 'hasta_0003.sqlite').as_posix()}"
    command.upgrade(_config(url), "0003_analisis_proveedor_real")
    return url


def test_downgrade_de_0003_a_base_elimina_tablas_y_triggers(tmp_path: Path) -> None:
    url = _upgrade_to_0003(tmp_path)
    db_path = Path(url.removeprefix("sqlite:///"))
    command.downgrade(_config(url), "base")
    assert not ((EXPECTED_TABLES | {"projects"}) & _names(db_path, "table"))
    assert not (EXPECTED_TRIGGERS & _names(db_path, "trigger"))


def test_upgrade_puede_repetirse_tras_downgrade(tmp_path: Path) -> None:
    url = _upgrade_to_0003(tmp_path)
    db_path = Path(url.removeprefix("sqlite:///"))
    command.downgrade(_config(url), "base")
    command.upgrade(_config(url), "0003_analisis_proveedor_real")
    assert EXPECTED_TABLES <= _names(db_path, "table")


def test_bajar_0004_no_es_automatico_y_no_toca_los_datos(tmp_path: Path) -> None:
    """0004 no se revierte automáticamente: la vía segura es restaurar la copia previa."""
    url = _upgrade_to_0003(tmp_path)
    db_path = Path(url.removeprefix("sqlite:///"))
    command.upgrade(_config(url), "0004_proyectos")
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("INSERT INTO manuscripts (title, created_at) VALUES ('Intacto', '2026-01-01')")
        connection.commit()
    with pytest.raises(NotImplementedError, match="Restaura la copia"):
        command.downgrade(_config(url), "0003_analisis_proveedor_real")
    with closing(sqlite3.connect(db_path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM manuscripts").fetchone()[0] == 1
        assert "projects" in {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_bajar_a_0002_conserva_la_inmutabilidad_de_analisis(tmp_path: Path) -> None:
    """Revertir 0003 borra columnas reconstruyendo tablas: los triggers deben seguir activos."""
    url = _upgrade_to_0003(tmp_path)
    db_path = Path(url.removeprefix("sqlite:///"))
    command.downgrade(_config(url), "0002_analisis_editorial")
    assert {"trg_analysis_runs_no_update", "trg_analysis_findings_no_delete"} <= _names(db_path, "trigger")
    with closing(sqlite3.connect(db_path)) as connection:
        run_columns = {row[1] for row in connection.execute("PRAGMA table_info(analysis_runs)")}
        finding_columns = {row[1] for row in connection.execute("PRAGMA table_info(analysis_findings)")}
    assert "model_name" not in run_columns and "sent_external" not in run_columns
    assert "justification" not in finding_columns


def test_0004_asigna_los_manuscritos_existentes_a_un_proyecto_inicial(tmp_path: Path) -> None:
    """Migrar una base con datos conserva los textos y los asigna a 'Proyecto inicial'."""
    url = _upgrade_to_0003(tmp_path)
    db_path = Path(url.removeprefix("sqlite:///"))
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("INSERT INTO manuscripts (title, created_at) VALUES ('Anterior', '2026-01-01')")
        connection.execute(
            "INSERT INTO manuscript_versions (manuscript_id, number, content, sha256, char_count, created_at) "
            "VALUES (1, 1, 'Texto anterior.', 'x', 14, '2026-01-01')"
        )
        connection.commit()
    command.upgrade(_config(url), "head")
    with closing(sqlite3.connect(db_path)) as connection:
        assert connection.execute("SELECT name, status FROM projects").fetchall() == [("Proyecto inicial", "activo")]
        assert connection.execute("SELECT project_id FROM manuscripts").fetchall() == [(1,)]
        assert connection.execute("SELECT content FROM manuscript_versions").fetchall() == [("Texto anterior.",)]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_0004_sin_manuscritos_no_crea_proyecto_inicial(tmp_path: Path) -> None:
    url = _upgrade_to_0003(tmp_path)
    db_path = Path(url.removeprefix("sqlite:///"))
    command.upgrade(_config(url), "head")
    with closing(sqlite3.connect(db_path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0
