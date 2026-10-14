"""Registro de tipos narrativos: modelos, campos editables, relaciones permitidas y estados de canon.

Ampliar el modelo exige añadir aquí el tipo y, si hace falta, una migración. El resto del
código (servicio, API, validaciones de canon) se aplica a todos los tipos por igual.
"""

from __future__ import annotations

from typing import Final

from app.db.models import Character, NarrativeLink, Place, PlotElement, StructureNode, TimelineEvent

# Estados de canon. Solo el autor puede pasar de propuesta o provisional a canónico.
PROVISIONAL: Final = "provisional"
PROPUESTA: Final = "propuesta_ia"
CANONICO: Final = "canonico"
ESTADOS: Final = (PROVISIONAL, PROPUESTA, CANONICO)

# Origen de la información: quién la creó. Un elemento de origen «ia» nunca cambia a «autor».
ORIGEN_AUTOR: Final = "autor"
ORIGEN_IA: Final = "ia"
ORIGENES: Final = (ORIGEN_AUTOR, ORIGEN_IA)

# Tipos de elemento. Las claves son los nombres que aparecen en la API y en las decisiones.
MODELS: Final = {
    "personaje": Character,
    "lugar": Place,
    "elemento_trama": PlotElement,
    "acontecimiento": TimelineEvent,
    "estructura": StructureNode,
    "vinculo": NarrativeLink,
}

EDITABLE: Final = {
    "personaje": ("name", "description", "goals", "motivations", "conflicts", "evolution", "notes"),
    "lugar": ("name", "description", "features", "notes"),
    "elemento_trama": ("kind", "title", "description", "notes"),
    "acontecimiento": ("title", "description", "narrative_order", "story_time", "notes"),
    "estructura": ("title", "summary", "notes"),
    "vinculo": (),
}

PLOT_KINDS: Final = ("acontecimiento", "conflicto", "subtrama", "misterio", "pregunta_abierta")
STRUCTURE_KINDS: Final = ("acto", "capitulo", "escena")

# Endpoints que pueden participar en un vínculo. «escena» es un nodo de estructura de tipo escena.
LINK_ENDPOINTS: Final = ("personaje", "lugar", "elemento_trama", "acontecimiento", "escena")

# Relaciones permitidas entre dos endpoints. Añadir un par aquí es la única forma de crear un vínculo nuevo.
RELATIONS: Final[dict[tuple[str, str], frozenset[str]]] = {
    ("personaje", "escena"): frozenset({"participa_en"}),
    ("personaje", "acontecimiento"): frozenset({"participa_en"}),
    ("personaje", "elemento_trama"): frozenset({"participa_en"}),
    ("personaje", "lugar"): frozenset({"vinculado_a"}),
    ("lugar", "escena"): frozenset({"ocurre_en"}),
    ("lugar", "acontecimiento"): frozenset({"ocurre_en"}),
    ("acontecimiento", "escena"): frozenset({"aparece_en"}),
    ("acontecimiento", "elemento_trama"): frozenset({"pertenece_a"}),
    ("elemento_trama", "escena"): frozenset({"aparece_en"}),
}

NARRATIVE_FIELDS: Final = ("premise", "synopsis", "genre", "theme", "tone", "development_status")
DEVELOPMENT_STATUSES: Final = ("idea", "planificacion", "escritura", "revision", "terminada")


def allowed_relation(source_kind: str, target_kind: str, relation: str) -> bool:
    return relation in RELATIONS.get((source_kind, target_kind), frozenset())
