"""Análisis con proveedor real: modelo, envío externo y justificación.

Revisión: 0003_analisis_proveedor_real
Revisión anterior: 0002_analisis_editorial

Solo añade columnas. Los triggers de inmutabilidad de la migración 0002 siguen
vigentes porque no se reconstruye ninguna tabla. Las filas anteriores quedan
con ``sent_external = 0``, ``model_name = NULL`` y ``justification = NULL``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0003_analisis_proveedor_real"
down_revision: str | None = "0002_analisis_editorial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        raise NotImplementedError(
            f"Esta migración solo está probada para SQLite; dialecto recibido: {bind.dialect.name}"
        )
    op.add_column("analysis_runs", sa.Column("model_name", sa.String(length=120), nullable=True))
    op.add_column(
        "analysis_runs",
        sa.Column("sent_external", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("analysis_findings", sa.Column("justification", sa.Text(), nullable=True))


IMMUTABLE_TABLES = ("analysis_runs", "analysis_findings")


def downgrade() -> None:
    # SQLite borra columnas reconstruyendo la tabla, y al reconstruirla se pierden sus triggers.
    # Por eso se recrean al final: la inmutabilidad debe sobrevivir a la bajada.
    with op.batch_alter_table("analysis_findings") as batch:
        batch.drop_column("justification")
    with op.batch_alter_table("analysis_runs") as batch:
        batch.drop_column("sent_external")
        batch.drop_column("model_name")

    for table in IMMUTABLE_TABLES:
        for action in ("UPDATE", "DELETE"):
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_{action.lower()}")
            op.execute(
                f"CREATE TRIGGER trg_{table}_no_{action.lower()} "
                f"BEFORE {action} ON {table} "
                f"BEGIN SELECT RAISE(ABORT, '{table} es inmutable'); END"
            )
