"""Endpoints de borradores y puntos de recuperación.

- ``GET /manuscripts/{id}/draft``: borrador actual (404 si no existe).
- ``POST /manuscripts/{id}/draft``: crea el borrador desde la última versión si no existe.
- ``PUT /manuscripts/{id}/draft``: guarda con escritura condicional (409 si la revisión no es la actual).
- ``GET /manuscripts/{id}/recovery-points``: lista los puntos, sin contenido.
- ``GET /manuscripts/{id}/recovery-points/{point_id}``: contenido de un punto.
- ``POST /manuscripts/{id}/recovery-points/{point_id}/restore``: restaura en una transacción.

No hay ningún endpoint que borre borradores ni puntos.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.models import ManuscriptDraft
from app.drafts.schemas import (
    DraftInitOut,
    DraftOut,
    DraftSave,
    RecoveryPointOut,
    RecoveryPointSummary,
    RestoreIn,
)
from app.drafts.service import DraftService
from app.projects.membership import reject_legacy_write_for_scene

router = APIRouter()


def get_session(request: Request) -> Iterator[Session]:
    session: Session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_service(request: Request, session: Session = Depends(get_session)) -> DraftService:
    return DraftService(
        session,
        max_chars=request.app.state.settings.max_version_chars,
        clock=request.app.state.clock,
    )


def _draft_out(draft: ManuscriptDraft) -> DraftOut:
    return DraftOut.model_validate(draft, from_attributes=True)


@router.get("/manuscripts/{manuscript_id}/draft", response_model=DraftOut)
def get_draft(manuscript_id: int, service: DraftService = Depends(get_service)) -> DraftOut:
    return _draft_out(service.get_draft(manuscript_id))


@router.post("/manuscripts/{manuscript_id}/draft", response_model=DraftInitOut)
def init_draft(manuscript_id: int, service: DraftService = Depends(get_service)) -> DraftInitOut:
    draft, created = service.init_draft(manuscript_id)
    return DraftInitOut(created=created, draft=_draft_out(draft))


@router.put("/manuscripts/{manuscript_id}/draft", response_model=DraftOut)
def save_draft(
    manuscript_id: int,
    payload: DraftSave,
    session: Session = Depends(get_session),
    service: DraftService = Depends(get_service),
) -> DraftOut:
    reject_legacy_write_for_scene(session, manuscript_id)
    return _draft_out(
        service.save(manuscript_id, payload.content, payload.base_revision, keep_previous=payload.keep_previous)
    )


@router.get("/manuscripts/{manuscript_id}/recovery-points", response_model=list[RecoveryPointSummary])
def list_points(manuscript_id: int, service: DraftService = Depends(get_service)) -> list[RecoveryPointSummary]:
    return [
        RecoveryPointSummary.model_validate(point, from_attributes=True)
        for point in service.list_points(manuscript_id)
    ]


@router.get("/manuscripts/{manuscript_id}/recovery-points/{point_id}", response_model=RecoveryPointOut)
def get_point(
    manuscript_id: int, point_id: int, service: DraftService = Depends(get_service)
) -> RecoveryPointOut:
    return RecoveryPointOut.model_validate(service.get_point(manuscript_id, point_id), from_attributes=True)


@router.post(
    "/manuscripts/{manuscript_id}/recovery-points/{point_id}/restore",
    response_model=DraftOut,
)
def restore_point(
    manuscript_id: int,
    point_id: int,
    payload: RestoreIn,
    session: Session = Depends(get_session),
    service: DraftService = Depends(get_service),
) -> DraftOut:
    reject_legacy_write_for_scene(session, manuscript_id)
    return _draft_out(service.restore(manuscript_id, point_id, payload.base_revision))
