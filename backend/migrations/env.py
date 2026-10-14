"""Entorno de Alembic. Usa la URL de ``app.config`` salvo que se pase explícitamente."""

from __future__ import annotations

from alembic import context

import app.db.models  # noqa: F401  (registra los modelos en Base.metadata)
from app.config import load_settings
from app.db.base import Base
from app.db.session import create_engine_for

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    explicit = config.attributes.get("database_url")
    return explicit or load_settings().database_url


def run_migrations_offline() -> None:
    """Genera SQL sin conectar. Útil para revisar cambios."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica las migraciones sobre una conexión real."""
    engine = create_engine_for(_database_url())
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
