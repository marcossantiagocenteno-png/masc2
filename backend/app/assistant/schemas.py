"""Esquemas HTTP del asistente. Estrictos: un campo desconocido es un error, no se ignora."""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.assistant.service import MAX_TEXTO_MENSAJE

ClientId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=64)]
Texto = Annotated[str, StringConstraints(max_length=MAX_TEXTO_MENSAJE)]
Huella = Annotated[str | None, StringConstraints(max_length=64)]
Entidad = Literal["personaje", "lugar", "elemento_trama", "acontecimiento", "premisa"]
Campo = Annotated[str, StringConstraints(max_length=40)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VistaPreviaIn(_Strict):
    texto: Texto


class MensajeIn(_Strict):
    client_id: ClientId
    texto: Texto
    autorizacion_hash: Huella = None


class CompletarIn(_Strict):
    entidad: Entidad
    campo: Campo
    entidad_id: int | None = None
    actual: Annotated[str, StringConstraints(max_length=MAX_TEXTO_MENSAJE)] = ""
    instruccion: Annotated[str | None, StringConstraints(max_length=500)] = None
    autorizacion_hash: Huella = None


def mensaje_a_dict(mensaje: Any) -> dict[str, Any]:
    return {
        "id": mensaje.id,
        "client_id": mensaje.client_id,
        "role": mensaje.role,
        "content": mensaje.content,
        "proveedor": mensaje.proveedor,
        "simulado": mensaje.simulado,
        "created_at": mensaje.created_at,
    }


def propuesta_a_dict(propuesta: Any, actual: dict[str, Any], base_cambiada: bool) -> dict[str, Any]:
    return {
        "id": propuesta.id,
        "message_id": propuesta.message_id,
        "operacion": propuesta.operacion,
        "entidad": propuesta.entidad,
        "target_id": propuesta.target_id,
        "datos": json.loads(propuesta.datos),
        "actual": actual,
        "motivo": propuesta.motivo,
        "estado": propuesta.estado,
        "resultado": propuesta.resultado,
        "resultado_id": propuesta.resultado_id,
        "base_cambiada": base_cambiada,
        "created_at": propuesta.created_at,
        "decided_at": propuesta.decided_at,
        "applied_at": propuesta.applied_at,
    }


def memoria_a_dict(item: Any) -> dict[str, Any]:
    return {
        "id": item.id,
        "kind": item.kind,
        "texto": item.texto,
        "proposal_id": item.proposal_id,
        "updated_at": item.updated_at,
    }
