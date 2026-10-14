"""Tablas de textos, versiones inmutables y revisiones editoriales.

Revisión: 0001_textos_y_versiones
Revisión anterior: ninguna

Crea triggers que impiden ``UPDATE`` y ``DELETE`` sobre las versiones, las
revisiones y sus ítems. Solo SQLite está soportado por esta migración: para
otro motor, los triggers deben escribirse de nuevo y probarse antes de usarse.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0001_textos_y_versiones"
down_revision: str | None = None
branch_labels = None
depends_on = None

IMMUTABLE_TABLES = ("manuscript_versions", "editorial_reviews", "review_items")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        raise NotImplementedError(
            f"La inmutabilidad de versiones solo está implementada para SQLite; "
            f"dialecto recibido: {bind.dialect.name}"
        )

    op.create_table(
        "manuscripts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "manuscript_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "manuscript_id",
            sa.Integer(),
            sa.ForeignKey("manuscripts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column(
            "parent_version_id",
            sa.Integer(),
            sa.ForeignKey("manuscript_versions.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("manuscript_id", "number", name="uq_manuscript_version_number"),
        sa.CheckConstraint("number >= 1", name="ck_version_number_positive"),
        sa.CheckConstraint("char_count >= 0", name="ck_version_char_count_non_negative"),
    )
    op.create_index("ix_manuscript_versions_manuscript_id", "manuscript_versions", ["manuscript_id"])

    op.create_table(
        "editorial_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "version_id",
            sa.Integer(),
            sa.ForeignKey("manuscript_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("reviewer", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_editorial_reviews_version_id", "editorial_reviews", ["version_id"])

    op.create_table(
        "review_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "review_id",
            sa.Integer(),
            sa.ForeignKey("editorial_reviews.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "version_id",
            sa.Integer(),
            sa.ForeignKey("manuscript_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # Texto libre a propósito: los tipos válidos viven en app.texts.kinds.
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("inference_basis", sa.Text(), nullable=True),
        sa.Column("suggestion", sa.Text(), nullable=True),
        sa.Column("dimension", sa.String(length=40), nullable=True),
        sa.Column("intent_status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("start_offset >= 0", name="ck_item_start_non_negative"),
        sa.CheckConstraint("end_offset > start_offset", name="ck_item_end_after_start"),
        sa.CheckConstraint("line_number >= 1", name="ck_item_line_positive"),
    )
    op.create_index("ix_review_items_review_id", "review_items", ["review_id"])
    op.create_index("ix_review_items_version_id", "review_items", ["version_id"])

    for table in IMMUTABLE_TABLES:
        for action in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER trg_{table}_no_{action.lower()} "
                f"BEFORE {action} ON {table} "
                f"BEGIN SELECT RAISE(ABORT, '{table} es inmutable'); END"
            )


def downgrade() -> None:
    for table in IMMUTABLE_TABLES:
        for action in ("UPDATE", "DELETE"):
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_{action.lower()}")
    op.drop_index("ix_review_items_version_id", table_name="review_items")
    op.drop_index("ix_review_items_review_id", table_name="review_items")
    op.drop_table("review_items")
    op.drop_index("ix_editorial_reviews_version_id", table_name="editorial_reviews")
    op.drop_table("editorial_reviews")
    op.drop_index("ix_manuscript_versions_manuscript_id", table_name="manuscript_versions")
    op.drop_table("manuscript_versions")
    op.drop_table("manuscripts")
