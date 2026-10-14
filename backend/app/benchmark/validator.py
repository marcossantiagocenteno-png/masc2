"""Validación estructural de casos, evaluaciones y rúbrica.

El validador comprueba que los archivos cumplan los modelos y que sean
coherentes entre sí: identificadores únicos, nombre de archivo igual al
identificador y dimensiones de cada evaluación iguales a las del caso.
No puntúa nada ni infiere calidad literaria.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from app.benchmark.models import BenchmarkCase, LiteraryEvaluation, Rubric


class ValidationIssue(BaseModel):
    """Un problema encontrado en un archivo o en una relación entre archivos."""

    source: str
    message: str


class ValidationReport(BaseModel):
    """Resultado acumulado de una validación. Ningún error corta el proceso."""

    checked: int = 0
    issues: list[ValidationIssue] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Verdadero si no hay ningún problema."""
        return not self.issues

    def add(self, source: str, message: str) -> None:
        """Registra un problema asociado a una fuente (archivo o identificador)."""
        self.issues.append(ValidationIssue(source=source, message=message))


def _format_pydantic_errors(error: ValidationError) -> list[str]:
    """Convierte errores de Pydantic en frases legibles."""
    messages: list[str] = []
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"]) or "(raíz)"
        messages.append(f"{location}: {item['msg']}")
    return messages


def load_case(path: Path) -> BenchmarkCase:
    """Carga y valida un caso desde un archivo JSON.

    Raises:
        ValidationError: si el contenido no cumple ``BenchmarkCase``.
    """
    return BenchmarkCase.model_validate_json(path.read_text(encoding="utf-8"))


def load_rubric(path: Path) -> Rubric:
    """Carga y valida la rúbrica desde un archivo JSON.

    Raises:
        ValidationError: si el contenido no cumple ``Rubric``.
    """
    return Rubric.model_validate_json(path.read_text(encoding="utf-8"))


def validate_cases(directory: Path, report: ValidationReport) -> dict[str, BenchmarkCase]:
    """Valida todos los casos ``*.json`` de un directorio.

    Comprueba que cada archivo sea válido, que su nombre sea
    ``<id>.json`` y que los identificadores no se repitan.

    Returns:
        Casos válidos indexados por identificador.
    """
    cases: dict[str, BenchmarkCase] = {}
    for path in sorted(directory.glob("*.json")):
        report.checked += 1
        try:
            case = load_case(path)
        except ValidationError as error:
            for message in _format_pydantic_errors(error):
                report.add(path.name, message)
            continue
        if path.stem != case.id:
            report.add(path.name, f"el nombre debe ser '{case.id}.json'")
        if case.id in cases:
            report.add(path.name, f"identificador de caso duplicado: '{case.id}'")
            continue
        cases[case.id] = case
    return cases


def validate_evaluation(
    evaluation: LiteraryEvaluation,
    case: BenchmarkCase,
    source: str,
) -> list[ValidationIssue]:
    """Comprueba que una evaluación sea coherente con su caso.

    Una evaluación completada debe puntuar exactamente las dimensiones
    que el caso declara. Una pendiente solo debe apuntar al caso correcto.
    """
    issues: list[ValidationIssue] = []
    if evaluation.case_id != case.id:
        issues.append(
            ValidationIssue(
                source=source,
                message=f"case_id '{evaluation.case_id}' no coincide con el caso '{case.id}'",
            )
        )
    if evaluation.status == "completada":
        scored = {score.dimension for score in evaluation.scores}
        expected = set(case.dimensions_under_test)
        if scored != expected:
            missing = sorted(d.value for d in expected - scored)
            extra = sorted(d.value for d in scored - expected)
            if missing:
                issues.append(
                    ValidationIssue(source=source, message=f"faltan dimensiones: {', '.join(missing)}")
                )
            if extra:
                issues.append(
                    ValidationIssue(source=source, message=f"dimensiones no evaluadas por el caso: {', '.join(extra)}")
                )
    return issues


def validate_evaluations(
    directory: Path,
    cases: dict[str, BenchmarkCase],
    report: ValidationReport,
) -> None:
    """Valida las evaluaciones ``*.json`` de un directorio contra sus casos."""
    for path in sorted(directory.glob("*.json")):
        report.checked += 1
        try:
            evaluation = LiteraryEvaluation.model_validate_json(path.read_text(encoding="utf-8"))
        except ValidationError as error:
            for message in _format_pydantic_errors(error):
                report.add(path.name, message)
            continue
        case = cases.get(evaluation.case_id)
        if case is None:
            report.add(path.name, f"el caso '{evaluation.case_id}' no existe")
            continue
        for issue in validate_evaluation(evaluation, case, source=path.name):
            report.issues.append(issue)
