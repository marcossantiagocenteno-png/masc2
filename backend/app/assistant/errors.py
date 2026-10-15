"""Errores del asistente. Heredan de ``TextError`` para el mismo mapeo HTTP que el resto del backend."""

from __future__ import annotations

from app.texts.errors import TextError


class AssistantUnavailable(TextError):
    """El proveedor elegido no está configurado o no es válido. Nada se envía."""

    status_code = 503


class AssistantFailed(TextError):
    """El proveedor falló al responder. Se guarda el mensaje del usuario y un aviso del sistema, nada más."""

    status_code = 502


class AssistantOutputInvalid(TextError):
    """La respuesta del proveedor no cumple el esquema. No se crea ninguna propuesta."""

    status_code = 502


class AuthorizationRequired(TextError):
    """Un proveedor externo exige una autorización explícita del contenido exacto que se enviará."""

    status_code = 403


class ContextChanged(TextError):
    """El contenido que se enviaría ha cambiado desde la vista previa autorizada. Nada se envía."""

    status_code = 409


class ProposalInvalid(TextError):
    """La propuesta no cumple las reglas de validación. No se guarda."""

    status_code = 422
