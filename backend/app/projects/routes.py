"""Endpoints de proyectos. No hay endpoint de borrado: los proyectos se archivan."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.db.models import Project
from app.projects.schemas import ProjectCreate, ProjectDetail, ProjectOut, ProjectRename
from app.projects.service import ProjectService
from app.texts.routes import get_session, manuscript_summary
from app.texts.schemas import ManuscriptCreate, ManuscriptSummary
from app.texts.service import TextService

router = APIRouter(prefix="/projects")


def get_project_service(request: Request, session: Session = Depends(get_session)) -> ProjectService:
    texts = TextService(session, max_version_chars=request.app.state.settings.max_version_chars)
    return ProjectService(session, texts)


def _out(project: Project) -> ProjectOut:
    return ProjectOut.model_validate(project, from_attributes=True)


@router.get("", response_model=list[ProjectOut])
def list_projects(
    status_filter: str | None = "activo", service: ProjectService = Depends(get_project_service)
) -> list[ProjectOut]:
    """Proyectos activos por defecto. ``status_filter=archivado`` o ``todos`` (vacío) para los demás."""
    value = None if status_filter in ("", "todos") else status_filter
    return [_out(item) for item in service.list_projects(value)]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProjectOut)
def create_project(payload: ProjectCreate, service: ProjectService = Depends(get_project_service)) -> ProjectOut:
    return _out(service.create_project(payload.name))


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(project_id: int, service: ProjectService = Depends(get_project_service)) -> ProjectDetail:
    project = service.get_project(project_id)
    count, last = service.stats(project_id)
    return ProjectDetail(**_out(project).model_dump(), manuscript_count=count, last_activity_at=last)


@router.patch("/{project_id}", response_model=ProjectOut)
def rename_project(
    project_id: int, payload: ProjectRename, service: ProjectService = Depends(get_project_service)
) -> ProjectOut:
    return _out(service.rename_project(project_id, payload.name))


@router.post("/{project_id}/archive", response_model=ProjectOut)
def archive_project(project_id: int, service: ProjectService = Depends(get_project_service)) -> ProjectOut:
    return _out(service.archive_project(project_id))


@router.post("/{project_id}/restore", response_model=ProjectOut)
def restore_project(project_id: int, service: ProjectService = Depends(get_project_service)) -> ProjectOut:
    return _out(service.restore_project(project_id))


@router.get("/{project_id}/manuscripts", response_model=list[ManuscriptSummary])
def list_project_manuscripts(
    project_id: int, service: ProjectService = Depends(get_project_service)
) -> list[ManuscriptSummary]:
    return [manuscript_summary(item) for item in service.list_manuscripts(project_id)]


@router.post("/{project_id}/manuscripts", status_code=status.HTTP_201_CREATED, response_model=ManuscriptSummary)
def create_project_manuscript(
    project_id: int, payload: ManuscriptCreate, service: ProjectService = Depends(get_project_service)
) -> ManuscriptSummary:
    return manuscript_summary(service.create_manuscript(project_id, payload.title, payload.content, payload.note))
