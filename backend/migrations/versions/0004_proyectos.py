"""Proyectos: contenedor aislado de manuscritos.

Revisión: 0004_proyectos
Revisión anterior: 0003_analisis_proveedor_real

- Crea ``projects``.
- Añade ``manuscripts.project_id`` (nulo permitido) con clave foránea.
- Si ya existen manuscritos, crea un proyecto inicial y los asigna a él.
  No se modifica ningún texto ni ninguna versión.

Decisión: la columna se añade con ``ALTER TABLE``, no reconstruyendo
``manuscripts``. Reconstruir esa tabla con versiones que la referencian hace
fallar ``DROP TABLE`` con las claves foráneas activas. Por la misma razón, la
bajada no es automática: se revierte restaurando la copia previa de la base
de datos (ver docs/RESPALDO_Y_RESTAURACION.md).
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0004_proyectos"
down_revision: str | None = "0003_analisis_proveedor_real"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        raise NotImplementedError(f"Esta migración solo está probada para SQLite; dialecto: {bind.dialect.name}")

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('activo', 'archivado')", name="ck_project_status"),
    )
    op.execute(
        "ALTER TABLE manuscripts ADD COLUMN project_id INTEGER "
        "REFERENCES projects (id) ON DELETE RESTRICT"
    )
    op.create_index("ix_manuscripts_project_id", "manuscripts", ["project_id"])

    existing = bind.execute(sa.text("SELECT COUNT(*) FROM manuscripts")).scalar_one()
    if existing:
        now = datetime.now(UTC).replace(tzinfo=None)
        bind.execute(
            sa.text(
                "INSERT INTO projects (name, status, created_at, updated_at) "
                "VALUES ('Proyecto inicial', 'activo', :now, :now)"
            ),
            {"now": now.isoformat(sep=" ")},
        )
        project_id = bind.execute(sa.text("SELECT id FROM projects WHERE name = 'Proyecto inicial'")).scalar_one()
        bind.execute(
            sa.text("UPDATE manuscripts SET project_id = :project_id WHERE project_id IS NULL"),
            {"project_id": project_id},
        )


def downgrade() -> None:
    raise NotImplementedError(
        "La bajada de 0004 no es automática en SQLite: exige reconstruir 'manuscripts'. "
        "Restaura la copia de la base de datos anterior a la migración (docs/RESPALDO_Y_RESTAURACION.md)."
    )
