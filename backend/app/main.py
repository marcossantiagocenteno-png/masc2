"""Aplicación FastAPI de Novel Engine.

En esta fase solo expone ``GET /health``. Los endpoints de manuscritos,
generación y evaluación todavía no existen y no tienen especificación.
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from app import __version__


class HealthResponse(BaseModel):
    """Respuesta del endpoint de salud."""

    status: str
    service: str
    version: str


def create_app() -> FastAPI:
    """Crea la aplicación. Una función facilita las pruebas con instancias limpias."""
    application = FastAPI(title="Novel Engine", version=__version__)

    @application.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        """Indica que el servicio responde."""
        return HealthResponse(status="ok", service="novel-engine-backend", version=__version__)

    return application


app = create_app()
