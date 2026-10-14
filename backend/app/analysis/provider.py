"""Interfaz de proveedores de análisis y resolución por configuración.

Un proveedor recibe el texto de un fragmento y devuelve hallazgos con cita y
posición dentro de ese fragmento. El servicio valida cada hallazgo antes de
guardarlo, así que un proveedor no puede inventar una cita sin que se note.

Proveedores:

- ``simulado`` (por defecto): local, sin llamadas externas.
- ``anthropic``: envía el fragmento a la API de Anthropic. Solo se usa si la
  configuración lo elige **y** cada petición lleva una autorización explícita
  (ver ``app.analysis.routes`` y ``app.analysis.service``). La configuración
  nunca autoriza el envío por sí sola.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from app.analysis.errors import ProviderUnavailable
from app.config import Settings


@dataclass(frozen=True)
class ProviderFinding:
    """Hallazgo tal como lo devuelve un proveedor o una verificación.

    ``quote_offset`` es la posición de la cita dentro del fragmento analizado,
    no dentro de la versión completa. ``justification`` es obligatoria para
    los hallazgos de proveedor; las verificaciones deterministas no la usan.
    """

    category: str
    quote: str
    quote_offset: int
    explanation: str
    effect: str | None
    certainty: str
    justification: str | None = None


class AnalysisProvider(Protocol):
    """Contrato de un proveedor de análisis."""

    name: str
    label: str
    is_simulated: bool
    is_external: bool

    def analyze(self, fragment: str) -> list[ProviderFinding]:
        """Devuelve hallazgos sobre el fragmento. No modifica nada."""
        ...


def _simulated_factory(_settings: Settings | None) -> AnalysisProvider:
    from app.analysis.simulated import SimulatedAnalyzer

    return SimulatedAnalyzer()


def _anthropic_factory(settings: Settings | None) -> AnalysisProvider:
    from app.analysis.anthropic_provider import AnthropicAnalyzer

    if settings is None or not settings.anthropic_api_key:
        raise ProviderUnavailable(
            "El proveedor 'anthropic' está elegido, pero falta ANTHROPIC_API_KEY en la configuración del backend."
        )
    if not settings.anthropic_model:
        raise ProviderUnavailable(
            "El proveedor 'anthropic' está elegido, pero falta NOVEL_ENGINE_ANTHROPIC_MODEL. "
            "Indica un identificador de modelo que tu cuenta admita."
        )
    return AnthropicAnalyzer(
        api_key=settings.anthropic_api_key,
        model=settings.anthropic_model,
        timeout_seconds=settings.anthropic_timeout_seconds,
        max_output_tokens=settings.anthropic_max_output_tokens,
    )


PROVIDER_FACTORIES: dict[str, Callable[[Settings | None], AnalysisProvider]] = {
    "simulado": _simulated_factory,
    "anthropic": _anthropic_factory,
}


def resolve_provider(name: str, settings: Settings | None = None) -> AnalysisProvider:
    """Devuelve el proveedor elegido o lanza ``ProviderUnavailable``.

    No hay ningún recurso de respaldo: si el proveedor elegido no está
    configurado, la operación falla. No se usa otro proveedor en su lugar.
    """
    factory = PROVIDER_FACTORIES.get(name)
    if factory is None:
        available = ", ".join(sorted(PROVIDER_FACTORIES))
        raise ProviderUnavailable(
            f"El proveedor '{name}' no está autorizado ni configurado en esta instalación. "
            f"Proveedores disponibles: {available}."
        )
    return factory(settings)
