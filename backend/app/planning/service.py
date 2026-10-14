"""Servicio de planificación narrativa.

Reglas que este módulo impone (y que prueban ``tests/test_planificacion.py``):

- Todo acceso filtra por ``project_id``. Un id de otra novela es «no encontrado», nunca un dato ajeno.
- Un vínculo solo une dos elementos del mismo proyecto y solo si la relación está permitida.
- Ninguna operación de canon cambia ``estado`` salvo ``aprobar``, ``aceptar_propuesta``, ``modificar_canon`` y ``archivar``.
- Modificar un elemento canónico exige ``confirmar_cambio_canon``. Sin ella, no se cambia nada.
- Aprobar exige confirmación explícita. Una propuesta de IA nunca pasa a canon por otra vía.
- Cada cambio de canon queda en ``narrative_decisions`` con la instantánea anterior.
- Validar antes de escribir: un fallo no deja cambios parciales. Cada método confirma una sola vez.
- Las escrituras en un proyecto archivado se rechazan, como ya ocurre con los manuscritos.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import utc_now
from app.db.models import NarrativeDecision, NarrativeLink, Project, StructureNode
from app.planning import kinds as K
from app.texts.errors import ConflictError, NotFoundError, ValidationFailed

Clock = Callable[[], datetime]
TREE_KINDS = ("acto", "capitulo", "escena")
# Qué padre admite cada tipo de nodo de estructura. ``None`` significa raíz.
PARENT_KINDS: dict[str, tuple[str | None, ...]] = {
    "acto": (None,),
    "capitulo": (None, "acto"),
    "escena": (None, "acto", "capitulo"),
}


class PlanningService:
    """Operaciones de planificación de un proyecto. Confirma cada operación."""

    def __init__(self, session: Session, clock: Clock = utc_now) -> None:
        self._session = session
        self._clock = clock

    # ------------------------------------------------------------------
    # Proyecto narrativo
    # ------------------------------------------------------------------

    def get_narrative(self, project_id: int) -> Project:
        return self._project(project_id)

    def update_narrative(self, project_id: int, changes: dict[str, Any]) -> Project:
        project = self._active_project(project_id)
        unknown = set(changes) - set(K.NARRATIVE_FIELDS)
        if unknown:
            raise ValidationFailed(f"campos narrativos no válidos: {', '.join(sorted(unknown))}")
        status = changes.get("development_status")
        if status is not None and status not in K.DEVELOPMENT_STATUSES:
            raise ValidationFailed(f"estado de desarrollo no válido: '{status}'")
        if not changes:
            return project
        for field, value in changes.items():
            setattr(project, field, value)
        project.updated_at = self._clock()
        self._session.commit()
        return project

    # ------------------------------------------------------------------
    # Elementos: personajes, lugares, trama, cronología
    # ------------------------------------------------------------------

    def create(self, kind: str, project_id: int, data: dict[str, Any], propuesta: bool = False) -> Any:
        """Crea un elemento. Con ``propuesta=True`` queda como propuesta de IA, nunca como canon."""
        self._require_creatable(kind)
        self._active_project(project_id)
        self._check_fields(kind, data)
        if kind == "elemento_trama" and data.get("kind") not in K.PLOT_KINDS:
            raise ValidationFailed(f"tipo de elemento de trama no válido: '{data.get('kind')}'")
        now = self._clock()
        row = K.MODELS[kind](
            project_id=project_id,
            estado=K.PROPUESTA if propuesta else K.PROVISIONAL,
            origen=K.ORIGEN_IA if propuesta else K.ORIGEN_AUTOR,
            created_at=now,
            updated_at=now,
            **data,
        )
        self._session.add(row)
        self._session.commit()
        return row

    def get(self, kind: str, project_id: int, element_id: int) -> Any:
        """Elemento del proyecto indicado, archivado o no. ``NotFoundError`` si no pertenece a él."""
        self._project(project_id)
        return self._element(kind, project_id, element_id)

    def list(
        self,
        kind: str,
        project_id: int,
        include_archived: bool = False,
        estado: str | None = None,
    ) -> Sequence[Any]:
        self._project(project_id)
        if estado is not None and estado not in K.ESTADOS:
            raise ValidationFailed(f"estado no válido: '{estado}'")
        model = K.MODELS[kind]
        query = select(model).where(model.project_id == project_id).order_by(model.id)
        if not include_archived:
            query = query.where(model.archived_at.is_(None))
        if estado is not None:
            query = query.where(model.estado == estado)
        return list(self._session.scalars(query).all())

    def update(
        self,
        kind: str,
        project_id: int,
        element_id: int,
        changes: dict[str, Any],
        confirmar_cambio_canon: bool = False,
    ) -> Any:
        """Edita un elemento. Si era canónico, exige confirmación y lo devuelve a provisional con una decisión."""
        self._active_project(project_id)
        row = self._element(kind, project_id, element_id)
        if row.archived_at is not None:
            raise ValidationFailed("el elemento está archivado; no se puede editar")
        allowed = K.EDITABLE.get(kind, ())
        unknown = set(changes) - set(allowed)
        if unknown:
            raise ValidationFailed(f"campos no editables en {kind}: {', '.join(sorted(unknown))}")
        if kind == "elemento_trama" and "kind" in changes and changes["kind"] not in K.PLOT_KINDS:
            raise ValidationFailed(f"tipo de elemento de trama no válido: '{changes['kind']}'")
        if not changes:
            return row

        was_canon = row.estado == K.CANONICO
        if was_canon and not confirmar_cambio_canon:
            raise ConflictError(
                "el elemento es canónico: cambiarlo exige confirmar_cambio_canon=true. "
                "No se ha modificado nada."
            )
        snapshot = self._snapshot(row)
        for field, value in changes.items():
            setattr(row, field, value)
        now = self._clock()
        row.updated_at = now
        if was_canon:
            row.estado = K.PROVISIONAL
            row.approved_decision_id = None
            self._record(kind, row, "modificar_canon", K.CANONICO, K.PROVISIONAL, snapshot, None, now)
        self._session.commit()
        return row

    def archive(self, kind: str, project_id: int, element_id: int, confirmar_canon: bool = False) -> Any:
        """Archiva un elemento sin borrarlo. Archivar un canónico exige confirmación."""
        self._active_project(project_id)
        row = self._element(kind, project_id, element_id)
        if row.archived_at is not None:
            raise ValidationFailed("el elemento ya está archivado")
        if row.estado == K.CANONICO and not confirmar_canon:
            raise ConflictError("el elemento es canónico: archivarlo exige confirmar_canon=true. No se ha modificado nada.")
        now = self._clock()
        snapshot = self._snapshot(row)
        row.archived_at = now
        row.updated_at = now
        self._record(kind, row, "archivar", row.estado, row.estado, snapshot, None, now)
        self._session.commit()
        return row

    def approve(self, kind: str, project_id: int, element_id: int, confirmar: bool, nota: str | None = None) -> Any:
        """Aprueba un elemento como canónico. Requiere confirmación explícita del autor."""
        if not confirmar:
            raise ValidationFailed("aprobar como canon exige confirmar=true")
        self._active_project(project_id)
        row = self._element(kind, project_id, element_id)
        if row.archived_at is not None:
            raise ValidationFailed("el elemento está archivado; no se puede aprobar")
        if row.estado == K.CANONICO:
            raise ConflictError("el elemento ya es canónico")
        previous = row.estado
        now = self._clock()
        snapshot = self._snapshot(row)
        decision = self._record(kind, row, "aprobar_canon", previous, K.CANONICO, snapshot, nota, now)
        self._session.flush()
        row.estado = K.CANONICO
        row.approved_decision_id = decision.id
        row.updated_at = now
        self._session.commit()
        return row

    def accept_proposal(self, kind: str, project_id: int, element_id: int) -> Any:
        """Acepta una propuesta de IA como material provisional. No la convierte en canon."""
        self._active_project(project_id)
        row = self._element(kind, project_id, element_id)
        if row.estado != K.PROPUESTA:
            raise ValidationFailed("solo se puede aceptar una propuesta de IA")
        now = self._clock()
        snapshot = self._snapshot(row)
        row.estado = K.PROVISIONAL
        row.updated_at = now
        self._record(kind, row, "aceptar_propuesta", K.PROPUESTA, K.PROVISIONAL, snapshot, None, now)
        self._session.commit()
        return row

    def decisions(self, kind: str, project_id: int, element_id: int) -> Sequence[NarrativeDecision]:
        self._project(project_id)
        self._element(kind, project_id, element_id)
        return list(
            self._session.scalars(
                select(NarrativeDecision)
                .where(
                    NarrativeDecision.project_id == project_id,
                    NarrativeDecision.element_kind == kind,
                    NarrativeDecision.element_id == element_id,
                )
                .order_by(NarrativeDecision.id)
            ).all()
        )

    # ------------------------------------------------------------------
    # Estructura: actos, capítulos y escenas
    # ------------------------------------------------------------------

    def create_node(
        self,
        project_id: int,
        node_kind: str,
        parent_id: int | None,
        data: dict[str, Any],
    ) -> StructureNode:
        """Crea un acto, capítulo o escena. La posición se añade al final de sus hermanos."""
        if node_kind not in TREE_KINDS:
            raise ValidationFailed(f"tipo de nodo no válido: '{node_kind}'")
        self._active_project(project_id)
        parent_kind = None
        if parent_id is not None:
            parent = self._node(project_id, parent_id)
            if parent.archived_at is not None:
                raise ValidationFailed("el nodo padre está archivado")
            parent_kind = parent.kind
        if parent_kind not in PARENT_KINDS[node_kind]:
            raise ValidationFailed(f"un nodo «{node_kind}» no puede colgar de un nodo «{parent_kind or 'raíz'}»")
        self._check_fields("estructura", data)
        position = self._next_position(project_id, parent_id)
        now = self._clock()
        row = StructureNode(
            project_id=project_id,
            parent_id=parent_id,
            kind=node_kind,
            position=position,
            estado=K.PROVISIONAL,
            origen=K.ORIGEN_AUTOR,
            created_at=now,
            updated_at=now,
            **data,
        )
        self._session.add(row)
        self._session.commit()
        return row

    def reorder(self, project_id: int, parent_id: int | None, order: list[int]) -> list[StructureNode]:
        """Reordena los hermanos de ``parent_id``. Cambia ``position``, nunca ``id``.

        ``order`` debe contener exactamente los hermanos del proyecto (archivados incluidos), una sola vez cada uno.
        """
        self._active_project(project_id)
        if parent_id is not None:
            self._node(project_id, parent_id)
        siblings = self._siblings(project_id, parent_id)
        sibling_ids = {node.id for node in siblings}
        if len(set(order)) != len(order) or set(order) != sibling_ids:
            raise ValidationFailed(
                "la lista de reordenación debe contener exactamente los hermanos del nodo, sin repetir ninguno"
            )
        by_id = {node.id: node for node in siblings}
        now = self._clock()
        for index, node_id in enumerate(order):
            by_id[node_id].position = index
            by_id[node_id].updated_at = now
        self._session.commit()
        return [by_id[node_id] for node_id in order]

    # ------------------------------------------------------------------
    # Vínculos
    # ------------------------------------------------------------------

    def link(
        self,
        project_id: int,
        source: tuple[str, int],
        target: tuple[str, int],
        relation: str,
        propuesta: bool = False,
    ) -> NarrativeLink:
        """Crea una relación tipada entre dos elementos del mismo proyecto."""
        source_kind, source_id = source
        target_kind, target_id = target
        for endpoint in (source_kind, target_kind):
            if endpoint not in K.LINK_ENDPOINTS:
                raise ValidationFailed(f"tipo de elemento no vinculable: '{endpoint}'")
        if not K.allowed_relation(source_kind, target_kind, relation):
            raise ValidationFailed(
                f"la relación «{relation}» no está permitida entre «{source_kind}» y «{target_kind}»"
            )
        self._active_project(project_id)
        self._endpoint(project_id, source_kind, source_id)
        self._endpoint(project_id, target_kind, target_id)
        duplicate = self._session.scalar(
            select(NarrativeLink.id).where(
                NarrativeLink.project_id == project_id,
                NarrativeLink.source_kind == source_kind,
                NarrativeLink.source_id == source_id,
                NarrativeLink.target_kind == target_kind,
                NarrativeLink.target_id == target_id,
                NarrativeLink.relation == relation,
            )
        )
        if duplicate is not None:
            raise ConflictError("ese vínculo ya existe")
        now = self._clock()
        row = NarrativeLink(
            project_id=project_id,
            source_kind=source_kind,
            source_id=source_id,
            target_kind=target_kind,
            target_id=target_id,
            relation=relation,
            estado=K.PROPUESTA if propuesta else K.PROVISIONAL,
            origen=K.ORIGEN_IA if propuesta else K.ORIGEN_AUTOR,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        self._session.commit()
        return row

    def links_of(self, project_id: int, kind: str, element_id: int, include_archived: bool = False) -> Sequence[NarrativeLink]:
        """Vínculos en los que participa un elemento, como origen o como destino."""
        self._project(project_id)
        query = select(NarrativeLink).where(
            NarrativeLink.project_id == project_id,
            (
                ((NarrativeLink.source_kind == kind) & (NarrativeLink.source_id == element_id))
                | ((NarrativeLink.target_kind == kind) & (NarrativeLink.target_id == element_id))
            ),
        ).order_by(NarrativeLink.id)
        if not include_archived:
            query = query.where(NarrativeLink.archived_at.is_(None))
        return list(self._session.scalars(query).all())

    def count_elements(self, project_id: int) -> dict[str, int]:
        """Recuento de elementos activos por tipo. Útil para paneles y para comprobar el aislamiento."""
        counts: dict[str, int] = {}
        for kind, model in K.MODELS.items():
            counts[kind] = self._session.scalar(
                select(func.count(model.id)).where(model.project_id == project_id, model.archived_at.is_(None))
            ) or 0
        return counts

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _project(self, project_id: int) -> Project:
        project = self._session.get(Project, project_id)
        if project is None:
            raise NotFoundError(f"no existe el proyecto {project_id}")
        return project

    def _active_project(self, project_id: int) -> Project:
        project = self._project(project_id)
        if project.status == "archivado":
            raise ValidationFailed("el proyecto está archivado; no admite cambios de planificación")
        return project

    def _require_creatable(self, kind: str) -> None:
        if kind not in K.MODELS or kind in ("estructura", "vinculo"):
            raise ValidationFailed(f"tipo de elemento no creable por esta vía: '{kind}'")

    def _check_fields(self, kind: str, data: dict[str, Any]) -> None:
        unknown = set(data) - set(K.EDITABLE.get(kind, ()))
        if unknown:
            raise ValidationFailed(f"campos no válidos en {kind}: {', '.join(sorted(unknown))}")

    def _element(self, kind: str, project_id: int, element_id: int) -> Any:
        if kind not in K.MODELS:
            raise NotFoundError(f"tipo de elemento desconocido: '{kind}'")
        model = K.MODELS[kind]
        row = self._session.scalar(select(model).where(model.id == element_id, model.project_id == project_id))
        if row is None:
            raise NotFoundError(f"no existe {kind} {element_id} en el proyecto {project_id}")
        return row

    def _node(self, project_id: int, node_id: int) -> StructureNode:
        row = self._session.scalar(
            select(StructureNode).where(StructureNode.id == node_id, StructureNode.project_id == project_id)
        )
        if row is None:
            raise NotFoundError(f"no existe el nodo {node_id} en el proyecto {project_id}")
        return row

    def _endpoint(self, project_id: int, kind: str, element_id: int) -> Any:
        """Resuelve un endpoint de vínculo. «escena» exige un nodo de estructura de tipo escena."""
        if kind == "escena":
            row = self._node(project_id, element_id)
            if row.kind != "escena":
                raise ValidationFailed(f"el nodo {element_id} no es una escena")
        else:
            row = self._element(kind, project_id, element_id)
        if row.archived_at is not None:
            raise ValidationFailed(f"{kind} {element_id} está archivado y no puede vincularse")
        return row

    def _siblings(self, project_id: int, parent_id: int | None) -> list[StructureNode]:
        condition = StructureNode.parent_id.is_(None) if parent_id is None else StructureNode.parent_id == parent_id
        return list(
            self._session.scalars(
                select(StructureNode)
                .where(StructureNode.project_id == project_id, condition)
                .order_by(StructureNode.position, StructureNode.id)
            ).all()
        )

    def _next_position(self, project_id: int, parent_id: int | None) -> int:
        siblings = self._siblings(project_id, parent_id)
        return (siblings[-1].position + 1) if siblings else 0

    def _snapshot(self, row: Any) -> str:
        data: dict[str, Any] = {}
        for column in row.__table__.columns:
            value = getattr(row, column.name)
            data[column.name] = value.isoformat() if isinstance(value, datetime) else value
        return json.dumps(data, ensure_ascii=False, sort_keys=True)

    def _record(
        self,
        kind: str,
        row: Any,
        action: str,
        previous: str | None,
        new: str | None,
        snapshot: str,
        note: str | None,
        now: datetime,
    ) -> NarrativeDecision:
        decision = NarrativeDecision(
            project_id=row.project_id,
            element_kind=kind,
            element_id=row.id,
            accion=action,
            estado_previo=previous,
            estado_nuevo=new,
            snapshot=snapshot,
            nota=note,
            created_at=now,
        )
        self._session.add(decision)
        return decision
