"""Planificación narrativa: núcleo de datos de la fase 2a.

Revisión: 0006_planificacion_narrativa
Revisión anterior: 0005_borradores_y_recuperacion

Cambios aditivos. No se modifica ningún manuscrito, versión, borrador ni copia:

- ``projects``: columnas narrativas nulables (premisa, sinopsis, género, tema, tono, estado de desarrollo).
  El proyecto es la novela; no se crea una tabla paralela con la misma identidad.
- Tablas nuevas, todas con ``project_id``: ``characters``, ``places``, ``plot_elements``,
  ``timeline_events``, ``structure_nodes``, ``narrative_links``, ``narrative_decisions``.
- Todas las entidades llevan ``estado`` (provisional, propuesta_ia, canonico), ``origen``
  (autor, ia), ``approved_decision_id`` y ``archived_at``.
- ``narrative_decisions`` es de solo inserción: triggers que rechazan UPDATE y DELETE.

La bajada no es automática: se revierte restaurando la copia previa (docs/RESPALDO_Y_RESTAURACION.md).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0006_planificacion_narrativa"
down_revision: str | None = "0005_borradores_y_recuperacion"
branch_labels = None
depends_on = None

IMMUTABLE_TABLES = ("narrative_decisions",)
PROJECT_COLUMNS = {
    "premise": sa.Text(),
    "synopsis": sa.Text(),
    "genre": sa.String(length=120),
    "theme": sa.Text(),
    "tone": sa.String(length=200),
    "development_status": sa.String(length=20),
}


def _canon_columns(decisions_table: str = "narrative_decisions") -> list[sa.Column]:
    return [
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="provisional"),
        sa.Column("origen", sa.String(length=10), nullable=False, server_default="autor"),
        sa.Column("approved_decision_id", sa.Integer(), sa.ForeignKey(f"{decisions_table}.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
    ]


def _canon_checks(table: str) -> list[sa.CheckConstraint]:
    return [
        sa.CheckConstraint("estado IN ('provisional', 'propuesta_ia', 'canonico')", name=f"ck_{table}_estado"),
        sa.CheckConstraint("origen IN ('autor', 'ia')", name=f"ck_{table}_origen"),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        raise NotImplementedError(f"Esta migración solo está probada para SQLite; dialecto: {bind.dialect.name}")

    for column, column_type in PROJECT_COLUMNS.items():
        op.add_column("projects", sa.Column(column, column_type, nullable=True))

    op.create_table(
        "narrative_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("element_kind", sa.String(length=30), nullable=False),
        sa.Column("element_id", sa.Integer(), nullable=False),
        sa.Column("accion", sa.String(length=30), nullable=False),
        sa.Column("estado_previo", sa.String(length=20), nullable=True),
        sa.Column("estado_nuevo", sa.String(length=20), nullable=True),
        sa.Column("snapshot", sa.Text(), nullable=True),
        sa.Column("nota", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Index("ix_narrative_decisions_project_id", "project_id"),
    )

    op.create_table(
        "characters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("goals", sa.Text(), nullable=True),
        sa.Column("motivations", sa.Text(), nullable=True),
        sa.Column("conflicts", sa.Text(), nullable=True),
        sa.Column("evolution", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_canon_columns(),
        *_canon_checks("characters"),
    )
    op.create_index("ix_characters_project_id", "characters", ["project_id"])

    op.create_table(
        "places",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("features", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_canon_columns(),
        *_canon_checks("places"),
    )
    op.create_index("ix_places_project_id", "places", ["project_id"])

    op.create_table(
        "plot_elements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_canon_columns(),
        *_canon_checks("plot_elements"),
        sa.CheckConstraint(
            "kind IN ('acontecimiento', 'conflicto', 'subtrama', 'misterio', 'pregunta_abierta')",
            name="ck_plot_elements_kind",
        ),
    )
    op.create_index("ix_plot_elements_project_id", "plot_elements", ["project_id"])

    op.create_table(
        "timeline_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        # Orden narrativo: el lugar del acontecimiento en el relato, no en la historia. Nulo si no se ha decidido.
        sa.Column("narrative_order", sa.Integer(), nullable=True),
        # Posición temporal dentro de la historia, en texto libre (p. ej. «tres años antes de la boda»).
        sa.Column("story_time", sa.String(length=200), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_canon_columns(),
        *_canon_checks("timeline_events"),
    )
    op.create_index("ix_timeline_events_project_id", "timeline_events", ["project_id"])

    op.create_table(
        "structure_nodes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("structure_nodes.id"), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_canon_columns(),
        *_canon_checks("structure_nodes"),
        sa.CheckConstraint("kind IN ('acto', 'capitulo', 'escena')", name="ck_structure_nodes_kind"),
        sa.CheckConstraint("position >= 0", name="ck_structure_nodes_position"),
    )
    op.create_index("ix_structure_nodes_project_id", "structure_nodes", ["project_id"])
    op.create_index("ix_structure_nodes_parent_id", "structure_nodes", ["parent_id"])

    op.create_table(
        "narrative_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_kind", sa.String(length=30), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("target_kind", sa.String(length=30), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("relation", sa.String(length=40), nullable=False),
        *_canon_columns(),
        *_canon_checks("narrative_links"),
        sa.UniqueConstraint(
            "project_id", "source_kind", "source_id", "target_kind", "target_id", "relation",
            name="uq_narrative_links_relation",
        ),
    )
    op.create_index("ix_narrative_links_project_id", "narrative_links", ["project_id"])
    op.create_index("ix_narrative_links_source", "narrative_links", ["project_id", "source_kind", "source_id"])
    op.create_index("ix_narrative_links_target", "narrative_links", ["project_id", "target_kind", "target_id"])

    for table in IMMUTABLE_TABLES:
        for action in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER trg_{table}_no_{action.lower()} "
                f"BEFORE {action} ON {table} "
                f"BEGIN SELECT RAISE(ABORT, '{table} es inmutable'); END"
            )


def downgrade() -> None:
    raise NotImplementedError(
        "La bajada de 0006 no es automática: borraría la planificación. "
        "Restaura la copia de la base de datos anterior a la migración (docs/RESPALDO_Y_RESTAURACION.md)."
    )
