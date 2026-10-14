"""Errores del análisis editorial. Heredan de ``TextError`` para usar el mismo mapeo HTTP."""

from __future__ import annotations

from app.texts.errors import TextError


class ProviderUnavailable(TextError):
    """No hay ningún proveedor autorizado y configurado con ese nombre."""

    status_code = 503


class ProviderFailed(TextError):
    """El proveedor produjo un error. No se guarda nada."""

    status_code = 502


class FindingsRejected(TextError):
    """El proveedor devolvió hallazgos que no cumplen las reglas. No se guarda nada."""

    status_code = 502


class ProviderOutputInvalid(TextError):
    """La respuesta del proveedor no cumple el esquema o sus citas no existen. No se guarda nada."""

    status_code = 502


class AuthorizationRequired(TextError):
    """El análisis necesita una autorización explícita de envío externo, y la petición no la incluye."""

    status_code = 403
