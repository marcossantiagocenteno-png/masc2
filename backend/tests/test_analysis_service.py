"""Servicio de análisis: persistencia, rechazo atómico y conservación del texto original."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.analysis.categories import PROVENANCE_DETERMINISTIC
from app.analysis.errors import FindingsRejected, ProviderFailed
from app.analysis.provider import ProviderFinding
from app.analysis.service import AnalysisService
from app.analysis.simulated import SimulatedAnalyzer
from app.config import Settings
from app.db.models import AnalysisFinding, AnalysisRun
from app.texts.errors import ContentTooLarge, IntegrityFailure, ValidationFailed
from app.texts.service import TextService
from tests.analysis_fakes import FailingProvider, ScriptedProvider, observation

CONTENT = (
    "La lluvia caía sobre el tejado. Dijo que que no lo sabía.\n"
    "Nadie se movió durante largo rato."
)


@pytest.fixture
def texts(session: Session, settings: Settings) -> TextService:
    return TextService(session, max_version_chars=settings.max_version_chars)


@pytest.fixture
def analysis(session: Session, texts: TextService) -> AnalysisService:
    return AnalysisService(session, texts, max_analysis_chars=200)


@pytest.fixture
def version_id(texts: TextService) -> int:
    manuscript = texts.create_manuscript("Análisis", CONTENT, None)
    return texts.list_versions(manuscript.id)[0].id


def _count(session: Session, model: type) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


# ---------------------------------------------------------------------------
# Persistencia y posiciones
# ---------------------------------------------------------------------------


def test_analisis_guarda_fragmento_proveedor_y_hallazgos(
    analysis: AnalysisService, texts: TextService, version_id: int
) -> None:
    start = 0
    end = len(CONTENT)
    run = analysis.analyze(version_id, start, end, SimulatedAnalyzer())

    assert run.fragment_text == CONTENT[start:end]
    assert run.provider_name == "simulado"
    assert run.provider_simulated is True
    assert "SIMULADO" in run.provider_label
    assert run.findings, "el simulador y las verificaciones deben producir hallazgos"


def test_posiciones_de_hallazgos_son_absolutas_y_la_linea_es_correcta(
    analysis: AnalysisService, version_id: int
) -> None:
    run = analysis.analyze(version_id, 0, len(CONTENT), ScriptedProvider(lambda f: []))
    problem = next(item for item in run.findings if item.category == "problema_verificable")
    assert CONTENT[problem.start_offset : problem.end_offset] == problem.quote == "que que"
    assert problem.line_number == 1
    assert problem.provenance == PROVENANCE_DETERMINISTIC
    assert problem.source_name == "verificacion_determinista"


def test_hallazgo_del_proveedor_en_segunda_linea_tiene_su_numero_de_linea(
    analysis: AnalysisService, version_id: int
) -> None:
    provider = ScriptedProvider(lambda f: [observation(f, "Nadie se movió durante largo rato.")])
    run = analysis.analyze(version_id, 0, len(CONTENT), provider)
    finding = next(item for item in run.findings if item.category == "observacion_literaria")
    assert finding.line_number == 2
    assert CONTENT[finding.start_offset : finding.end_offset] == finding.quote
    assert finding.source_name == "doble-de-prueba"


def test_listado_devuelve_solo_los_analisis_de_su_version(
    session: Session, texts: TextService, analysis: AnalysisService, version_id: int
) -> None:
    analysis.analyze(version_id, 0, 10, SimulatedAnalyzer())
    other = texts.add_version(texts.get_version(version_id).manuscript_id, "Otra versión.", None, None)
    assert len(analysis.list_runs(version_id)) == 1
    assert analysis.list_runs(other.id) == []


# ---------------------------------------------------------------------------
# Rechazo atómico: citas inventadas, evidencia ausente, fallos del proveedor
# ---------------------------------------------------------------------------


def test_cita_inventada_rechaza_el_lote_entero_sin_guardar_nada(
    session: Session, analysis: AnalysisService, version_id: int
) -> None:
    def invented(fragment: str) -> list[ProviderFinding]:
        return [observation(fragment, "Esta frase no existe.", offset=0)]

    with pytest.raises(FindingsRejected, match="no coincide exactamente"):
        analysis.analyze(version_id, 0, len(CONTENT), ScriptedProvider(invented))

    # Aunque las verificaciones deterministas sí eran válidas, no se guarda nada.
    assert _count(session, AnalysisRun) == 0
    assert _count(session, AnalysisFinding) == 0


def test_observacion_sin_efecto_se_rechaza(session: Session, analysis: AnalysisService, version_id: int) -> None:
    def no_effect(fragment: str) -> list[ProviderFinding]:
        return [observation(fragment, "Nadie se movió durante largo rato.", effect=None)]

    with pytest.raises(FindingsRejected, match="explicar su efecto"):
        analysis.analyze(version_id, 0, len(CONTENT), ScriptedProvider(no_effect))
    assert _count(session, AnalysisRun) == 0


def test_observacion_sin_cita_se_rechaza(session: Session, analysis: AnalysisService, version_id: int) -> None:
    def empty_quote(fragment: str) -> list[ProviderFinding]:
        return [observation(fragment, "", offset=0)]

    with pytest.raises(FindingsRejected, match="cita está vacía"):
        analysis.analyze(version_id, 0, len(CONTENT), ScriptedProvider(empty_quote))
    assert _count(session, AnalysisRun) == 0


def test_proveedor_no_puede_producir_problemas_verificables(
    session: Session, analysis: AnalysisService, version_id: int
) -> None:
    def fake_problem(fragment: str) -> list[ProviderFinding]:
        return [
            ProviderFinding(
                category="problema_verificable",
                quote="Nadie",
                quote_offset=fragment.index("Nadie"),
                explanation="Problema inventado por el proveedor.",
                effect=None,
                certainty="verificable",
            )
        ]

    with pytest.raises(FindingsRejected, match="no puede proceder de 'proveedor'"):
        analysis.analyze(version_id, 0, len(CONTENT), ScriptedProvider(fake_problem))
    assert _count(session, AnalysisRun) == 0


def test_atribucion_de_intencion_en_el_proveedor_se_rechaza(
    session: Session, analysis: AnalysisService, version_id: int
) -> None:
    def attributes(fragment: str) -> list[ProviderFinding]:
        return [observation(fragment, "Nadie se movió durante largo rato.", explanation="El autor quiere angustia.")]

    with pytest.raises(FindingsRejected, match="atribuye intención"):
        analysis.analyze(version_id, 0, len(CONTENT), ScriptedProvider(attributes))
    assert _count(session, AnalysisRun) == 0


def test_fallo_del_proveedor_no_guarda_nada(session: Session, analysis: AnalysisService, version_id: int) -> None:
    with pytest.raises(ProviderFailed, match="falló"):
        analysis.analyze(version_id, 0, len(CONTENT), FailingProvider())
    assert _count(session, AnalysisRun) == 0


# ---------------------------------------------------------------------------
# Rangos y límites
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("start,end", [(5, 5), (10, 3), (-1, 4), (0, len(CONTENT) + 1)])
def test_rango_de_fragmento_no_valido_se_rechaza(
    analysis: AnalysisService, version_id: int, start: int, end: int
) -> None:
    with pytest.raises(ValidationFailed, match="rango de fragmento no válido"):
        analysis.analyze(version_id, start, end, SimulatedAnalyzer())


def test_fragmento_demasiado_grande_se_rechaza(texts: TextService, analysis: AnalysisService) -> None:
    long_manuscript = texts.create_manuscript("Largo", "a" * 300, None)
    long_version = texts.list_versions(long_manuscript.id)[0]
    with pytest.raises(ContentTooLarge, match="el máximo es 200"):
        analysis.analyze(long_version.id, 0, 201, SimulatedAnalyzer())


# ---------------------------------------------------------------------------
# Conservación del original y de la persistencia
# ---------------------------------------------------------------------------


def test_analizar_no_modifica_la_version_original(
    analysis: AnalysisService, texts: TextService, version_id: int
) -> None:
    before = texts.get_version(version_id)
    before_content, before_hash = before.content, before.sha256
    analysis.analyze(version_id, 0, len(CONTENT), SimulatedAnalyzer())
    after = texts.get_version(version_id)
    assert after.content == before_content == CONTENT
    assert after.sha256 == before_hash


def test_los_analisis_no_se_pueden_modificar_ni_borrar_en_sql(
    session: Session, analysis: AnalysisService, version_id: int
) -> None:
    run = analysis.analyze(version_id, 0, 20, SimulatedAnalyzer())
    with pytest.raises(IntegrityError, match="inmutable"):
        session.execute(text("UPDATE analysis_findings SET explanation = 'x' WHERE run_id = :id"), {"id": run.id})
        session.commit()
    session.rollback()
    with pytest.raises(IntegrityError, match="inmutable"):
        session.execute(text("DELETE FROM analysis_runs WHERE id = :id"), {"id": run.id})
        session.commit()
    session.rollback()


def test_fragmento_alterado_se_detecta_al_leer(
    session: Session,
    session_factory: sessionmaker[Session],
    settings: Settings,
    analysis: AnalysisService,
    version_id: int,
) -> None:
    run = analysis.analyze(version_id, 0, 20, SimulatedAnalyzer())

    # Simulación de manipulación: se desactiva el trigger solo dentro de esta prueba.
    session.execute(text("DROP TRIGGER trg_analysis_runs_no_update"))
    session.execute(text("UPDATE analysis_runs SET fragment_text = 'alterado' WHERE id = :id"), {"id": run.id})
    session.commit()

    with session_factory() as fresh:
        fresh_service = AnalysisService(
            fresh,
            TextService(fresh, max_version_chars=settings.max_version_chars),
            max_analysis_chars=settings.max_analysis_chars,
        )
        with pytest.raises(IntegrityFailure, match="no coincide"):
            fresh_service.list_runs(version_id)
