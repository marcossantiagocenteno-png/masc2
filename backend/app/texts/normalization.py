"""Normalización del contenido y cálculo del hash de versión.

Toda versión se guarda normalizada: Unicode NFC y saltos de línea ``\\n``.
Así las posiciones de las citas son estables entre plataformas y editores.
"""

from __future__ import annotations

import hashlib
import unicodedata


def normalize_content(raw: str) -> str:
    """Devuelve el texto en NFC con saltos de línea ``\\n``."""
    text = unicodedata.normalize("NFC", raw)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def content_sha256(content: str) -> str:
    """Hash SHA-256 del contenido normalizado, en UTF-8."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
