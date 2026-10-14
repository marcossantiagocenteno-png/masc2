"""Errores del dominio de borradores."""

from __future__ import annotations

from typing import Any

from app.texts.errors import ConflictError, NotFoundError


class DraftConflict(ConflictError):
    """La revisión enviada no es la actual. Nada se ha sobrescrito.

    ``payload`` describe el borrador actual y el punto de recuperación que conserva
    el texto rechazado, para que el cliente pueda reconciliar sin perder nada.
    """

    def __init__(self, message: str, payload: dict[str, Any]) -> None:
        super().__init__(message)
        self.payload = payload


class DraftNotFound(NotFoundError):
    """El manuscrito no tiene borrador o el punto de recuperación no pertenece a él."""
