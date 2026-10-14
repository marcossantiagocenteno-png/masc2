"""Categorías de hallazgo y sus reglas.

Cada categoría define qué certeza admite, si necesita explicar su efecto y
qué procedencia le corresponde. Una categoría no puede producirse desde una
procedencia que no le corresponde: por ejemplo, solo una verificación
determinista puede producir un problema verificable.
"""

from __future__ import annotations

from dataclasses import dataclass

PROVENANCE_DETERMINISTIC = "determinista"
PROVENANCE_PROVIDER = "proveedor"


@dataclass(frozen=True)
class CategorySpec:
    """Reglas de una categoría."""

    name: str
    label: str
    provenance: str
    allowed_certainty: frozenset[str]
    requires_effect: bool


CATEGORIES: dict[str, CategorySpec] = {
    "problema_verificable": CategorySpec(
        name="problema_verificable",
        label="Problemas verificables",
        provenance=PROVENANCE_DETERMINISTIC,
        allowed_certainty=frozenset({"verificable"}),
        requires_effect=False,
    ),
    "observacion_literaria": CategorySpec(
        name="observacion_literaria",
        label="Observaciones literarias",
        provenance=PROVENANCE_PROVIDER,
        allowed_certainty=frozenset({"alta", "media", "baja"}),
        requires_effect=True,
    ),
    "inferencia_incierta": CategorySpec(
        name="inferencia_incierta",
        label="Inferencias inciertas",
        provenance=PROVENANCE_PROVIDER,
        allowed_certainty=frozenset({"media", "baja"}),
        requires_effect=True,
    ),
    "preferencia_de_gusto": CategorySpec(
        name="preferencia_de_gusto",
        label="Preferencias de gusto (no son errores)",
        provenance=PROVENANCE_PROVIDER,
        allowed_certainty=frozenset({"no_aplica"}),
        requires_effect=False,
    ),
    "elemento_a_preservar": CategorySpec(
        name="elemento_a_preservar",
        label="Elementos que funcionan y conviene preservar",
        provenance=PROVENANCE_PROVIDER,
        allowed_certainty=frozenset({"alta", "media", "baja"}),
        requires_effect=True,
    ),
}
