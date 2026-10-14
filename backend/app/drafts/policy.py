"""Política de puntos de recuperación.

Un punto se crea cuando:

- ``periodico``: han pasado al menos ``PERIODIC_INTERVAL`` desde el último punto
  (o no hay ninguno todavía).
- ``significativo``: el texto ha cambiado al menos ``SIGNIFICANT_CHARS`` caracteres
  respecto al último punto y han pasado al menos ``SIGNIFICANT_MIN_INTERVAL``.

El cambio significativo se mide por diferencia de longitud, no por diferencia de
contenido: es una aproximación barata y suficiente para no crear un punto por
pulsación. Los motivos ``conflicto``, ``antes_de_sobrescribir`` y
``antes_de_restaurar`` no siguen esta política: los crea el servicio cuando ocurren.
"""

from __future__ import annotations

from datetime import datetime, timedelta

PERIODICO = "periodico"
SIGNIFICATIVO = "significativo"
CONFLICTO = "conflicto"
ANTES_DE_RESTAURAR = "antes_de_restaurar"
ANTES_DE_SOBRESCRIBIR = "antes_de_sobrescribir"

REASONS = frozenset({PERIODICO, SIGNIFICATIVO, CONFLICTO, ANTES_DE_RESTAURAR, ANTES_DE_SOBRESCRIBIR})

PERIODIC_INTERVAL = timedelta(minutes=5)
SIGNIFICANT_CHARS = 500
SIGNIFICANT_MIN_INTERVAL = timedelta(seconds=60)


def reason_for_new_point(
    last_point: tuple[datetime, int] | None,
    current_chars: int,
    now: datetime,
) -> str | None:
    """Motivo del punto que debe crearse tras un guardado, o ``None`` si no toca.

    ``last_point`` es ``(created_at, char_count)`` del último punto del manuscrito.
    """
    if last_point is None:
        return PERIODICO
    last_at, last_chars = last_point
    elapsed = now - last_at
    if elapsed >= PERIODIC_INTERVAL:
        return PERIODICO
    if elapsed >= SIGNIFICANT_MIN_INTERVAL and abs(current_chars - last_chars) >= SIGNIFICANT_CHARS:
        return SIGNIFICATIVO
    return None
