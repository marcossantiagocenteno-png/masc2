"""Pruebas de los modelos Pydantic del benchmark."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from pydantic import ValidationError

from app.benchmark.models import (
    BenchmarkCase,
    Dimension,
    DimensionScore,
    LiteraryEvaluation,
    Rubric,
)

# ---------------------------------------------------------------------------
# BenchmarkCase
# ---------------------------------------------------------------------------


def test_caso_valido_se_acepta(valid_case_data: dict[str, Any]) -> None:
    case = BenchmarkCase.model_validate(valid_case_data)
    assert case.id == "caso-prueba-01"
    assert case.dimensions_under_test == [Dimension.DRAMATURGY]


@pytest.mark.parametrize("case_id", ["ab", "Caso-01", "caso_01", "-caso", "caso-", "a" * 64])
def test_id_de_caso_invalido_se_rechaza(valid_case_data: dict[str, Any], case_id: str) -> None:
    valid_case_data["id"] = case_id
    with pytest.raises(ValidationError):
        BenchmarkCase.model_validate(valid_case_data)


def test_provenance_debe_marcar_ejemplo_ficticio(valid_case_data: dict[str, Any]) -> None:
    valid_case_data["provenance"] = "version_aprobada"
    with pytest.raises(ValidationError):
        BenchmarkCase.model_validate(valid_case_data)


def test_idioma_restringido_a_espanol(valid_case_data: dict[str, Any]) -> None:
    valid_case_data["language"] = "en"
    with pytest.raises(ValidationError):
        BenchmarkCase.model_validate(valid_case_data)


def test_campo_desconocido_se_rechaza(valid_case_data: dict[str, Any]) -> None:
    valid_case_data["texto_de_referencia"] = "Un texto inventado."
    with pytest.raises(ValidationError):
        BenchmarkCase.model_validate(valid_case_data)


@pytest.mark.parametrize("field", ["assignment", "narrative_context", "title"])
def test_textos_obligatorios_no_pueden_estar_vacios(
    valid_case_data: dict[str, Any], field: str
) -> None:
    valid_case_data[field] = "   "
    with pytest.raises(ValidationError):
        BenchmarkCase.model_validate(valid_case_data)


@pytest.mark.parametrize("field", ["constraints", "expected_properties"])
def test_listas_obligatorias_no_pueden_estar_vacias(
    valid_case_data: dict[str, Any], field: str
) -> None:
    valid_case_data[field] = []
    with pytest.raises(ValidationError):
        BenchmarkCase.model_validate(valid_case_data)


def test_dimension_desconocida_se_rechaza(valid_case_data: dict[str, Any]) -> None:
    valid_case_data["dimensions_under_test"] = ["originalidad"]
    with pytest.raises(ValidationError):
        BenchmarkCase.model_validate(valid_case_data)


def test_dimension_repetida_se_rechaza(valid_case_data: dict[str, Any]) -> None:
    valid_case_data["dimensions_under_test"] = ["dramaturgia", "dramaturgia"]
    valid_case_data["evaluation_criteria"].append(copy.deepcopy(valid_case_data["evaluation_criteria"][0]))
    with pytest.raises(ValidationError, match="repetidas"):
        BenchmarkCase.model_validate(valid_case_data)


def test_criterio_para_dimension_no_evaluada_se_rechaza(valid_case_data: dict[str, Any]) -> None:
    valid_case_data["evaluation_criteria"].append(
        {"dimension": "continuidad", "question": "¿Coherente?", "critical_defect_if": [], "preference_only_if": []}
    )
    with pytest.raises(ValidationError, match="no evaluadas"):
        BenchmarkCase.model_validate(valid_case_data)


def test_dimension_evaluada_sin_criterio_se_rechaza(valid_case_data: dict[str, Any]) -> None:
    valid_case_data["dimensions_under_test"] = ["dramaturgia", "continuidad"]
    with pytest.raises(ValidationError, match="faltan criterios"):
        BenchmarkCase.model_validate(valid_case_data)


# ---------------------------------------------------------------------------
# DimensionScore: límites de la escala 1-5
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("score", [1, 2, 3, 4, 5])
def test_puntuaciones_dentro_de_la_escala_se_aceptan(score: int) -> None:
    item = DimensionScore(dimension=Dimension.PROSE_VOICE, score=score, justification="Justificado.")
    assert item.score == score


@pytest.mark.parametrize("score", [0, -1, 6, 10])
def test_puntuaciones_fuera_de_la_escala_se_rechazan(score: int) -> None:
    with pytest.raises(ValidationError):
        DimensionScore(dimension=Dimension.PROSE_VOICE, score=score, justification="Justificado.")


@pytest.mark.parametrize("score", ["3", 3.0, 2.5, True, None])
def test_puntuaciones_no_enteras_se_rechazan(score: Any) -> None:
    with pytest.raises(ValidationError):
        DimensionScore(dimension=Dimension.PROSE_VOICE, score=score, justification="Justificado.")


def test_puntuacion_sin_justificacion_se_rechaza() -> None:
    with pytest.raises(ValidationError):
        DimensionScore(dimension=Dimension.PROSE_VOICE, score=3, justification="")


def test_defecto_critico_limita_la_puntuacion_a_dos() -> None:
    with pytest.raises(ValidationError, match="no puede superar 2"):
        DimensionScore(
            dimension=Dimension.DRAMATURGY,
            score=3,
            justification="Justificado.",
            critical_defects=["La escena no cambia nada."],
        )


def test_defecto_critico_con_puntuacion_dos_es_valido() -> None:
    item = DimensionScore(
        dimension=Dimension.DRAMATURGY,
        score=2,
        justification="Justificado.",
        critical_defects=["La escena no cambia nada."],
    )
    assert item.score == 2


def test_nota_estilistica_no_limita_la_puntuacion() -> None:
    item = DimensionScore(
        dimension=Dimension.DRAMATURGY,
        score=5,
        justification="Justificado.",
        stylistic_notes=["Preferiría un final más seco."],
    )
    assert item.score == 5
    assert item.critical_defects == []


# ---------------------------------------------------------------------------
# LiteraryEvaluation
# ---------------------------------------------------------------------------


def test_evaluacion_pendiente_valida(valid_evaluation_data: dict[str, Any]) -> None:
    evaluation = LiteraryEvaluation.model_validate(valid_evaluation_data)
    assert evaluation.status == "pendiente"
    assert evaluation.scores == []


def test_evaluacion_pendiente_no_puede_tener_puntuaciones(valid_evaluation_data: dict[str, Any]) -> None:
    valid_evaluation_data["scores"] = [
        {"dimension": "dramaturgia", "score": 3, "justification": "Justificado."}
    ]
    with pytest.raises(ValidationError, match="pendiente"):
        LiteraryEvaluation.model_validate(valid_evaluation_data)


def test_evaluacion_completada_necesita_evaluador(valid_evaluation_data: dict[str, Any]) -> None:
    valid_evaluation_data["status"] = "completada"
    valid_evaluation_data["scores"] = [
        {"dimension": "dramaturgia", "score": 3, "justification": "Justificado."}
    ]
    with pytest.raises(ValidationError, match="evaluador"):
        LiteraryEvaluation.model_validate(valid_evaluation_data)


def test_evaluacion_completada_necesita_puntuaciones(valid_evaluation_data: dict[str, Any]) -> None:
    valid_evaluation_data["status"] = "completada"
    valid_evaluation_data["assessor"] = "revisor humano"
    with pytest.raises(ValidationError, match="puntuaciones"):
        LiteraryEvaluation.model_validate(valid_evaluation_data)


def test_evaluacion_completada_valida(valid_evaluation_data: dict[str, Any]) -> None:
    valid_evaluation_data["status"] = "completada"
    valid_evaluation_data["assessor"] = "revisor humano"
    valid_evaluation_data["scores"] = [
        {"dimension": "dramaturgia", "score": 1, "justification": "Justificado.", "critical_defects": ["Nada cambia."]}
    ]
    evaluation = LiteraryEvaluation.model_validate(valid_evaluation_data)
    assert evaluation.scores[0].score == 1


def test_dimension_puntuada_dos_veces_se_rechaza(valid_evaluation_data: dict[str, Any]) -> None:
    valid_evaluation_data["status"] = "completada"
    valid_evaluation_data["assessor"] = "revisor humano"
    valid_evaluation_data["scores"] = [
        {"dimension": "dramaturgia", "score": 3, "justification": "Uno."},
        {"dimension": "dramaturgia", "score": 4, "justification": "Dos."},
    ]
    with pytest.raises(ValidationError, match="más de una vez"):
        LiteraryEvaluation.model_validate(valid_evaluation_data)


def test_case_id_de_evaluacion_invalido_se_rechaza(valid_evaluation_data: dict[str, Any]) -> None:
    valid_evaluation_data["case_id"] = "Caso Inválido"
    with pytest.raises(ValidationError):
        LiteraryEvaluation.model_validate(valid_evaluation_data)


# ---------------------------------------------------------------------------
# Rubric
# ---------------------------------------------------------------------------


def _rubric_dimension(name: str) -> dict[str, Any]:
    return {
        "dimension": name,
        "label": name,
        "purpose": "Propósito.",
        "levels": [{"level": n, "descriptor": f"Nivel {n}."} for n in range(1, 6)],
        "critical_defects": ["Defecto."],
        "stylistic_preferences": ["Preferencia."],
    }


def _rubric_data() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "name": "Rúbrica de prueba",
        "scale": "1-5",
        "dimensions": [_rubric_dimension(d.value) for d in Dimension],
    }


def test_rubrica_valida_se_acepta() -> None:
    assert len(Rubric.model_validate(_rubric_data()).dimensions) == 5


def test_rubrica_con_niveles_desordenados_se_rechaza() -> None:
    data = _rubric_data()
    data["dimensions"][0]["levels"] = list(reversed(data["dimensions"][0]["levels"]))
    with pytest.raises(ValidationError, match="orden"):
        Rubric.model_validate(data)


def test_rubrica_con_nivel_seis_se_rechaza() -> None:
    data = _rubric_data()
    data["dimensions"][0]["levels"][4]["level"] = 6
    with pytest.raises(ValidationError):
        Rubric.model_validate(data)


def test_rubrica_sin_una_dimension_se_rechaza() -> None:
    data = _rubric_data()
    data["dimensions"][0] = _rubric_dimension("dramaturgia")
    with pytest.raises(ValidationError, match="exactamente una vez"):
        Rubric.model_validate(data)


def test_rubrica_sin_defectos_criticos_se_rechaza() -> None:
    data = _rubric_data()
    data["dimensions"][0]["critical_defects"] = []
    with pytest.raises(ValidationError):
        Rubric.model_validate(data)
