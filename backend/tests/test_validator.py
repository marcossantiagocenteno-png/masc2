"""Pruebas del validador estructural y de la CLI sobre el directorio evals."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from app.benchmark.cli import main, run_validation
from app.benchmark.models import BenchmarkCase, LiteraryEvaluation
from app.benchmark.validator import (
    ValidationReport,
    load_rubric,
    validate_cases,
    validate_evaluation,
    validate_evaluations,
)
from tests.conftest import EVALS_DIR


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_evals(tmp_path: Path) -> Path:
    """Crea un directorio evals vacío con la estructura esperada."""
    for name in ("cases", "rubrics", "reports"):
        (tmp_path / name).mkdir()
    return tmp_path


# ---------------------------------------------------------------------------
# Directorio real del repositorio
# ---------------------------------------------------------------------------


def test_casos_reales_del_repositorio_son_validos() -> None:
    report = ValidationReport()
    cases = validate_cases(EVALS_DIR / "cases", report)
    assert report.ok, report.issues
    assert len(cases) >= 3


def test_todos_los_casos_reales_estan_marcados_como_ficticios() -> None:
    report = ValidationReport()
    cases = validate_cases(EVALS_DIR / "cases", report)
    assert cases
    assert all(case.provenance == "ejemplo_ficticio" for case in cases.values())


def test_rubrica_real_es_valida_y_cubre_cinco_dimensiones() -> None:
    rubric = load_rubric(EVALS_DIR / "rubrics" / "rubrica-literaria-v1.json")
    assert len(rubric.dimensions) == 5


def test_cli_sobre_el_directorio_real_termina_con_cero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--evals-dir", str(EVALS_DIR)]) == 0
    assert "Validación estructural correcta." in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Casos inválidos en un directorio temporal
# ---------------------------------------------------------------------------


def test_caso_con_json_roto_se_reporta_sin_cortar_la_validacion(tmp_path: Path) -> None:
    evals = _make_evals(tmp_path)
    (evals / "cases" / "roto.json").write_text("{no es json", encoding="utf-8")
    report = ValidationReport()
    cases = validate_cases(evals / "cases", report)
    assert cases == {}
    assert not report.ok
    assert report.checked == 1


def test_nombre_de_archivo_debe_coincidir_con_el_id(tmp_path: Path, valid_case_data: dict[str, Any]) -> None:
    evals = _make_evals(tmp_path)
    _write_json(evals / "cases" / "otro-nombre.json", valid_case_data)
    report = ValidationReport()
    validate_cases(evals / "cases", report)
    assert any("debe ser" in issue.message for issue in report.issues)


def test_identificador_duplicado_se_reporta(tmp_path: Path, valid_case_data: dict[str, Any]) -> None:
    evals = _make_evals(tmp_path)
    _write_json(evals / "cases" / "caso-prueba-01.json", valid_case_data)
    _write_json(evals / "cases" / "otro.json", copy.deepcopy(valid_case_data))
    report = ValidationReport()
    cases = validate_cases(evals / "cases", report)
    assert list(cases) == ["caso-prueba-01"]
    assert any("duplicado" in issue.message for issue in report.issues)


def test_cli_devuelve_uno_con_caso_invalido(tmp_path: Path, valid_case_data: dict[str, Any]) -> None:
    evals = _make_evals(tmp_path)
    valid_case_data["provenance"] = "version_aprobada"
    _write_json(evals / "cases" / "caso-prueba-01.json", valid_case_data)
    assert main(["--evals-dir", str(evals)]) == 1


def test_cli_devuelve_uno_si_el_directorio_no_existe(tmp_path: Path) -> None:
    assert main(["--evals-dir", str(tmp_path / "no-existe")]) == 1


# ---------------------------------------------------------------------------
# Evaluaciones frente a su caso
# ---------------------------------------------------------------------------


@pytest.fixture
def case(valid_case_data: dict[str, Any]) -> BenchmarkCase:
    return BenchmarkCase.model_validate(valid_case_data)


def test_evaluacion_pendiente_coherente_no_tiene_problemas(
    case: BenchmarkCase, valid_evaluation_data: dict[str, Any]
) -> None:
    evaluation = LiteraryEvaluation.model_validate(valid_evaluation_data)
    assert validate_evaluation(evaluation, case, source="e.json") == []


def test_evaluacion_de_otro_caso_se_reporta(case: BenchmarkCase, valid_evaluation_data: dict[str, Any]) -> None:
    valid_evaluation_data["case_id"] = "caso-otro-02"
    evaluation = LiteraryEvaluation.model_validate(valid_evaluation_data)
    issues = validate_evaluation(evaluation, case, source="e.json")
    assert len(issues) == 1
    assert "no coincide" in issues[0].message


def test_evaluacion_completada_debe_cubrir_las_dimensiones_del_caso(
    case: BenchmarkCase, valid_evaluation_data: dict[str, Any]
) -> None:
    valid_evaluation_data["status"] = "completada"
    valid_evaluation_data["assessor"] = "revisor humano"
    valid_evaluation_data["scores"] = [
        {"dimension": "continuidad", "score": 4, "justification": "Justificado."}
    ]
    evaluation = LiteraryEvaluation.model_validate(valid_evaluation_data)
    messages = [issue.message for issue in validate_evaluation(evaluation, case, source="e.json")]
    assert any("faltan dimensiones: dramaturgia" in m for m in messages)
    assert any("no evaluadas por el caso: continuidad" in m for m in messages)


def test_evaluaciones_del_directorio_se_cruzan_con_los_casos(
    tmp_path: Path, valid_case_data: dict[str, Any], valid_evaluation_data: dict[str, Any]
) -> None:
    evals = _make_evals(tmp_path)
    _write_json(evals / "cases" / "caso-prueba-01.json", valid_case_data)
    valid_evaluation_data["case_id"] = "caso-inexistente-09"
    _write_json(evals / "reports" / "evaluacion.json", valid_evaluation_data)

    report = ValidationReport()
    cases = validate_cases(evals / "cases", report)
    validate_evaluations(evals / "reports", cases, report)
    assert any("no existe" in issue.message for issue in report.issues)


def test_run_validation_con_evaluacion_pendiente_valida(
    tmp_path: Path,
    valid_case_data: dict[str, Any],
    valid_evaluation_data: dict[str, Any],
) -> None:
    evals = _make_evals(tmp_path)
    _write_json(evals / "cases" / "caso-prueba-01.json", valid_case_data)
    _write_json(evals / "reports" / "evaluacion.json", valid_evaluation_data)
    report = run_validation(evals)
    assert report.ok, report.issues
    assert report.checked == 2
