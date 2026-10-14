"""Endpoints del análisis editorial."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.analysis.errors import AuthorizationRequired
from app.analysis.provider import resolve_provider
from app.analysis.schemas import AnalysisRequest, AnalysisRunOut, ProviderStatusOut
from app.analysis.service import AnalysisService
from app.texts.errors import TextError
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
    """Analiza un fragmento con el proveedor configurado. No modifica la versión.

    Para un proveedor externo, la petición debe llevar ``external_authorization``
    con el nombre del proveedor configurado. Sin ella, no se realiza ninguna llamada.
    """
    settings = request.app.state.settings
    provider = resolve_provider(settings.analysis_provider, settings)

    authorization = payload.external_authorization
    if provider.is_external:
        if authorization is None:
            raise AuthorizationRequired(
                f"el proveedor '{provider.name}' envía el fragmento fuera de este equipo: "
                "la petición debe incluir external_authorization"
            )
        if authorization.provider != provider.name:
            raise AuthorizationRequired(
                f"la autorización indica '{authorization.provider}', pero el proveedor configurado es '{provider.name}'"
            )

    run = service.analyze(
        version_id,
        payload.start_offset,
        payload.end_offset,
        provider,
        external_authorized=authorization is not None,
    )
    return AnalysisRunOut.model_validate(run, from_attributes=True)


@router.get("/analysis/provider", response_model=ProviderStatusOut)
def provider_status(request: Request) -> ProviderStatusOut:
    """Qué proveedor está configurado. No llama a ningún servicio ni devuelve secretos."""
    settings = request.app.state.settings
    try:
        provider = resolve_provider(settings.analysis_provider, settings)
    except TextError as error:
        return ProviderStatusOut(
            configured=False,
            name=settings.analysis_provider,
            label=None,
            is_simulated=None,
            is_external=None,
            model_name=settings.anthropic_model if settings.analysis_provider == "anthropic" else None,
            reason=str(error),
        )
    return ProviderStatusOut(
        configured=True,
        name=provider.name,
        label=provider.label,
        is_simulated=provider.is_simulated,
        is_external=provider.is_external,
        model_name=getattr(provider, "model", None),
    )


@router.get("/versions/{version_id}/analyses", response_model=list[AnalysisRunOut])
def list_analyses(
    version_id: int,
    service: AnalysisService = Depends(get_analysis_service),
) -> list[AnalysisRunOut]:
    """Análisis guardados de una versión."""
    return [AnalysisRunOut.model_validate(run, from_attributes=True) for run in service.list_runs(version_id)]
