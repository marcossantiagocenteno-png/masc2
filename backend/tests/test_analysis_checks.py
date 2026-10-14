"""Verificaciones deterministas: solo problemas mecánicos, sin falsos positivos literarios."""

from __future__ import annotations

from app.analysis.checks import run_deterministic_checks


def _categories(fragment: str) -> list[str]:
    return [finding.category for finding in run_deterministic_checks(fragment)]


def test_palabra_funcional_repetida_se_detecta_con_posicion_exacta() -> None:
    fragment = "Dijo que que no lo sabía."
    findings = run_deterministic_checks(fragment)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.category == "problema_verificable"
    assert finding.quote == "que que"
    assert fragment[finding.quote_offset : finding.quote_offset + len(finding.quote)] == "que que"
    assert finding.certainty == "verificable"
    assert finding.effect is None


def test_repeticion_con_puntuacion_entre_ambas_no_se_marca() -> None:
    assert run_deterministic_checks("No, no. Ya lo sé.") == []


def test_repeticion_de_palabra_no_funcional_no_se_marca() -> None:
    # Una repetición de palabra de contenido puede ser un recurso del autor: la regla no la juzga.
    assert run_deterministic_checks("Corría, corría sin mirar atrás.") == []


def test_espacio_doble_entre_palabras_se_detecta() -> None:
    fragment = "Hola  mundo."
    findings = run_deterministic_checks(fragment)
    assert [(f.quote, f.quote_offset) for f in findings] == [("  ", 4)]


def test_sangria_al_inicio_de_linea_no_se_marca() -> None:
    assert run_deterministic_checks("  Inicio de párrafo, con sangría.") == []


def test_guillemets_sin_pareja_se_detectan_en_ambos_sentidos() -> None:
    assert _categories("Dijo «hola y se fue.") == ["problema_verificable"]
    assert _categories("Dijo hola». Se fue.") == ["problema_verificable"]


def test_guillemets_con_pareja_no_se_marcan() -> None:
    assert run_deterministic_checks("Dijo «hola» y se fue.") == []


def test_frases_breves_ambiguedad_y_silencios_no_son_errores() -> None:
    fragment = "Sí. No. Nada. Quizá lo sepa, quizá no. Silencio."
    assert run_deterministic_checks(fragment) == []


def test_resultados_ordenados_por_posicion() -> None:
    fragment = "Dijo que que y «hola de de"
    offsets = [f.quote_offset for f in run_deterministic_checks(fragment)]
    assert offsets == sorted(offsets)
