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
