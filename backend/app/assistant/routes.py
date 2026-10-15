"""Rutas del asistente, siempre bajo el proyecto. Toda consulta filtra por ``project_id``."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.assistant.schemas import (
    CompletarIn,
    MensajeIn,
    VistaPreviaIn,
    memoria_a_dict,
    mensaje_a_dict,
    propuesta_a_dict,
)
from app.assistant.service import AssistantService
from app.texts.routes import get_session

router = APIRouter(prefix="/projects/{project_id}/asistente")


def get_service(request: Request, session: Session = Depends(get_session)) -> AssistantService:
    return AssistantService(
        session,
        request.app.state.settings,
        client_factory=getattr(request.app.state, "assistant_client_factory", None),
        clock=request.app.state.clock,
    )


def _respuesta_mensajes(service: AssistantService, resultado: dict[str, Any]) -> dict[str, Any]:
    propuestas = [
        propuesta_a_dict(p, service.actual_de(p), service.base_cambiada(p)) for p in resultado["propuestas"]
    ]
    return {
        "mensajes": [mensaje_a_dict(m) for m in resultado["mensajes"]],
        "propuestas": propuestas,
        "error": resultado["error"],
    }


@router.get("")
def estado(project_id: int, service: AssistantService = Depends(get_service)) -> dict[str, Any]:
    """Chat de la novela con su historial y el proveedor que respondería ahora."""
    conversacion = service.conversacion(project_id)
    proveedor = service.proveedor()
    return {
        "conversacion_id": conversacion.id,
        "mensajes": [mensaje_a_dict(m) for m in service.mensajes(project_id)],
        "proveedor": {"nombre": proveedor.name, "simulado": proveedor.is_simulated, "externo": proveedor.is_external},
    }


@router.post("/vista-previa")
def vista_previa(project_id: int, payload: VistaPreviaIn, service: AssistantService = Depends(get_service)) -> dict[str, Any]:
    """Contenido exacto que se enviaría. Un proveedor externo exige autorizar esta huella."""
    return service.vista_previa(project_id, payload.texto)


@router.post("/mensajes")
def enviar(project_id: int, payload: MensajeIn, service: AssistantService = Depends(get_service)) -> dict[str, Any]:
    resultado = service.enviar(project_id, payload.client_id, payload.texto, payload.autorizacion_hash)
    return _respuesta_mensajes(service, resultado)


@router.get("/propuestas")
def listar_propuestas(
    project_id: int,
    estado: str | None = Query(default=None, max_length=20),
    service: AssistantService = Depends(get_service),
) -> list[dict[str, Any]]:
    return [propuesta_a_dict(p, service.actual_de(p), service.base_cambiada(p)) for p in service.propuestas(project_id, estado)]


@router.post("/propuestas/{proposal_id}/aprobar")
def aprobar(project_id: int, proposal_id: int, service: AssistantService = Depends(get_service)) -> dict[str, Any]:
    propuesta = service.aprobar(project_id, proposal_id)
    return propuesta_a_dict(propuesta, service.actual_de(propuesta), service.base_cambiada(propuesta))


@router.post("/propuestas/{proposal_id}/rechazar")
def rechazar(project_id: int, proposal_id: int, service: AssistantService = Depends(get_service)) -> dict[str, Any]:
    propuesta = service.rechazar(project_id, proposal_id)
    return propuesta_a_dict(propuesta, service.actual_de(propuesta), service.base_cambiada(propuesta))


@router.get("/memoria")
def memoria(project_id: int, service: AssistantService = Depends(get_service)) -> list[dict[str, Any]]:
    return [memoria_a_dict(item) for item in service.memoria(project_id)]


@router.post("/autocompletar/vista-previa")
def vista_previa_completado(project_id: int, payload: CompletarIn, service: AssistantService = Depends(get_service)) -> dict[str, Any]:
    return service.vista_previa_completado(
        project_id, payload.entidad, payload.campo, payload.entidad_id, payload.actual, payload.instruccion
    )


@router.post("/autocompletar")
def autocompletar(project_id: int, payload: CompletarIn, service: AssistantService = Depends(get_service)) -> dict[str, Any]:
    return service.autocompletar(
        project_id,
        payload.entidad,
        payload.campo,
        payload.entidad_id,
        payload.actual,
        payload.instruccion,
        payload.autorizacion_hash,
    )
