"""Base declarativa de SQLAlchemy y utilidades de tiempo."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Clase base de todos los modelos persistidos."""


def utc_now() -> datetime:
    """Fecha y hora actual en UTC, sin zona horaria (SQLite no la conserva)."""
    return datetime.now(UTC).replace(tzinfo=None)
