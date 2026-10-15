"""Asistente conversacional y propuestas de cambio (chat global del proyecto).

Revisión: 0012_asistente
Revisión anterior: 0011_recomendaciones_estructura

Cambio aditivo: cuatro tablas nuevas, sin tocar ninguna existente.

- ``assistant_conversations`` y ``assistant_messages``: historial del chat, por proyecto.
- ``assistant_proposals``: cambios propuestos por el asistente. No modifican datos hasta su aprobación.
- ``assistant_memory_items``: memoria narrativa (confirmado, propuesta, pendiente, rechazada, contradicción).

No hay bajada automática: la recuperación es la copia de seguridad verificada (ver docs/MIGRACION_LOCAL.md).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0012_asistente"
down_revision: str | None = "0011_recomendaciones_estructura"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_assistant_conversations_project_id", "assistant_conversations", ["project_id"])

    op.create_table(
        "assistant_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("assistant_conversations.id"), nullable=False),
        sa.Column("client_id", sa.String(64), nullable=True),
        sa.Column("role", sa.String(12), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("proveedor", sa.String(40), nullable=True),
        sa.Column("simulado", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("role IN ('usuario', 'asistente', 'sistema')", name="ck_assistant_messages_role"),
        sa.UniqueConstraint("conversation_id", "client_id", name="uq_assistant_messages_client"),
    )
    op.create_index("ix_assistant_messages_project_id", "assistant_messages", ["project_id"])
    op.create_index("ix_assistant_messages_conversation_id", "assistant_messages", ["conversation_id"])

    op.create_table(
        "assistant_proposals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("assistant_conversations.id"), nullable=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("assistant_messages.id"), nullable=True),
        sa.Column("operacion", sa.String(12), nullable=False),
        sa.Column("entidad", sa.String(20), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("datos", sa.Text(), nullable=False),
        sa.Column("base_snapshot", sa.String(64), nullable=True),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.Column("dependencias", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("estado", sa.String(20), nullable=False, server_default="pendiente"),
        sa.Column("resultado", sa.Text(), nullable=True),
        sa.Column("resultado_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("operacion IN ('crear', 'actualizar')", name="ck_assistant_proposals_operacion"),
        sa.CheckConstraint(
            "entidad IN ('personaje', 'lugar', 'elemento_trama', 'acontecimiento', 'premisa')",
            name="ck_assistant_proposals_entidad",
        ),
        sa.CheckConstraint(
            "estado IN ('pendiente', 'aplicada', 'rechazada', 'fallida', 'desactualizada')",
            name="ck_assistant_proposals_estado",
        ),
    )
    op.create_index("ix_assistant_proposals_project_id", "assistant_proposals", ["project_id"])
    op.create_index("ix_assistant_proposals_project_estado", "assistant_proposals", ["project_id", "estado"])

    op.create_table(
        "assistant_memory_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("proposal_id", sa.Integer(), sa.ForeignKey("assistant_proposals.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('confirmado', 'propuesta', 'idea', 'pendiente', 'contradiccion', 'rechazada')",
            name="ck_assistant_memory_kind",
        ),
    )
    op.create_index("ix_assistant_memory_project_id", "assistant_memory_items", ["project_id"])
    op.create_index("ix_assistant_memory_project_kind", "assistant_memory_items", ["project_id", "kind"])


def downgrade() -> None:
    raise NotImplementedError("La bajada de 0012 no es automática. Restaura la copia de seguridad verificada.")
