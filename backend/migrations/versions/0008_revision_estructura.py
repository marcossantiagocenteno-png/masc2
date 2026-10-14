"""Revisión de la estructura por proyecto (control de concurrencia de la reordenación y los movimientos).

Revisión: 0008_revision_estructura
Revisión anterior: 0007_integridad_planificacion

Por qué una columna nueva: sin ella, dos operaciones sobre la misma estructura pueden leer la vista
anterior y escribir después sobre la posterior, perdiendo la primera. Un contador en la propia fila
del proyecto permite comprobarlo en la misma sentencia que escribe: si cambió desde la lectura, la
operación falla sin cambiar nada.

Cambio aditivo: ``projects.structure_version`` con valor 0 para todos los proyectos existentes.
La bajada no es automática (restaura la copia anterior).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0008_revision_estructura"
down_revision: str | None = "0007_integridad_planificacion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        raise NotImplementedError(f"Esta migración solo está probada para SQLite; dialecto: {bind.dialect.name}")
    op.add_column(
        "projects",
        sa.Column("structure_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    raise NotImplementedError(
        "La bajada de 0008 no es automática. Restaura la copia de la base de datos anterior a la migración "
        "(docs/RESPALDO_Y_RESTAURACION.md)."
    )
