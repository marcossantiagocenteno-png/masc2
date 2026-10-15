"""Catálogo de géneros seleccionables. Es una clasificación de la obra, no una estructura ni una convención.

Añadir un género es añadir una entrada aquí: la clave es estable y no debe cambiarse una vez usada. ``otro``
permite conservar cualquier valor libre existente con su texto, sin reinterpretarlo.
"""

from __future__ import annotations

from typing import Final

OTRO: Final = "otro"

GENEROS: Final[tuple[tuple[str, str], ...]] = (
    ("misterio", "Misterio e investigación"),
    ("thriller", "Thriller y suspense"),
    ("romance", "Romance"),
    ("terror", "Terror"),
    ("aventura", "Aventura"),
    ("formacion", "Novela de formación"),
    ("tragedia", "Tragedia"),
    ("fantasia", "Fantasía"),
    ("ciencia_ficcion", "Ciencia ficción"),
    ("historica", "Novela histórica"),
    ("realismo", "Realismo"),
    ("drama", "Drama"),
    ("humor", "Humor"),
)

CLAVES: Final[frozenset[str]] = frozenset(clave for clave, _ in GENEROS) | {OTRO}
ETIQUETAS: Final[dict[str, str]] = {clave: etiqueta for clave, etiqueta in GENEROS}
ETIQUETAS[OTRO] = "Otro"


def catalogo() -> list[dict[str, str]]:
    """Catálogo para la interfaz: clave y etiqueta, en el orden de la tabla."""
    return [{"key": clave, "label": etiqueta} for clave, etiqueta in GENEROS] + [{"key": OTRO, "label": "Otro"}]
