"""Aplicación FastAPI de Novel Engine.

Endpoints:

- ``GET /health``: estado del servicio.
- ``/manuscripts``, ``/versions``: textos, versiones y revisiones editoriales (ver ``app.texts.routes``).
- ``/versions/{id}/analyses``: análisis editorial de fragmentos (ver ``app.analysis.routes``).
- ``/projects``: proyectos (novelas) aislados, archivables y restaurables (ver ``app.projects.routes``).
- ``/manuscripts/{id}/draft`` y ``/recovery-points``: borradores y puntos de recuperación (ver ``app.drafts.routes``).

La base de datos debe estar migrada antes de arrancar: ``python -m alembic upgrade head``.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app import __version__
from app.config import Settings, load_settings
from app.backups.runtime import start_background, stop_background
from app.db.base import utc_now
from app.db.esquema import estado_del_esquema
from app.db.session import create_engine_for, create_session_factory
from app.drafts.errors import DraftConflict
from app.drafts.routes import router as drafts_router
from app.analysis.routes import router as analysis_router
from app.planning.routes import router as planning_router
from app.assistant.routes import router as assistant_router
from app.projects.routes import router as projects_router
from app.projects.scoped_routes import router as scoped_manuscripts_router
from app.texts.errors import TextError
from app.texts.routes import router as texts_router

logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    """Respuesta del endpoint de salud. ``esquema.al_dia`` indica si la base está migrada hasta la última revisión."""

    status: str
    service: str
    version: str
    esquema: dict[str, Any]


def _cabeceras_cors(request: Request, origenes: tuple[str, ...]) -> dict[str, str]:
    """Cabeceras CORS para una respuesta generada fuera del middleware (errores no controlados)."""
    origen = request.headers.get("origin")
    if origen is None or origen not in origenes:
        return {}
    return {"Access-Control-Allow-Origin": origen, "Vary": "Origin"}


def create_app(settings: Settings | None = None) -> FastAPI:
    """Crea la aplicación con la configuración indicada o la del entorno."""
    settings = settings or load_settings()
    engine = create_engine_for(settings.database_url)

    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
        esquema = estado_del_esquema(engine)
        if not esquema["al_dia"]:
            logger.warning(
                "La base de datos no está migrada (revisión actual: %s; esperada: %s). "
                "Las rutas nuevas fallarán. Ejecuta: python -m alembic upgrade head",
                esquema["revision_actual"],
                esquema["revision_esperada"],
            )
        # Marcador de ejecución y copias automáticas. Ver app/backups/runtime.py.
        background = start_background(settings, application.state.clock)
        try:
            yield
        finally:
            stop_background(settings, background)

    application = FastAPI(title="Novel Engine", version=__version__, lifespan=lifespan)
    application.state.settings = settings
    application.state.engine = engine
    application.state.session_factory = create_session_factory(engine)
    # Reloj inyectable: las pruebas lo sustituyen para controlar los intervalos de los puntos.
    application.state.clock = utc_now

    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST", "PUT", "PATCH"],
        allow_headers=["Content-Type"],
    )

    @application.exception_handler(TextError)
    def _handle_text_error(_request: Request, error: TextError) -> JSONResponse:
        content: dict[str, object] = {"detail": str(error)}
        if isinstance(error, DraftConflict):
            content.update(error.payload)
        return JSONResponse(status_code=error.status_code, content=content)

    @application.exception_handler(Exception)
    def _handle_unexpected(request: Request, error: Exception) -> JSONResponse:
        # Sin cabeceras CORS, el navegador mostraría este error como fallo de conexión. Aquí se devuelve el detalle.
        logger.error("Error no controlado en %s %s", request.method, request.url.path, exc_info=error)
        return JSONResponse(
            status_code=500,
            content={"detail": "Error interno del servidor. Revisa el registro del backend."},
            headers=_cabeceras_cors(request, settings.cors_origins),
        )

    @application.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        """Indica que el servicio responde y si la base está migrada."""
        return HealthResponse(
            status="ok",
            service="novel-engine-backend",
            version=__version__,
            esquema=estado_del_esquema(engine),
        )

    application.include_router(texts_router)
    application.include_router(analysis_router)
    application.include_router(projects_router)
    application.include_router(scoped_manuscripts_router)
    application.include_router(drafts_router)
    application.include_router(planning_router)
    application.include_router(assistant_router)
    return application


app = create_app()
