"""Endpoints HTTP de manuscritos, versiones y revisiones editoriales."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session, object_session

from app.db.models import EditorialReview, Manuscript, ManuscriptVersion
from app.texts.schemas import (
    ManuscriptCreate,
    ManuscriptSummary,
    ReviewCreate,
    ReviewOut,
    VersionCreate,
    VersionOut,
    VersionSummary,
)
from app.projects.membership import reject_legacy_write_for_scene, scene_node_id
from app.texts.service import TextService

router = APIRouter()


def get_session(request: Request) -> Iterator[Session]:
    """Sesión por petición. Se cierra al terminar la respuesta."""
    session: Session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_service(request: Request, session: Session = Depends(get_session)) -> TextService:
    """Servicio de textos configurado con el límite de la aplicación."""
    return TextService(session, max_version_chars=request.app.state.settings.max_version_chars)


def _summary(version: ManuscriptVersion) -> VersionSummary:
    return VersionSummary.model_validate(version, from_attributes=True)


def manuscript_summary(manuscript: Manuscript) -> ManuscriptSummary:
    latest = manuscript.versions[-1].number if manuscript.versions else 0
    session = object_session(manuscript)
    return ManuscriptSummary(
        id=manuscript.id,
        project_id=manuscript.project_id,
        title=manuscript.title,
        created_at=manuscript.created_at,
        version_count=len(manuscript.versions),
        latest_version_number=latest,
        scene_node_id=scene_node_id(session, manuscript.id) if session is not None else None,
    )


def _review_out(review: EditorialReview) -> ReviewOut:
    return ReviewOut.model_validate(review, from_attributes=True)


@router.post("/manuscripts", status_code=status.HTTP_201_CREATED, response_model=ManuscriptSummary)
def create_manuscript(payload: ManuscriptCreate, service: TextService = Depends(get_service)) -> ManuscriptSummary:
    """Crea un manuscrito con la versión 1."""
    manuscript = service.create_manuscript(payload.title, payload.content, payload.note)
    return manuscript_summary(manuscript)


@router.get("/manuscripts", response_model=list[ManuscriptSummary])
def list_manuscripts(service: TextService = Depends(get_service)) -> list[ManuscriptSummary]:
    """Lista de manuscritos."""
    return [manuscript_summary(item) for item in service.list_manuscripts()]


@router.get("/manuscripts/{manuscript_id}", response_model=ManuscriptSummary)
def get_manuscript(manuscript_id: int, service: TextService = Depends(get_service)) -> ManuscriptSummary:
    """Detalle de un manuscrito."""
    return manuscript_summary(service.get_manuscript(manuscript_id))


@router.post(
    "/manuscripts/{manuscript_id}/versions",
    status_code=status.HTTP_201_CREATED,
    response_model=VersionOut,
)
def create_version(
    manuscript_id: int,
    payload: VersionCreate,
    session: Session = Depends(get_session),
    service: TextService = Depends(get_service),
) -> VersionOut:
    """Crea una versión nueva. Nunca modifica las anteriores. Ruta heredada: no admite escenas."""
    reject_legacy_write_for_scene(session, manuscript_id)
    version = service.add_version(
        manuscript_id, payload.content, payload.note, payload.based_on_version_id
    )
    return _version_out(service, version)


@router.get("/manuscripts/{manuscript_id}/versions", response_model=list[VersionSummary])
def list_versions(manuscript_id: int, service: TextService = Depends(get_service)) -> list[VersionSummary]:
    """Versiones de un manuscrito, sin contenido."""
    return [_summary(item) for item in service.list_versions(manuscript_id)]


@router.get("/versions/{version_id}", response_model=VersionOut)
def get_version(version_id: int, service: TextService = Depends(get_service)) -> VersionOut:
    """Versión completa, con su contenido y el número de revisiones."""
    return _version_out(service, service.get_version(version_id))


@router.post(
    "/versions/{version_id}/reviews",
    status_code=status.HTTP_201_CREATED,
    response_model=ReviewOut,
)
def create_review(
    version_id: int,
    payload: ReviewCreate,
    service: TextService = Depends(get_service),
) -> ReviewOut:
    """Crea una revisión vinculada a esta versión."""
    review = service.create_review(version_id, payload.reviewer, payload.items)
    return _review_out(review)


@router.get("/versions/{version_id}/reviews", response_model=list[ReviewOut])
def list_reviews(version_id: int, service: TextService = Depends(get_service)) -> list[ReviewOut]:
    """Revisiones vinculadas a esta versión."""
    return [_review_out(item) for item in service.list_reviews(version_id)]


def _version_out(service: TextService, version: ManuscriptVersion) -> VersionOut:
    base = _summary(version).model_dump()
    return VersionOut(**base, content=version.content, review_count=service.review_count(version.id))
