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


def test_anthropic_sin_variables_no_tiene_clave_ni_modelo_por_defecto() -> None:
    settings = load_settings({})
    assert settings.anthropic_api_key is None
    assert settings.anthropic_model is None  # nunca se inventa un identificador de modelo
    assert settings.anthropic_timeout_seconds == 60.0
    assert settings.anthropic_max_output_tokens == 2000


def test_anthropic_lee_clave_modelo_timeout_y_tokens_del_entorno() -> None:
    settings = load_settings(
        {
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "NOVEL_ENGINE_ANTHROPIC_MODEL": "modelo-de-prueba",
            "NOVEL_ENGINE_ANTHROPIC_TIMEOUT_SECONDS": "15.5",
            "NOVEL_ENGINE_ANTHROPIC_MAX_OUTPUT_TOKENS": "900",
        }
    )
    assert settings.anthropic_api_key == "sk-ant-test"
    assert settings.anthropic_model == "modelo-de-prueba"
    assert settings.anthropic_timeout_seconds == 15.5
    assert settings.anthropic_max_output_tokens == 900


def test_la_clave_no_aparece_en_la_representacion_de_la_configuracion() -> None:
    settings = load_settings({"ANTHROPIC_API_KEY": "sk-ant-SECRETO"})
    assert "SECRETO" not in repr(settings)
    assert "SECRETO" not in str(settings)


@pytest.mark.parametrize(
    "env",
    [
        {"NOVEL_ENGINE_ANTHROPIC_TIMEOUT_SECONDS": "rapido"},
        {"NOVEL_ENGINE_ANTHROPIC_TIMEOUT_SECONDS": "0"},
        {"NOVEL_ENGINE_ANTHROPIC_MAX_OUTPUT_TOKENS": "0"},
        {"NOVEL_ENGINE_ANTHROPIC_MAX_OUTPUT_TOKENS": "99999"},
        {"NOVEL_ENGINE_ANTHROPIC_MAX_OUTPUT_TOKENS": "mucho"},
    ],
)
def test_limites_de_anthropic_fuera_de_rango_se_rechazan(env: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        load_settings(env)
