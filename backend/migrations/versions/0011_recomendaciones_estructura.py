"""Recomendaciones de estructura y propuestas de actos (F2).

Revisión: 0011_recomendaciones_estructura
Revisión anterior: 0010_generos_y_directrices

Cambio aditivo:
- ``structure_model_choices``: historial de modelos de estructura elegidos. Solo de inserción: los triggers rechazan
  UPDATE y DELETE. El modelo actual es la fila más reciente.
- ``structure_proposals``: etapas propuestas para actos. Se pueden editar mientras están pendientes y se
  aceptan o rechazan; nunca se borran. Los triggers rechazan DELETE. Aceptar una propuesta crea un acto
  provisional en ``structure_nodes``: esta migración no escribe en ``structure_nodes`` ni en ``narrative_decisions``.

No modifica tablas existentes. La bajada no es automática.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0011_recomendaciones_estructura"
down_revision: str | None = "0010_generos_y_directrices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "structure_model_choices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("model_key", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_structure_model_choices_project_id", "structure_model_choices", ["project_id"])
    op.execute(
        "CREATE TRIGGER trg_structure_model_choices_no_update BEFORE UPDATE ON structure_model_choices "
        "BEGIN SELECT RAISE(ABORT, 'structure_model_choices es inmutable'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_structure_model_choices_no_delete BEFORE DELETE ON structure_model_choices "
        "BEGIN SELECT RAISE(ABORT, 'structure_model_choices es inmutable'); END"
    )

    op.create_table(
        "structure_proposals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("lote", sa.Integer(), nullable=False),
        sa.Column("model_key", sa.String(40), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("funcion", sa.Text(), nullable=False),
        sa.Column("pregunta", sa.Text(), nullable=False),
        sa.Column("base_tipo", sa.String(30), nullable=False),
        sa.Column("entradas", sa.Text(), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False, server_default="pendiente"),
        sa.Column("node_id", sa.Integer(), sa.ForeignKey("structure_nodes.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("estado IN ('pendiente', 'aceptada', 'rechazada')", name="ck_structure_proposals_estado"),
        sa.CheckConstraint("position >= 0", name="ck_structure_proposals_position"),
        sa.UniqueConstraint("project_id", "lote", "position", name="uq_structure_proposals_position"),
    )
    op.create_index("ix_structure_proposals_project_id", "structure_proposals", ["project_id"])
    op.execute(
        "CREATE TRIGGER trg_structure_proposals_no_delete BEFORE DELETE ON structure_proposals "
        "BEGIN SELECT RAISE(ABORT, 'structure_proposals no se borra: las propuestas se aceptan o se rechazan'); END"
    )


def downgrade() -> None:
    raise NotImplementedError("La bajada de 0011 no es automática. Restaura la copia anterior a esta migración.")
