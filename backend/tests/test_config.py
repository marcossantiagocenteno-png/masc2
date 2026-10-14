"""Pruebas de la configuración por entorno."""

from __future__ import annotations

import pytest

from app.config import (
    DEFAULT_CORS_ORIGINS,
    DEFAULT_DATABASE_URL,
    DEFAULT_MAX_VERSION_CHARS,
    Settings,
    load_settings,
)


def test_valores_por_defecto() -> None:
    settings = load_settings({})
    assert settings.database_url == DEFAULT_DATABASE_URL
    assert settings.max_version_chars == 500_000 == DEFAULT_MAX_VERSION_CHARS
    assert settings.cors_origins == DEFAULT_CORS_ORIGINS


def test_database_url_por_defecto_es_sqlite_en_data() -> None:
    assert DEFAULT_DATABASE_URL.startswith("sqlite:///")
    assert DEFAULT_DATABASE_URL.endswith("/data/novel_engine.sqlite")


def test_variables_de_entorno_sobrescriben_los_valores() -> None:
    settings = load_settings(
        {
            "DATABASE_URL": "sqlite:////tmp/otra.sqlite",
            "NOVEL_ENGINE_MAX_VERSION_CHARS": "1234",
            "NOVEL_ENGINE_CORS_ORIGINS": "http://a.test, http://b.test",
        }
    )
    assert settings.database_url == "sqlite:////tmp/otra.sqlite"
    assert settings.max_version_chars == 1234
    assert settings.cors_origins == ("http://a.test", "http://b.test")


def test_limite_no_entero_se_rechaza() -> None:
    with pytest.raises(ValueError, match="entero"):
        load_settings({"NOVEL_ENGINE_MAX_VERSION_CHARS": "mucho"})


@pytest.mark.parametrize("value", ["0", "-5"])
def test_limite_no_positivo_se_rechaza(value: str) -> None:
    with pytest.raises(ValueError, match="positivo"):
        load_settings({"NOVEL_ENGINE_MAX_VERSION_CHARS": value})


def test_settings_directos_validan_el_limite() -> None:
    with pytest.raises(ValueError):
        Settings(max_version_chars=0)


def test_proveedor_de_analisis_por_defecto_es_simulado() -> None:
    settings = load_settings({})
    assert settings.analysis_provider == "simulado"
    assert settings.max_analysis_chars == 8_000


def test_variables_de_analisis_se_leen() -> None:
    settings = load_settings(
        {"NOVEL_ENGINE_ANALYSIS_PROVIDER": "openai", "NOVEL_ENGINE_MAX_ANALYSIS_CHARS": "500"}
    )
    assert settings.analysis_provider == "openai"
    assert settings.max_analysis_chars == 500


def test_limite_de_analisis_no_positivo_se_rechaza() -> None:
    with pytest.raises(ValueError):
        Settings(max_analysis_chars=0)
