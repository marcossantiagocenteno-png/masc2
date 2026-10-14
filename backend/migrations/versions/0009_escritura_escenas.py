"""Escritura de escenas: cada escena puede tener su propio manuscrito, enlazado por una tabla propia.

Revisión: 0009_escritura_escenas
Revisión anterior: 0008_revision_estructura

Por qué una tabla y no una columna en ``structure_nodes``: la escena pertenece a la planificación y el
texto al manuscrito. La tabla une ambos por id. Ni el título ni la posición forman parte de la unión,
así que renombrar o mover una escena no la rompe. Un manuscrito de escena reutiliza su borrador,
sus versiones y sus puntos de recuperación: no se copia ningún texto.

Cambio aditivo: tabla ``scene_manuscripts`` vacía. Sus reglas quedan en la base:

- Un nodo solo puede tener un manuscrito, y un manuscrito solo puede pertenecer a un nodo.
- Nodo y manuscrito deben pertenecer al mismo proyecto, y el nodo debe ser una escena.
- La fila es inmutable: no se actualiza ni se borra.

La migración no modifica datos existentes. La bajada no es automática (restaura la copia anterior).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0009_escritura_escenas"
down_revision: str | None = "0008_revision_estructura"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        raise NotImplementedError(f"Esta migración solo está probada para SQLite; dialecto: {bind.dialect.name}")
    op.create_table(
        "scene_manuscripts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("node_id", sa.Integer(), sa.ForeignKey("structure_nodes.id"), nullable=False),
        sa.Column("manuscript_id", sa.Integer(), sa.ForeignKey("manuscripts.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("node_id", name="uq_scene_manuscripts_node"),
        sa.UniqueConstraint("manuscript_id", name="uq_scene_manuscripts_manuscript"),
    )
    op.create_index("ix_scene_manuscripts_project_id", "scene_manuscripts", ["project_id"])
    op.execute(
        """
        CREATE TRIGGER trg_scene_manuscripts_valid BEFORE INSERT ON scene_manuscripts
        WHEN NOT EXISTS (
            SELECT 1 FROM structure_nodes n
            WHERE n.id = NEW.node_id AND n.project_id = NEW.project_id AND n.kind = 'escena'
        ) OR NOT EXISTS (
            SELECT 1 FROM manuscripts m
            WHERE m.id = NEW.manuscript_id AND m.project_id = NEW.project_id
        )
        BEGIN
            SELECT RAISE(ABORT, 'escritura de escena no válida: el nodo debe ser una escena del proyecto y el manuscrito del mismo proyecto');
        END
        """
    )
    op.execute(
        "CREATE TRIGGER trg_scene_manuscripts_no_update BEFORE UPDATE ON scene_manuscripts "
        "BEGIN SELECT RAISE(ABORT, 'scene_manuscripts es inmutable'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_scene_manuscripts_no_delete BEFORE DELETE ON scene_manuscripts "
        "BEGIN SELECT RAISE(ABORT, 'scene_manuscripts es inmutable'); END"
    )


def downgrade() -> None:
    raise NotImplementedError("La bajada de 0009 no es automática. Restaura la copia anterior a esta migración.")
