"""Aplicación FastAPI de Novel Engine.

Endpoints:

- ``GET /health``: estado del servicio.
- ``/manuscripts``, ``/versions``: textos, versiones y revisiones editoriales (ver ``app.texts.routes``).

La base de datos debe estar migrada antes de arrancar: ``python -m alembic upgrade head``.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app import __version__
from app.config import Settings, load_settings
from app.db.session import create_engine_for, create_session_factory
from app.texts.errors import TextError
from app.texts.routes import router as texts_router


class HealthResponse(BaseModel):
    """Respuesta del endpoint de salud."""

    status: str
    service: str
    version: str


def create_app(settings: Settings | None = None) -> FastAPI:
    """Crea la aplicación con la configuración indicada o la del entorno."""
    settings = settings or load_settings()
    engine = create_engine_for(settings.database_url)

    application = FastAPI(title="Novel Engine", version=__version__)
    application.state.settings = settings
    application.state.engine = engine
    application.state.session_factory = create_session_factory(engine)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @application.exception_handler(TextError)
    def _handle_text_error(_request: Request, error: TextError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"detail": str(error)})

    @application.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        """Indica que el servicio responde."""
        return HealthResponse(status="ok", service="novel-engine-backend", version=__version__)

    application.include_router(texts_router)
    return application


app = create_app()
