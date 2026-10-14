"""Borradores persistentes y puntos de recuperación.

Revisión: 0005_borradores_y_recuperacion
Revisión anterior: 0004_proyectos

Solo crea tablas nuevas. No modifica ni elimina datos existentes: versiones
formales, revisiones, análisis y proyectos quedan intactos.

- ``manuscript_drafts``: un borrador por manuscrito (clave única), con contador de revisión.
- ``draft_recovery_points``: copias inmutables del borrador (triggers en SQLite).

La bajada no es automática: borraría borradores y puntos de recuperación que pueden
ser la única copia de trabajo del autor. Para revertir, restaura una copia previa de la
base de datos (docs/RESPALDO_Y_RESTAURACION.md).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0005_borradores_y_recuperacion"
down_revision: str | None = "0004_proyectos"
branch_labels = None
depends_on = None

IMMUTABLE_TABLES = ("draft_recovery_points",)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        raise NotImplementedError(f"Esta migración solo está probada para SQLite; dialecto: {bind.dialect.name}")

    op.create_table(
        "manuscript_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("manuscript_id", sa.Integer(), sa.ForeignKey("manuscripts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "base_version_id",
            sa.Integer(),
            sa.ForeignKey("manuscript_versions.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("manuscript_id", name="uq_draft_manuscript"),
        sa.CheckConstraint("revision >= 1", name="ck_draft_revision_positive"),
    )

    op.create_table(
        "draft_recovery_points",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("manuscript_id", sa.Integer(), sa.ForeignKey("manuscripts.id", ondelete="RESTRICT"), nullable=False),
        # Texto libre a propósito: los motivos válidos viven en app.drafts.reasons.
        sa.Column("reason", sa.String(length=40), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("draft_revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("draft_revision >= 0", name="ck_point_revision_non_negative"),
    )
    op.create_index("ix_draft_recovery_points_manuscript_id", "draft_recovery_points", ["manuscript_id"])

    for table in IMMUTABLE_TABLES:
        for action in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER trg_{table}_no_{action.lower()} "
                f"BEFORE {action} ON {table} "
                f"BEGIN SELECT RAISE(ABORT, '{table} es inmutable'); END"
            )


def downgrade() -> None:
    raise NotImplementedError(
        "La bajada de 0005 no es automática: borraría borradores y puntos de recuperación. "
        "Restaura la copia de la base de datos anterior a la migración (docs/RESPALDO_Y_RESTAURACION.md)."
    )
