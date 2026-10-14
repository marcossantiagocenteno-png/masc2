"""Normalización del contenido y hash de versión."""

from __future__ import annotations

import unicodedata

from app.texts.normalization import content_sha256, normalize_content


def test_saltos_de_linea_se_normalizan_a_lf() -> None:
    assert normalize_content("a\r\nb\rc\nd") == "a\nb\nc\nd"


def test_unicode_se_normaliza_a_nfc() -> None:
    decomposed = unicodedata.normalize("NFD", "canción")
    assert decomposed != "canción"
    assert normalize_content(decomposed) == "canción"


def test_texto_ya_normalizado_no_cambia() -> None:
    text = "Primera línea.\n\nSegunda línea, con acentos: ñ, á."
    assert normalize_content(text) == text


def test_hash_es_estable_y_cambia_con_el_contenido() -> None:
    assert content_sha256("hola") == content_sha256("hola")
    assert content_sha256("hola") != content_sha256("hola ")
    assert len(content_sha256("hola")) == 64
