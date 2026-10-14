"""Simulacro reproducible de restauración y advertencias de crecimiento de la base."""

from __future__ import annotations

from pathlib import Path

from app.backups.drill import run_drill
from app.backups.retention import RetentionPreview, growth_warnings


def test_el_simulacro_completo_pasa_en_una_carpeta_temporal(tmp_path: Path) -> None:
    steps = run_drill(tmp_path / "simulacro")
    failed = [step for step in steps if not step.ok]
    assert failed == []
    assert len(steps) >= 9


def _preview(points: int, per_day: float, chars: int) -> RetentionPreview:
    return RetentionPreview(
        points_total=points,
        points_by_reason={"periodico": points},
        growth_per_day=per_day,
        candidates=(),
        points_chars_total=chars,
    )


def test_sin_crecimiento_ni_base_grande_no_hay_advertencias() -> None:
    assert growth_warnings(_preview(10, 0.5, 5000), database_bytes=1_000_000) == []


def test_una_base_grande_genera_advertencia() -> None:
    warnings = growth_warnings(_preview(10, 0.0, 0), database_bytes=300 * 1024 * 1024)
    assert len(warnings) == 1 and "MB" in warnings[0]


def test_un_crecimiento_anual_grande_genera_advertencia_con_estimacion() -> None:
    # 20 puntos/día de 2.000 caracteres: ~ 20*365*2000*2 bytes ≈ 29 MB/año; con 200 puntos/día, ~290 MB/año.
    warnings = growth_warnings(_preview(100, 200.0, 200_000), database_bytes=1_000_000)
    assert len(warnings) == 1
    assert "al año" in warnings[0]
    assert "no se borran automáticamente" in warnings[0]
