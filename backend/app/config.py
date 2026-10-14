"""Configuración de Novel Engine desde variables de entorno.

Variables:

- ``DATABASE_URL``: URL de SQLAlchemy. Por defecto, un archivo SQLite en ``data/``.
  Solo SQLite está probado. Otras URL se aceptan por configuración, pero las
  migraciones solo saben crear la protección de inmutabilidad en SQLite.
- ``NOVEL_ENGINE_MAX_VERSION_CHARS``: límite de caracteres por versión, tras
  normalizar el texto. Por defecto, 500.000.
- ``NOVEL_ENGINE_CORS_ORIGINS``: orígenes permitidos, separados por comas.
- ``NOVEL_ENGINE_ANALYSIS_PROVIDER``: proveedor de análisis. Por defecto,
  ``simulado``. Ningún otro valor está autorizado en esta versión.
- ``NOVEL_ENGINE_MAX_ANALYSIS_CHARS``: tamaño máximo de un fragmento a analizar.
  Por defecto, 8.000.
- ``ANTHROPIC_API_KEY``: clave de la API de Anthropic. Solo se lee aquí. Nunca
  aparece en ``repr``, respuestas HTTP ni logs.
- ``NOVEL_ENGINE_ANTHROPIC_MODEL``: identificador del modelo. No tiene valor por
  defecto: debe ser uno que tu cuenta admita (ver README).
- ``NOVEL_ENGINE_ANTHROPIC_TIMEOUT_SECONDS``: tiempo máximo por llamada. Por defecto, 60.
- ``NOVEL_ENGINE_ANTHROPIC_MAX_OUTPUT_TOKENS``: límite de tokens de salida. Por defecto, 2000.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = REPO_ROOT / "data" / "novel_engine.sqlite"
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_DATABASE_PATH.as_posix()}"
DEFAULT_MAX_VERSION_CHARS = 500_000
DEFAULT_CORS_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")
DEFAULT_ANALYSIS_PROVIDER = "simulado"
DEFAULT_MAX_ANALYSIS_CHARS = 8_000
DEFAULT_ANTHROPIC_TIMEOUT_SECONDS = 60.0
DEFAULT_ANTHROPIC_MAX_OUTPUT_TOKENS = 2_000


@dataclass(frozen=True)
class Settings:
    """Configuración inmutable de la aplicación."""

    database_url: str = DEFAULT_DATABASE_URL
    max_version_chars: int = DEFAULT_MAX_VERSION_CHARS
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    analysis_provider: str = DEFAULT_ANALYSIS_PROVIDER
    max_analysis_chars: int = DEFAULT_MAX_ANALYSIS_CHARS
    # ``repr=False``: la clave no debe aparecer al imprimir o registrar la configuración.
    anthropic_api_key: str | None = field(default=None, repr=False)
    anthropic_model: str | None = None
    anthropic_timeout_seconds: float = DEFAULT_ANTHROPIC_TIMEOUT_SECONDS
    anthropic_max_output_tokens: int = DEFAULT_ANTHROPIC_MAX_OUTPUT_TOKENS

    def __post_init__(self) -> None:
        if self.max_version_chars < 1:
            raise ValueError("max_version_chars debe ser un entero positivo")
        if self.max_analysis_chars < 1:
            raise ValueError("max_analysis_chars debe ser un entero positivo")
        if self.anthropic_timeout_seconds <= 0:
            raise ValueError("anthropic_timeout_seconds debe ser positivo")
        if not 1 <= self.anthropic_max_output_tokens <= 8_192:
            raise ValueError("anthropic_max_output_tokens debe estar entre 1 y 8192")
        if not self.database_url.strip():
            raise ValueError("database_url no puede estar vacío")


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Lee la configuración del entorno. Lanza ``ValueError`` si un valor no es válido."""
    source = os.environ if env is None else env

    database_url = source.get("DATABASE_URL", "").strip() or DEFAULT_DATABASE_URL

    raw_limit = source.get("NOVEL_ENGINE_MAX_VERSION_CHARS", "").strip()
    if raw_limit:
        try:
            max_chars = int(raw_limit)
        except ValueError as error:
            raise ValueError("NOVEL_ENGINE_MAX_VERSION_CHARS debe ser un entero") from error
    else:
        max_chars = DEFAULT_MAX_VERSION_CHARS

    raw_origins = source.get("NOVEL_ENGINE_CORS_ORIGINS", "").strip()
    origins = (
        tuple(item.strip() for item in raw_origins.split(",") if item.strip())
        if raw_origins
        else DEFAULT_CORS_ORIGINS
    )

    provider = source.get("NOVEL_ENGINE_ANALYSIS_PROVIDER", "").strip() or DEFAULT_ANALYSIS_PROVIDER

    raw_analysis_limit = source.get("NOVEL_ENGINE_MAX_ANALYSIS_CHARS", "").strip()
    if raw_analysis_limit:
        try:
            analysis_limit = int(raw_analysis_limit)
        except ValueError as error:
            raise ValueError("NOVEL_ENGINE_MAX_ANALYSIS_CHARS debe ser un entero") from error
    else:
        analysis_limit = DEFAULT_MAX_ANALYSIS_CHARS

    api_key = source.get("ANTHROPIC_API_KEY", "").strip() or None
    model = source.get("NOVEL_ENGINE_ANTHROPIC_MODEL", "").strip() or None
    timeout = _float_or_default(source, "NOVEL_ENGINE_ANTHROPIC_TIMEOUT_SECONDS", DEFAULT_ANTHROPIC_TIMEOUT_SECONDS)
    max_tokens = _int_or_default(
        source, "NOVEL_ENGINE_ANTHROPIC_MAX_OUTPUT_TOKENS", DEFAULT_ANTHROPIC_MAX_OUTPUT_TOKENS
    )

    return Settings(
        database_url=database_url,
        max_version_chars=max_chars,
        cors_origins=origins,
        analysis_provider=provider,
        max_analysis_chars=analysis_limit,
        anthropic_api_key=api_key,
        anthropic_model=model,
        anthropic_timeout_seconds=timeout,
        anthropic_max_output_tokens=max_tokens,
    )


def _int_or_default(source: Mapping[str, str], name: str, default: int) -> int:
    raw = source.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as error:
        raise ValueError(f"{name} debe ser un entero") from error


def _float_or_default(source: Mapping[str, str], name: str, default: float) -> float:
    raw = source.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as error:
        raise ValueError(f"{name} debe ser un número") from error
