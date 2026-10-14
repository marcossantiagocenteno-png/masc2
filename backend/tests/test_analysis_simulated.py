"""Analizador simulado: identificado como simulado y limitado a datos estructurales."""

from __future__ import annotations

from app.analysis.categories import CATEGORIES
from app.analysis.provider import resolve_provider
from app.analysis.simulated import LABEL, SimulatedAnalyzer, split_sentences
from app.analysis.validation import validate_finding
from app.texts.errors import TextError
import pytest


def test_se_identifica_como_simulado() -> None:
    analyzer = SimulatedAnalyzer()
    assert analyzer.is_simulated is True
    assert analyzer.name == "simulado"
    assert "SIMULADO" in analyzer.label
    assert analyzer.label == LABEL


def test_solo_produce_datos_estructurales_marcados_como_simulados() -> None:
    fragment = "Llovía. La calle estaba vacía y nadie esperaba el tren de la noche. Esperé."
    findings = SimulatedAnalyzer().analyze(fragment)
    assert findings, "debe producir al menos un hallazgo con fragmento no vacío"
    assert {finding.category for finding in findings} <= {"observacion_literaria", "preferencia_de_gusto"}
    assert all(finding.explanation.startswith("[Simulado]") for finding in findings)


def test_cada_hallazgo_es_valido_frente_a_las_reglas_del_servicio() -> None:
    fragment = "Llovía. La calle estaba vacía y nadie esperaba el tren de la noche. Esperé."
    for finding in SimulatedAnalyzer().analyze(fragment):
        assert validate_finding(finding, fragment, CATEGORIES[finding.category].provenance) is None


def test_la_cita_es_exacta_dentro_del_fragmento() -> None:
    fragment = "Llovía. La calle estaba vacía y nadie esperaba el tren de la noche. Esperé."
    for finding in SimulatedAnalyzer().analyze(fragment):
        assert fragment[finding.quote_offset : finding.quote_offset + len(finding.quote)] == finding.quote


def test_frases_breves_no_se_penalizan() -> None:
    findings = SimulatedAnalyzer().analyze("Sí. No. Nada.")
    assert all(finding.category != "problema_verificable" for finding in findings)
    assert all(finding.certainty != "verificable" for finding in findings)


def test_fragmento_sin_letras_no_produce_hallazgos() -> None:
    assert SimulatedAnalyzer().analyze("... !!! ?") == []


def test_es_determinista() -> None:
    fragment = "Uno. Dos tres cuatro. Cinco."
    assert SimulatedAnalyzer().analyze(fragment) == SimulatedAnalyzer().analyze(fragment)


def test_separacion_de_frases_con_posiciones() -> None:
    sentences = split_sentences("Primera. Segunda frase larga.")
    assert [(s.text, s.start) for s in sentences] == [("Primera.", 0), ("Segunda frase larga.", 9)]


def test_el_simulado_se_resuelve_sin_configuracion() -> None:
    provider = resolve_provider("simulado")
    assert provider.name == "simulado"
    assert provider.is_external is False


def test_anthropic_sin_clave_no_se_resuelve_y_no_revela_nada() -> None:
    with pytest.raises(TextError) as info:
        resolve_provider("anthropic")
    assert info.value.status_code == 503
    assert "falta ANTHROPIC_API_KEY" in str(info.value)


@pytest.mark.parametrize("name", ["openai", "externo", "SIMULADO ", "claude"])
def test_proveedores_no_autorizados_se_rechazan(name: str) -> None:
    with pytest.raises(TextError) as info:
        resolve_provider(name)
    assert info.value.status_code == 503
    assert "no está autorizado" in str(info.value)
