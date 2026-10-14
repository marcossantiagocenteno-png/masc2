"""Análisis editorial de fragmentos: ejecuciones y hallazgos inmutables.

Revisión: 0002_analisis_editorial
Revisión anterior: 0001_textos_y_versiones

Como las versiones, los análisis y sus hallazgos no se modifican ni se borran.
Los triggers son solo para SQLite, igual que en la migración 0001.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0002_analisis_editorial"
down_revision: str | None = "0001_textos_y_versiones"
branch_labels = None
depends_on = None

IMMUTABLE_TABLES = ("analysis_runs", "analysis_findings")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        raise NotImplementedError(
            f"La inmutabilidad de análisis solo está implementada para SQLite; "
            f"dialecto recibido: {bind.dialect.name}"
        )

    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "version_id",
            sa.Integer(),
            sa.ForeignKey("manuscript_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("fragment_start", sa.Integer(), nullable=False),
        sa.Column("fragment_end", sa.Integer(), nullable=False),
        sa.Column("fragment_text", sa.Text(), nullable=False),
        sa.Column("provider_name", sa.String(length=60), nullable=False),
        sa.Column("provider_label", sa.String(length=300), nullable=False),
        sa.Column("provider_simulated", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("fragment_start >= 0", name="ck_analysis_fragment_start_non_negative"),
        sa.CheckConstraint("fragment_end > fragment_start", name="ck_analysis_fragment_end_after_start"),
    )
    op.create_index("ix_analysis_runs_version_id", "analysis_runs", ["version_id"])

    op.create_table(
        "analysis_findings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("analysis_runs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # Texto libre a propósito: las categorías válidas viven en app.analysis.categories.
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("provenance", sa.String(length=20), nullable=False),
        sa.Column("source_name", sa.String(length=60), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("effect", sa.Text(), nullable=True),
        sa.Column("certainty", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("start_offset >= 0", name="ck_finding_start_non_negative"),
        sa.CheckConstraint("end_offset > start_offset", name="ck_finding_end_after_start"),
        sa.CheckConstraint("line_number >= 1", name="ck_finding_line_positive"),
    )
    op.create_index("ix_analysis_findings_run_id", "analysis_findings", ["run_id"])

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
    op.drop_index("ix_analysis_findings_run_id", table_name="analysis_findings")
    op.drop_table("analysis_findings")
    op.drop_index("ix_analysis_runs_version_id", table_name="analysis_runs")
    op.drop_table("analysis_runs")
