"""Línea de comandos para validar el directorio ``evals``.

Uso desde ``backend/``::

    python -m app.benchmark.cli --evals-dir ../evals

Valida ``cases/*.json``, ``rubrics/*.json`` y ``reports/*.json``. Termina con
código 0 si todo es válido y con código 1 si hay problemas. No ejecuta
ninguna evaluación literaria.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from app.benchmark.validator import (
    ValidationReport,
    load_rubric,
    validate_cases,
    validate_evaluations,
)


def run_validation(evals_dir: Path) -> ValidationReport:
    """Valida casos, rúbricas y evaluaciones de ``evals_dir``."""
    report = ValidationReport()

    rubrics_dir = evals_dir / "rubrics"
    for path in sorted(rubrics_dir.glob("*.json")):
        report.checked += 1
        try:
            load_rubric(path)
        except ValidationError as error:
            for item in error.errors():
                location = ".".join(str(part) for part in item["loc"]) or "(raíz)"
                report.add(path.name, f"{location}: {item['msg']}")

    cases = validate_cases(evals_dir / "cases", report)
    validate_evaluations(evals_dir / "reports", cases, report)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada. Devuelve el código de salida del proceso."""
    parser = argparse.ArgumentParser(
        description="Valida la estructura de casos, rúbricas y evaluaciones.",
    )
    parser.add_argument(
        "--evals-dir",
        type=Path,
        default=Path("../evals"),
        help="Directorio evals (por defecto ../evals, desde backend/).",
    )
    args = parser.parse_args(argv)
    evals_dir: Path = args.evals_dir

    if not evals_dir.is_dir():
        print(f"No existe el directorio: {evals_dir}")
        return 1

    report = run_validation(evals_dir)
    print(f"Archivos revisados: {report.checked}")
    if report.ok:
        print("Validación estructural correcta.")
        return 0
    print(f"Problemas encontrados: {len(report.issues)}")
    for issue in report.issues:
        print(f"- {issue.source}: {issue.message}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
