"""Reglas de validación de hallazgos: citas, procedencia, certeza, efecto e intenciones."""

from __future__ import annotations

import pytest

from app.analysis.provider import ProviderFinding
from app.analysis.validation import find_intent_attribution, validate_finding

FRAGMENT = "La lluvia caía sobre el tejado. Nadie se movió."


def _finding(**overrides: object) -> ProviderFinding:
    data: dict[str, object] = {
        "category": "observacion_literaria",
        "quote": "Nadie se movió.",
        "quote_offset": FRAGMENT.index("Nadie"),
        "explanation": "La frase corta detiene la escena.",
        "effect": "El silencio pesa más que cualquier acción.",
        "certainty": "media",
    }
    data.update(overrides)
    return ProviderFinding(**data)  # type: ignore[arg-type]


def test_hallazgo_valido_pasa() -> None:
    assert validate_finding(_finding(), FRAGMENT, "proveedor") is None


def test_cita_inventada_se_rechaza() -> None:
    # "Nadie se fue." cabe en el fragmento pero no coincide con lo que hay en esa posición.
    reason = validate_finding(_finding(quote="Nadie se fue."), FRAGMENT, "proveedor")
    assert reason is not None and "no coincide exactamente" in reason


def test_cita_con_posicion_incorrecta_se_rechaza() -> None:
    reason = validate_finding(_finding(quote_offset=0), FRAGMENT, "proveedor")
    assert reason is not None and "no coincide exactamente" in reason


def test_cita_fuera_del_fragmento_se_rechaza() -> None:
    reason = validate_finding(_finding(quote_offset=len(FRAGMENT)), FRAGMENT, "proveedor")
    assert reason is not None and "fuera del fragmento" in reason


def test_cita_vacia_se_rechaza() -> None:
    reason = validate_finding(_finding(quote="", quote_offset=0), FRAGMENT, "proveedor")
    assert reason == "la cita está vacía"


def test_observacion_sin_efecto_se_rechaza() -> None:
    reason = validate_finding(_finding(effect=None), FRAGMENT, "proveedor")
    assert reason is not None and "explicar su efecto" in reason


def test_explicacion_vacia_se_rechaza() -> None:
    reason = validate_finding(_finding(explanation="   "), FRAGMENT, "proveedor")
    assert reason == "falta la explicación"


def test_certeza_no_permitida_en_la_categoria_se_rechaza() -> None:
    reason = validate_finding(_finding(certainty="verificable"), FRAGMENT, "proveedor")
    assert reason is not None and "certeza 'verificable' no permitida" in reason


def test_inferencia_no_puede_declararse_con_certeza_alta() -> None:
    reason = validate_finding(_finding(category="inferencia_incierta", certainty="alta"), FRAGMENT, "proveedor")
    assert reason is not None and "no permitida" in reason


def test_inferencia_con_grado_incierto_es_valida() -> None:
    assert validate_finding(
        _finding(category="inferencia_incierta", certainty="baja"), FRAGMENT, "proveedor"
    ) is None


def test_preferencia_de_gusto_solo_admite_no_aplica() -> None:
    assert validate_finding(
        _finding(category="preferencia_de_gusto", certainty="no_aplica", effect=None), FRAGMENT, "proveedor"
    ) is None
    reason = validate_finding(_finding(category="preferencia_de_gusto", certainty="alta"), FRAGMENT, "proveedor")
    assert reason is not None


def test_problema_verificable_no_puede_venir_de_un_proveedor() -> None:
    finding = _finding(category="problema_verificable", certainty="verificable", effect=None)
    reason = validate_finding(finding, FRAGMENT, "proveedor")
    assert reason is not None and "no puede proceder de 'proveedor'" in reason


def test_categoria_desconocida_se_rechaza() -> None:
    reason = validate_finding(_finding(category="ritmo_perfecto"), FRAGMENT, "proveedor")
    assert reason is not None and "no permitida" in reason


@pytest.mark.parametrize(
    "text",
    [
        "El autor quiere que el lector sienta miedo.",
        "La autora pretende denunciar la injusticia.",
        "Su intención del autor era crear tensión.",
        "Lo que la autora quiso decir es evidente.",
    ],
)
def test_atribucion_de_intencion_al_autor_se_rechaza(text: str) -> None:
    assert find_intent_attribution(text) is not None
    reason = validate_finding(_finding(explanation=text), FRAGMENT, "proveedor")
    assert reason is not None and "atribuye intención" in reason


def test_atribucion_en_el_efecto_tambien_se_rechaza() -> None:
    reason = validate_finding(_finding(effect="La autora busca provocar angustia."), FRAGMENT, "proveedor")
    assert reason is not None and "atribuye intención" in reason


@pytest.mark.parametrize(
    "text",
    [
        "La intención de la frase es neutra.",
        "El silencio sostiene la escena sin explicarla.",
        "La frase es breve y no explica el motivo.",
    ],
)
def test_frases_neutras_no_se_confunden_con_atribucion(text: str) -> None:
    assert find_intent_attribution(text) is None
