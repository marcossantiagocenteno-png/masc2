"""Retención de puntos de recuperación: la vista previa nunca borra ni elimina lo irrecuperable.

Se construye un historial con reloj controlado: periódicos, un conflicto y un punto
«antes de sobrescribir». Después se calcula la vista previa en un instante futuro fijado.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from sqlalchemy import func, select

from app.backups.retention import RetentionPolicy, points_in_backup, preview
from app.backups.service import BackupService
from app.config import Settings
from app.db.models import DraftRecoveryPoint
from app.db.session import create_engine_for, create_session_factory
from app.drafts.errors import DraftConflict
from app.drafts.service import DraftService
from app.texts.service import TextService
from tests.backup_fakes import T0, FakeClock


def _build_history(settings: Settings, clock: FakeClock) -> int:
    """Historial: p1 y p2 periódicos, p3 conflicto, p4 antes de sobrescribir (en ese orden)."""
    engine = create_engine_for(settings.database_url)
    try:
        with create_session_factory(engine)() as session:
            manuscript = TextService(session, settings.max_version_chars).create_manuscript("Historial", "Inicio.", None)
            drafts = DraftService(session, settings.max_version_chars, clock)
            drafts.init_draft(manuscript.id)
            drafts.save(manuscript.id, "A", 1)  # p1 periódico (primer guardado)
            clock.advance(minutes=6)
            drafts.save(manuscript.id, "B", 2)  # p2 periódico (más de 5 minutos)
            clock.advance(minutes=6)
            try:
                drafts.save(manuscript.id, "Tardía", 1)  # p3 conflicto
            except DraftConflict:
                pass
            clock.advance(minutes=6)
            drafts.save(manuscript.id, "C", 3, keep_previous=True)  # p4 antes_de_sobrescribir
            return manuscript.id
    finally:
        engine.dispose()


def _points(settings: Settings) -> dict[int, tuple[str, str]]:
    engine = create_engine_for(settings.database_url)
    try:
        with create_session_factory(engine)() as session:
            rows = session.scalars(select(DraftRecoveryPoint)).all()
            return {p.id: (p.reason, p.sha256) for p in rows}
    finally:
        engine.dispose()


def _policy(keep: int = 1, days: int = 90) -> RetentionPolicy:
    return RetentionPolicy(keep_per_manuscript=keep, min_age=timedelta(days=days))


def _preview(settings: Settings, now, policy: RetentionPolicy, backed_up: dict[int, str]):  # type: ignore[no-untyped-def]
    engine = create_engine_for(settings.database_url)
    try:
        with create_session_factory(engine)() as session:
            return preview(session, now, policy, backed_up)
    finally:
        engine.dispose()


def _backup_points(settings: Settings, directory: Path, clock: FakeClock) -> dict[int, str]:
    outcome = BackupService(
        source=Path(settings.database_url.removeprefix("sqlite:///")),
        directory=directory,
        clock=clock,
        keep=5,
        min_keep=1,
        max_age=timedelta(days=30),
    ).run()
    assert outcome.path is not None
    return points_in_backup(outcome.path)


def test_la_vista_previa_no_borra_nada(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    _build_history(settings, clock)
    before = _points(settings)
    backed = _backup_points(settings, tmp_path / "copias", clock)

    result = _preview(settings, T0 + timedelta(days=400), _policy(), backed)

    assert result.candidates  # hay candidatos, pero solo se listan
    assert _points(settings) == before  # ni uno solo se ha eliminado


def test_nunca_son_candidatos_conflictos_ni_puntos_de_sobrescritura(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    _build_history(settings, clock)
    backed = _backup_points(settings, tmp_path / "copias", clock)
    reasons = _points(settings)

    result = _preview(settings, T0 + timedelta(days=400), _policy(keep=1), backed)

    candidate_reasons = {reasons[c.point_id][0] for c in result.candidates}
    assert candidate_reasons <= {"periodico", "significativo"}
    assert result.kept_because.get("motivo protegido (conflicto)") == 1
    assert result.kept_because.get("motivo protegido (antes_de_sobrescribir)") == 1


def test_un_punto_sin_copia_verificada_se_conserva(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    _build_history(settings, clock)

    result = _preview(settings, T0 + timedelta(days=400), _policy(keep=1), backed_up={})

    assert result.candidates == ()
    assert result.kept_because.get("sin copia verificada que lo contenga", 0) >= 2


def test_una_copia_con_otro_hash_no_respalda_el_punto(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    _build_history(settings, clock)
    backed = _backup_points(settings, tmp_path / "copias", clock)
    tampered = {point_id: "0" * 64 for point_id in backed}

    result = _preview(settings, T0 + timedelta(days=400), _policy(keep=1), tampered)

    assert result.candidates == ()


def test_los_mas_recientes_de_cada_manuscrito_se_conservan(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    _build_history(settings, clock)
    backed = _backup_points(settings, tmp_path / "copias", clock)
    newest_per_manuscript = max(_points(settings))

    result = _preview(settings, T0 + timedelta(days=400), _policy(keep=20), backed)

    assert result.candidates == ()  # con 20 recientes por manuscrito no hay candidatos
    assert newest_per_manuscript in _points(settings)


def test_un_punto_reciente_no_es_candidato(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    _build_history(settings, clock)
    backed = _backup_points(settings, tmp_path / "copias", clock)

    result = _preview(settings, clock.now + timedelta(minutes=1), _policy(keep=1, days=90), backed)

    assert result.candidates == ()
    assert result.kept_because.get("reciente", 0) >= 1


def test_las_metricas_describen_el_historial(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    _build_history(settings, clock)

    result = _preview(settings, clock.now, _policy(), backed_up={})

    assert result.points_total == 4
    assert result.points_by_reason == {"periodico": 2, "conflicto": 1, "antes_de_sobrescribir": 1}
    assert result.growth_per_day > 0
    assert result.versions_total == 1
    assert result.drafts_total == 1


def test_no_existe_operacion_de_borrado_en_la_vista_previa() -> None:
    """La limpieza automática queda para otra fase: el módulo no expone ninguna función que borre."""
    from app.backups import retention

    public = {name for name in dir(retention) if not name.startswith("_")}
    assert not {name for name in public if "delete" in name.lower() or "borra" in name.lower() or "purge" in name.lower()}


def test_los_triggers_siguen_impidiendo_borrar_puntos(settings: Settings) -> None:
    """Mantener la inmutabilidad: la base rechaza DELETE sobre los puntos."""
    import sqlite3

    clock = FakeClock()
    _build_history(settings, clock)
    connection = sqlite3.connect(settings.database_url.removeprefix("sqlite:///"))
    try:
        try:
            connection.execute("DELETE FROM draft_recovery_points")
            deleted = True
        except sqlite3.DatabaseError as error:
            deleted = False
            assert "inmutable" in str(error)
    finally:
        connection.close()
    assert deleted is False
