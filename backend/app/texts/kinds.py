"""Tipos de ítem editorial permitidos.

Añadir un tipo nuevo consiste en añadir una entrada aquí. La columna
``review_items.kind`` no tiene restricción en la base de datos, así que no
hace falta una migración para el tipo en sí.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ItemKind:
    """Descripción de un tipo de ítem."""

    name: str
    requires_inference_basis: bool


ITEM_KINDS: dict[str, ItemKind] = {
    "observacion": ItemKind(name="observacion", requires_inference_basis=False),
    "inferencia": ItemKind(name="inferencia", requires_inference_basis=True),
}

# Único valor admitido hoy. El evaluador no puede afirmar intenciones del autor.
INTENT_NOT_DECLARED = "no_declarada"
ALLOWED_INTENT_STATUSES: frozenset[str] = frozenset({INTENT_NOT_DECLARED})
