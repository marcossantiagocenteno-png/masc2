"""Endpoints del análisis editorial."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.analysis.provider import resolve_provider
from app.analysis.schemas import AnalysisRequest, AnalysisRunOut
from app.analysis.service import AnalysisService
from app.texts.routes import get_session
from app.texts.service import TextService

router = APIRouter()


def get_analysis_service(request: Request, session: Session = Depends(get_session)) -> AnalysisService:
    """Servicio de análisis con los límites de la aplicación."""
    texts = TextService(session, max_version_chars=request.app.state.settings.max_version_chars)
    return AnalysisService(
        session,
        texts,
        max_analysis_chars=request.app.state.settings.max_analysis_chars,
    )


@router.post(
    "/versions/{version_id}/analyses",
    status_code=status.HTTP_201_CREATED,
    response_model=AnalysisRunOut,
)
def create_analysis(
    version_id: int,
    payload: AnalysisRequest,
    request: Request,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisRunOut:
    """Analiza un fragmento con el proveedor configurado. No modifica la versión."""
    provider = resolve_provider(request.app.state.settings.analysis_provider)
    run = service.analyze(version_id, payload.start_offset, payload.end_offset, provider)
    return AnalysisRunOut.model_validate(run, from_attributes=True)


@router.get("/versions/{version_id}/analyses", response_model=list[AnalysisRunOut])
def list_analyses(
    version_id: int,
    service: AnalysisService = Depends(get_analysis_service),
) -> list[AnalysisRunOut]:
    """Análisis guardados de una versión."""
    return [AnalysisRunOut.model_validate(run, from_attributes=True) for run in service.list_runs(version_id)]
