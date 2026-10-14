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
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = REPO_ROOT / "data" / "novel_engine.sqlite"
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_DATABASE_PATH.as_posix()}"
DEFAULT_MAX_VERSION_CHARS = 500_000
DEFAULT_CORS_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")
DEFAULT_ANALYSIS_PROVIDER = "simulado"
DEFAULT_MAX_ANALYSIS_CHARS = 8_000


@dataclass(frozen=True)
class Settings:
    """Configuración inmutable de la aplicación."""

    database_url: str = DEFAULT_DATABASE_URL
    max_version_chars: int = DEFAULT_MAX_VERSION_CHARS
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    analysis_provider: str = DEFAULT_ANALYSIS_PROVIDER
    max_analysis_chars: int = DEFAULT_MAX_ANALYSIS_CHARS

    def __post_init__(self) -> None:
        if self.max_version_chars < 1:
            raise ValueError("max_version_chars debe ser un entero positivo")
        if self.max_analysis_chars < 1:
            raise ValueError("max_analysis_chars debe ser un entero positivo")
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

    return Settings(
        database_url=database_url,
        max_version_chars=max_chars,
        cors_origins=origins,
        analysis_provider=provider,
        max_analysis_chars=analysis_limit,
    )
