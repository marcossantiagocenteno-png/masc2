"""Integridad de la planificación: decisiones con actor y resultado, y vínculos validados en la base.

Revisión: 0007_integridad_planificacion
Revisión anterior: 0006_planificacion_narrativa

Cambios aditivos:

- ``narrative_decisions.actor`` (por defecto ``autor``): quién originó la decisión.
  Las decisiones anteriores a esta migración se atribuyen al autor: en la fase 2a no existía
  ningún otro actor.
- ``narrative_decisions.resultado``: estado del elemento tras el cambio. Nulo en decisiones anteriores.
- Triggers en ``narrative_links``: un vínculo solo puede apuntar a un elemento existente, activo,
  del mismo proyecto, y de un tipo válido. Antes, esta regla solo la aplicaba el servicio.

La migración comprueba primero que los vínculos existentes cumplen la regla. Si alguno no la
cumple, falla sin aplicar nada: no se borra ni se modifica ningún dato. La bajada no es automática.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0007_integridad_planificacion"
down_revision: str | None = "0006_planificacion_narrativa"
branch_labels = None
depends_on = None

_TABLE_BY_KIND = {
    "personaje": "characters",
    "lugar": "places",
    "elemento_trama": "plot_elements",
    "acontecimiento": "timeline_events",
}


def _endpoint_ok(kind: str, id_expr: str, project_expr: str, require_active: bool) -> str:
    """Condición SQL: el extremo (kind, id) existe, pertenece al proyecto y, si se pide, no está archivado."""
    active = " AND e.archived_at IS NULL" if require_active else ""
    branches = [
        f"({kind} = '{kind_name}' AND EXISTS (SELECT 1 FROM {table} e "
        f"WHERE e.id = {id_expr} AND e.project_id = {project_expr}{active}))"
        for kind_name, table in _TABLE_BY_KIND.items()
    ]
    branches.append(
        f"({kind} = 'escena' AND EXISTS (SELECT 1 FROM structure_nodes e "
        f"WHERE e.id = {id_expr} AND e.project_id = {project_expr} AND e.kind = 'escena'{active}))"
    )
    return "(" + " OR ".join(branches) + ")"


def _link_rule(require_active: bool, source: str, target: str, project: str) -> str:
    return (
        f"{_endpoint_ok(f'{source}_kind', f'{source}_id', project, require_active)} AND "
        f"{_endpoint_ok(f'{target}_kind', f'{target}_id', project, require_active)}"
    )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        raise NotImplementedError(f"Esta migración solo está probada para SQLite; dialecto: {bind.dialect.name}")

    # 1) Los vínculos existentes deben cumplir la regla antes de añadir los triggers. Existen extremos
    #    archivados legítimos (un vínculo sigue vigente cuando se archiva uno de sus extremos), así que
    #    aquí no se exige que estén activos.
    invalid = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM narrative_links l WHERE NOT ("
            + _link_rule(False, "l.source", "l.target", "l.project_id")
            + ")"
        )
    ).scalar_one()
    if invalid:
        raise RuntimeError(
            f"{invalid} vínculo(s) existente(s) no cumplen la regla de integridad. "
            "No se ha aplicado ningún cambio: revísalos antes de migrar (ver docs/RESPALDO_Y_RESTAURACION.md)."
        )

    # 2) Decisiones: actor y resultado.
    op.add_column(
        "narrative_decisions",
        sa.Column("actor", sa.String(length=20), nullable=False, server_default="autor"),
    )
    op.add_column("narrative_decisions", sa.Column("resultado", sa.Text(), nullable=True))

    # 3) Triggers de vínculos. Los endpoints deben estar activos al crear o al cambiar un extremo.
    #    Archivar o aprobar un vínculo no cambia los extremos, así que no se revalida.
    rule_insert = _link_rule(True, "NEW.source", "NEW.target", "NEW.project_id")
    op.execute(
        "CREATE TRIGGER trg_narrative_links_check_insert BEFORE INSERT ON narrative_links "
        "BEGIN "
        f"SELECT RAISE(ABORT, 'vínculo no válido: un extremo no existe, está archivado, es de otro proyecto o su tipo no es válido') WHERE NOT ({rule_insert}); "
        "END"
    )
    op.execute(
        "CREATE TRIGGER trg_narrative_links_check_update BEFORE UPDATE OF "
        "project_id, source_kind, source_id, target_kind, target_id ON narrative_links "
        "BEGIN "
        f"SELECT RAISE(ABORT, 'vínculo no válido: un extremo no existe, está archivado, es de otro proyecto o su tipo no es válido') WHERE NOT ({rule_insert}); "
        "END"
    )


def downgrade() -> None:
    raise NotImplementedError(
        "La bajada de 0007 no es automática. Restaura la copia de la base de datos anterior a la migración "
        "(docs/RESPALDO_Y_RESTAURACION.md)."
    )
