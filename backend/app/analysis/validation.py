"""Reglas que todo hallazgo debe cumplir antes de guardarse.

Principios:

- Ninguna cita se acepta si no coincide exactamente con el fragmento en la
  posición indicada.
- Cada categoría admite solo su procedencia y sus certezas.
- Un hallazgo con efecto obligatorio debe explicar su efecto.
- Ningún texto puede atribuir intenciones al autor. Es un filtro léxico:
  reduce el riesgo, no lo elimina.
"""

from __future__ import annotations

import re

from app.analysis.categories import CATEGORIES
from app.analysis.provider import ProviderFinding

MAX_TEXT_CHARS = 2_000

# Frases que atribuyen intención al autor o a la autora. Se rechazan en cualquier hallazgo.
_INTENT_PATTERNS = [
    re.compile(
        r"\b(el|la) autora?\b[^.;]{0,60}\b(quiere|quería|quiso|pretende|pretendía|pretendió|"
        r"intenta|intentaba|intentó|busca|buscaba|desea|deseaba)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(intención|intenciones) (del|de la|de) autora?\b", re.IGNORECASE),
    re.compile(r"\blo que (el|la) autora? quiso\b", re.IGNORECASE),
    re.compile(r"\bel autor (quiere|quería|pretende|pretendía|quiso|intenta|intentaba)\b", re.IGNORECASE),
]


def find_intent_attribution(text: str) -> str | None:
    """Devuelve el fragmento de texto que atribuye intención, o ``None``."""
    for pattern in _INTENT_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


def validate_finding(finding: ProviderFinding, fragment: str, provenance: str) -> str | None:
    """Devuelve el motivo de rechazo, o ``None`` si el hallazgo es válido.

    ``provenance`` es ``determinista`` para las verificaciones y ``proveedor`` para
    cualquier proveedor.
    """
    spec = CATEGORIES.get(finding.category)
    if spec is None:
        return f"categoría no permitida '{finding.category}'"

    if spec.provenance != provenance:
        return (
            f"la categoría '{finding.category}' no puede proceder de '{provenance}'"
        )

    if not finding.quote:
        return "la cita está vacía"
    end = finding.quote_offset + len(finding.quote)
    if finding.quote_offset < 0 or end > len(fragment):
        return "la cita queda fuera del fragmento"
    if fragment[finding.quote_offset : end] != finding.quote:
        return "la cita no coincide exactamente con el fragmento en esa posición"

    explanation = finding.explanation.strip()
    if not explanation:
        return "falta la explicación"
    if len(explanation) > MAX_TEXT_CHARS:
        return "la explicación supera el límite"

    if finding.certainty not in spec.allowed_certainty:
        return (
            f"certeza '{finding.certainty}' no permitida en '{finding.category}'; "
            f"usa una de: {', '.join(sorted(spec.allowed_certainty))}"
        )

    effect = (finding.effect or "").strip()
    if spec.requires_effect and not effect:
        return f"'{finding.category}' necesita explicar su efecto"
    if effect and len(effect) > MAX_TEXT_CHARS:
        return "el efecto supera el límite"

    for text in (explanation, effect):
        attribution = find_intent_attribution(text)
        if attribution:
            return f"atribuye intención al autor: «{attribution}»"

    return None
