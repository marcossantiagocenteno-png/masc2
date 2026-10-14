"""Rutas de manuscritos acotadas a un proyecto: ``/projects/{p}/manuscripts/{m}/...``.

Comprueban pertenencia (ver ``membership``) antes de leer o escribir. Las escrituras exigen un proyecto
activo. La lógica de versiones, borradores, puntos, análisis y revisiones es la de los servicios existentes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.db.models import ManuscriptDraft
from app.drafts.schemas import DraftInitOut, DraftOut, DraftSave, RecoveryPointOut, RecoveryPointSummary, RestoreIn
from app.drafts.service import DraftService
from app.analysis.routes import get_analysis_service, run_analysis
from app.analysis.schemas import AnalysisRequest, AnalysisRunOut
from app.analysis.service import AnalysisService
from app.projects.membership import manuscript_in_project, require_writable, version_in_manuscript
from app.texts.routes import _review_out, _version_out, get_service, get_session, manuscript_summary
from app.texts.schemas import ManuscriptSummary, ReviewCreate, ReviewOut, VersionCreate, VersionOut, VersionSummary
from app.texts.service import TextService

router = APIRouter(prefix="/projects/{project_id}/manuscripts/{manuscript_id}")


def _draft_service(request: Request, session: Session = Depends(get_session)) -> DraftService:
    return DraftService(session, max_chars=request.app.state.settings.max_version_chars, clock=request.app.state.clock)


def _draft_out(draft: ManuscriptDraft) -> DraftOut:
    return DraftOut.model_validate(draft, from_attributes=True)


@router.get("", response_model=ManuscriptSummary)
def get_manuscript(project_id: int, manuscript_id: int, session: Session = Depends(get_session)) -> ManuscriptSummary:
    return manuscript_summary(manuscript_in_project(session, project_id, manuscript_id))


@router.get("/versions", response_model=list[VersionSummary])
def list_versions(
    project_id: int, manuscript_id: int, session: Session = Depends(get_session), service: TextService = Depends(get_service)
) -> list[VersionSummary]:
    manuscript_in_project(session, project_id, manuscript_id)
    return [VersionSummary.model_validate(item, from_attributes=True) for item in service.list_versions(manuscript_id)]


@router.get("/versions/{version_id}", response_model=VersionOut)
def get_version(
    project_id: int,
    manuscript_id: int,
    version_id: int,
    session: Session = Depends(get_session),
    service: TextService = Depends(get_service),
) -> VersionOut:
    version_in_manuscript(session, project_id, manuscript_id, version_id)
    return _version_out(service, service.get_version(version_id))


@router.post("/versions", status_code=status.HTTP_201_CREATED, response_model=VersionOut)
def create_version(
    project_id: int,
    manuscript_id: int,
    payload: VersionCreate,
    session: Session = Depends(get_session),
    service: TextService = Depends(get_service),
) -> VersionOut:
    """Crea una versión formal nueva. Nunca modifica las anteriores ni el borrador."""
    manuscript_in_project(session, project_id, manuscript_id)
    require_writable(session, project_id)
    version = service.add_version(manuscript_id, payload.content, payload.note, payload.based_on_version_id)
    return _version_out(service, version)


@router.post("/draft", response_model=DraftInitOut)
def init_draft(
    project_id: int,
    manuscript_id: int,
    session: Session = Depends(get_session),
    service: DraftService = Depends(_draft_service),
) -> DraftInitOut:
    manuscript_in_project(session, project_id, manuscript_id)
    draft, created = service.init_draft(manuscript_id)
    return DraftInitOut(created=created, draft=_draft_out(draft))


@router.get("/draft", response_model=DraftOut)
def get_draft(
    project_id: int, manuscript_id: int, session: Session = Depends(get_session), service: DraftService = Depends(_draft_service)
) -> DraftOut:
    manuscript_in_project(session, project_id, manuscript_id)
    return _draft_out(service.get_draft(manuscript_id))


@router.put("/draft", response_model=DraftOut)
def save_draft(
    project_id: int,
    manuscript_id: int,
    payload: DraftSave,
    session: Session = Depends(get_session),
    service: DraftService = Depends(_draft_service),
) -> DraftOut:
    manuscript_in_project(session, project_id, manuscript_id)
    require_writable(session, project_id)
    return _draft_out(service.save(manuscript_id, payload.content, payload.base_revision, keep_previous=payload.keep_previous))


@router.get("/recovery-points", response_model=list[RecoveryPointSummary])
def list_points(
    project_id: int, manuscript_id: int, session: Session = Depends(get_session), service: DraftService = Depends(_draft_service)
) -> list[RecoveryPointSummary]:
    manuscript_in_project(session, project_id, manuscript_id)
    return [RecoveryPointSummary.model_validate(point, from_attributes=True) for point in service.list_points(manuscript_id)]


@router.get("/recovery-points/{point_id}", response_model=RecoveryPointOut)
def get_point(
    project_id: int,
    manuscript_id: int,
    point_id: int,
    session: Session = Depends(get_session),
    service: DraftService = Depends(_draft_service),
) -> RecoveryPointOut:
    manuscript_in_project(session, project_id, manuscript_id)
    return RecoveryPointOut.model_validate(service.get_point(manuscript_id, point_id), from_attributes=True)


@router.post("/recovery-points/{point_id}/restore", response_model=DraftOut)
def restore_point(
    project_id: int,
    manuscript_id: int,
    point_id: int,
    payload: RestoreIn,
    session: Session = Depends(get_session),
    service: DraftService = Depends(_draft_service),
) -> DraftOut:
    manuscript_in_project(session, project_id, manuscript_id)
    require_writable(session, project_id)
    return _draft_out(service.restore(manuscript_id, point_id, payload.base_revision))


# ----------------------------------------------------------------------
# Análisis y revisiones de una versión. Pertenencia antes de cualquier proveedor o escritura.
# ----------------------------------------------------------------------


@router.post("/versions/{version_id}/analyses", status_code=status.HTTP_201_CREATED, response_model=AnalysisRunOut)
def create_analysis(
    project_id: int,
    manuscript_id: int,
    version_id: int,
    payload: AnalysisRequest,
    request: Request,
    session: Session = Depends(get_session),
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisRunOut:
    """Analiza un fragmento de una versión del proyecto. No modifica la versión."""
    version_in_manuscript(session, project_id, manuscript_id, version_id)
    require_writable(session, project_id)
    return run_analysis(request, service, version_id, payload)


@router.get("/versions/{version_id}/analyses", response_model=list[AnalysisRunOut])
def list_analyses(
    project_id: int,
    manuscript_id: int,
    version_id: int,
    session: Session = Depends(get_session),
    service: AnalysisService = Depends(get_analysis_service),
) -> list[AnalysisRunOut]:
    version_in_manuscript(session, project_id, manuscript_id, version_id)
    return [AnalysisRunOut.model_validate(run, from_attributes=True) for run in service.list_runs(version_id)]


@router.post("/versions/{version_id}/reviews", status_code=status.HTTP_201_CREATED, response_model=ReviewOut)
def create_review(
    project_id: int,
    manuscript_id: int,
    version_id: int,
    payload: ReviewCreate,
    session: Session = Depends(get_session),
    service: TextService = Depends(get_service),
) -> ReviewOut:
    """Crea una revisión vinculada a una versión del proyecto. Valida las citas antes de guardar nada."""
    version_in_manuscript(session, project_id, manuscript_id, version_id)
    require_writable(session, project_id)
    return _review_out(service.create_review(version_id, payload.reviewer, payload.items))


@router.get("/versions/{version_id}/reviews", response_model=list[ReviewOut])
def list_reviews(
    project_id: int,
    manuscript_id: int,
    version_id: int,
    session: Session = Depends(get_session),
    service: TextService = Depends(get_service),
) -> list[ReviewOut]:
    version_in_manuscript(session, project_id, manuscript_id, version_id)
    return [_review_out(item) for item in service.list_reviews(version_id)]
