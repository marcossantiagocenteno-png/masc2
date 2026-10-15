"""Valores permitidos de las directrices narrativas. Ninguno viene marcado por defecto: el autor decide.

Son decisiones independientes entre sí. Un valor no implica otros (por ejemplo, la persona no fija el punto de vista).
"""

from __future__ import annotations

from typing import Final, Literal

PERSONAS: Final = ("primera", "segunda", "tercera")
TIEMPOS_VERBALES: Final = ("presente", "pasado", "futuro", "mixto")
TIPOS_NARRADOR: Final = ("narrador_personaje", "narrador_externo")
PUNTOS_DE_VISTA: Final = ("un_personaje", "varios_personajes", "omnisciente")
FOCALIZACIONES: Final = ("interna_fija", "interna_variable", "externa", "omnisciente")

CAMPOS_TEXTO: Final = ("voz", "estilo", "intencion", "limites", "instrucciones")
CAMPOS_VALOR: Final = ("persona", "tiempo_verbal", "tipo_narrador", "punto_de_vista", "focalizacion")
