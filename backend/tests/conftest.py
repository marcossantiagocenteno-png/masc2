"""Fixtures compartidas por las pruebas del backend."""

from __future__ import annotations

import copy
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db.session import create_engine_for, create_session_factory
from app.main import create_app
from app.texts.service import TextService

REPO_ROOT = Path(__file__).resolve().parents[2]
EVALS_DIR = REPO_ROOT / "evals"
BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture
def valid_case_data() -> dict[str, Any]:
    """Datos de un caso válido y ficticio. Cada prueba recibe una copia propia."""
    return copy.deepcopy(
        {
            "schema_version": 1,
            "id": "caso-prueba-01",
            "title": "Caso de prueba",
            "provenance": "ejemplo_ficticio",
            "language": "es",
            "assignment": "Escribe una escena breve.",
            "narrative_context": "Contexto ficticio.",
            "constraints": ["Una sola voz narrativa."],
            "expected_properties": ["La escena cambia algo."],
            "dimensions_under_test": ["dramaturgia"],
            "evaluation_criteria": [
                {
                    "dimension": "dramaturgia",
                    "question": "¿La escena cambia algo?",
                    "critical_defect_if": ["No cambia nada."],
                    "preference_only_if": [],
                }
            ],
        }
    )


@pytest.fixture
def valid_evaluation_data() -> dict[str, Any]:
    """Datos de una evaluación pendiente y coherente con el caso de prueba."""
    return {
        "schema_version": 1,
        "case_id": "caso-prueba-01",
        "status": "pendiente",
        "assessor": None,
        "scores": [],
    }


# ---------------------------------------------------------------------------
# Base de datos temporal migrada con Alembic (tarea 002)
# ---------------------------------------------------------------------------


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    """SQLite nuevo en un directorio temporal, migrado hasta ``head``.

    Las pruebas usan las migraciones reales, no ``create_all``: así se
    comprueba también el esquema y los triggers de inmutabilidad.
    """
    url = f"sqlite:///{(tmp_path / 'test.sqlite').as_posix()}"
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["database_url"] = url
    command.upgrade(config, "head")
    return url


@pytest.fixture
def settings(database_url: str) -> Settings:
    """Configuración de prueba con el límite por defecto."""
    return Settings(database_url=database_url)


@pytest.fixture
def session_factory(settings: Settings) -> Iterator[sessionmaker[Session]]:
    engine = create_engine_for(settings.database_url)
    yield create_session_factory(engine)
    engine.dispose()


@pytest.fixture
def session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with session_factory() as db_session:
        yield db_session


@pytest.fixture
def service(session: Session, settings: Settings) -> TextService:
    return TextService(session, max_version_chars=settings.max_version_chars)


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
