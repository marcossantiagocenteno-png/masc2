"""Estado del esquema de la base de datos frente a las migraciones instaladas.

Una base sin migrar hace fallar las rutas que usan tablas nuevas. Esas respuestas de error no llevan cabeceras CORS,
así que el navegador las muestra como fallo de conexión. Este módulo permite detectarlo antes, desde ``/health``
y al arrancar.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine

BACKEND_DIR = Path(__file__).resolve().parents[2]


def revision_esperada() -> str:
    """Revisión más reciente de las migraciones instaladas en este código."""
    script = ScriptDirectory.from_config(Config(str(BACKEND_DIR / "alembic.ini")))
    heads = script.get_heads()
    if len(heads) != 1:
        raise RuntimeError(f"hay varias revisiones finales de migración: {heads}")
    return heads[0]


def estado_del_esquema(engine: Engine) -> dict[str, Any]:
    """Compara la revisión de la base con la esperada. No modifica nada."""
    esperada = revision_esperada()
    try:
        with engine.connect() as connection:
            actual = MigrationContext.configure(connection).get_current_revision()
    except Exception:
        # Sin base accesible no se puede afirmar nada del esquema: se informa como no disponible.
        return {"disponible": False, "revision_actual": None, "revision_esperada": esperada, "al_dia": False}
    return {
        "disponible": True,
        "revision_actual": actual,
        "revision_esperada": esperada,
        "al_dia": actual == esperada,
    }
