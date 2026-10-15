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
- ``NOVEL_ENGINE_BACKUP_DIR``: carpeta de las copias de seguridad, separada de la base. Por defecto, ``data/backups``.
- ``NOVEL_ENGINE_BACKUP_INTERVAL_MINUTES``: frecuencia de copias automáticas mientras corre el backend. Por defecto, 60. ``0`` las desactiva.
- ``NOVEL_ENGINE_BACKUP_KEEP``: número máximo de copias conservadas. Por defecto, 14.
- ``NOVEL_ENGINE_BACKUP_MIN_KEEP``: copias que nunca se borran por antigüedad. Por defecto, 3.
- ``NOVEL_ENGINE_BACKUP_MAX_AGE_DAYS``: antigüedad a partir de la cual se borra una copia (si quedan más de ``MIN_KEEP``). Por defecto, 30.
- ``NOVEL_ENGINE_RETENTION_KEEP_PER_MANUSCRIPT``: puntos de recuperación recientes que siempre se conservan por manuscrito. Por defecto, 20.
- ``NOVEL_ENGINE_RETENTION_MIN_AGE_DAYS``: antigüedad mínima de un punto para que sea candidato a limpieza. Por defecto, 90.
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
DEFAULT_ASSISTANT_PROVIDER = "simulado"
DEFAULT_ASSISTANT_MAX_CONTEXT_CHARS = 15_000
DEFAULT_MAX_ANALYSIS_CHARS = 8_000
DEFAULT_ANTHROPIC_TIMEOUT_SECONDS = 60.0
DEFAULT_ANTHROPIC_MAX_OUTPUT_TOKENS = 2_000
DEFAULT_BACKUP_DIR = REPO_ROOT / "data" / "backups"
DEFAULT_BACKUP_INTERVAL_MINUTES = 60
DEFAULT_BACKUP_KEEP = 14
DEFAULT_BACKUP_MIN_KEEP = 3
DEFAULT_BACKUP_MAX_AGE_DAYS = 30
DEFAULT_RETENTION_KEEP_PER_MANUSCRIPT = 20
DEFAULT_RETENTION_MIN_AGE_DAYS = 90


@dataclass(frozen=True)
class Settings:
    """Configuración inmutable de la aplicación."""

    database_url: str = DEFAULT_DATABASE_URL
    max_version_chars: int = DEFAULT_MAX_VERSION_CHARS
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    analysis_provider: str = DEFAULT_ANALYSIS_PROVIDER
    # Asistente conversacional: "simulado" (reglas locales, sin llamadas externas) o "anthropic".
    assistant_provider: str = DEFAULT_ASSISTANT_PROVIDER
    assistant_max_context_chars: int = DEFAULT_ASSISTANT_MAX_CONTEXT_CHARS
    max_analysis_chars: int = DEFAULT_MAX_ANALYSIS_CHARS
    # ``repr=False``: la clave no debe aparecer al imprimir o registrar la configuración.
    anthropic_api_key: str | None = field(default=None, repr=False)
    anthropic_model: str | None = None
    anthropic_timeout_seconds: float = DEFAULT_ANTHROPIC_TIMEOUT_SECONDS
    anthropic_max_output_tokens: int = DEFAULT_ANTHROPIC_MAX_OUTPUT_TOKENS
    # ``None`` desactiva las copias: las pruebas no escriben en disco salvo que lo pidan.
    backup_dir: str | None = None
    backup_interval_minutes: int = 0
    backup_keep: int = DEFAULT_BACKUP_KEEP
    backup_min_keep: int = DEFAULT_BACKUP_MIN_KEEP
    backup_max_age_days: int = DEFAULT_BACKUP_MAX_AGE_DAYS
    retention_keep_per_manuscript: int = DEFAULT_RETENTION_KEEP_PER_MANUSCRIPT
    retention_min_age_days: int = DEFAULT_RETENTION_MIN_AGE_DAYS

    def __post_init__(self) -> None:
        if self.backup_interval_minutes < 0:
            raise ValueError("backup_interval_minutes no puede ser negativo")
        if not 1 <= self.backup_min_keep <= self.backup_keep:
            raise ValueError("se exige 1 <= backup_min_keep <= backup_keep")
        if self.backup_max_age_days < 1:
            raise ValueError("backup_max_age_days debe ser al menos 1")
        if self.retention_keep_per_manuscript < 1 or self.retention_min_age_days < 0:
            raise ValueError("los parámetros de retención deben ser positivos")
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

    backup_dir = source.get("NOVEL_ENGINE_BACKUP_DIR", "").strip() or str(DEFAULT_BACKUP_DIR)

    return Settings(
        backup_dir=backup_dir,
        backup_interval_minutes=_int_or_default(
            source, "NOVEL_ENGINE_BACKUP_INTERVAL_MINUTES", DEFAULT_BACKUP_INTERVAL_MINUTES
        ),
        backup_keep=_int_or_default(source, "NOVEL_ENGINE_BACKUP_KEEP", DEFAULT_BACKUP_KEEP),
        backup_min_keep=_int_or_default(source, "NOVEL_ENGINE_BACKUP_MIN_KEEP", DEFAULT_BACKUP_MIN_KEEP),
        backup_max_age_days=_int_or_default(
            source, "NOVEL_ENGINE_BACKUP_MAX_AGE_DAYS", DEFAULT_BACKUP_MAX_AGE_DAYS
        ),
        retention_keep_per_manuscript=_int_or_default(
            source, "NOVEL_ENGINE_RETENTION_KEEP_PER_MANUSCRIPT", DEFAULT_RETENTION_KEEP_PER_MANUSCRIPT
        ),
        retention_min_age_days=_int_or_default(
            source, "NOVEL_ENGINE_RETENTION_MIN_AGE_DAYS", DEFAULT_RETENTION_MIN_AGE_DAYS
        ),
        database_url=database_url,
        max_version_chars=max_chars,
        cors_origins=origins,
        analysis_provider=provider,
        assistant_provider=source.get("NOVEL_ENGINE_ASSISTANT_PROVIDER", "").strip() or DEFAULT_ASSISTANT_PROVIDER,
        assistant_max_context_chars=_int_or_default(
            source, "NOVEL_ENGINE_ASSISTANT_MAX_CONTEXT_CHARS", DEFAULT_ASSISTANT_MAX_CONTEXT_CHARS
        ),
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
