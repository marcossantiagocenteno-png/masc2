"""Errores de dominio. Cada uno indica el código HTTP que le corresponde."""

from __future__ import annotations


class TextError(Exception):
    """Base de los errores de dominio de textos."""

    status_code: int = 400


class NotFoundError(TextError):
    """El recurso no existe."""

    status_code = 404


class ValidationFailed(TextError):
    """La petición no cumple las reglas del dominio."""

    status_code = 422


class ContentTooLarge(TextError):
    """El contenido supera el límite configurado."""

    status_code = 413


class ConflictError(TextError):
    """Conflicto de concurrencia, por ejemplo dos versiones con el mismo número."""

    status_code = 409


class IntegrityFailure(TextError):
    """El contenido almacenado no coincide con su hash. Nunca se devuelve el texto."""

    status_code = 500
