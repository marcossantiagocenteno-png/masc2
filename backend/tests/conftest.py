"""Fixtures compartidas por las pruebas del backend."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EVALS_DIR = REPO_ROOT / "evals"


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
