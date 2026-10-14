"""Interfaz de proveedores de análisis y resolución por configuración.

Un proveedor recibe el texto de un fragmento y devuelve hallazgos con cita y
posición dentro de ese fragmento. El servicio valida cada hallazgo antes de
guardarlo, así que un proveedor no puede inventar una cita sin que se note.

Solo existe un proveedor incluido: el analizador simulado. Añadir un proveedor
real exige código nuevo, una entrada en ``PROVIDER_FACTORIES`` y una decisión
explícita de envío de datos. No hay ningún proveedor externo configurado.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from app.analysis.errors import ProviderUnavailable


@dataclass(frozen=True)
class ProviderFinding:
    """Hallazgo tal como lo devuelve un proveedor o una verificación.

    ``quote_offset`` es la posición de la cita dentro del fragmento analizado,
    no dentro de la versión completa.
    """

    category: str
    quote: str
    quote_offset: int
    explanation: str
    effect: str | None
    certainty: str


class AnalysisProvider(Protocol):
    """Contrato de un proveedor de análisis."""

    name: str
    label: str
    is_simulated: bool

    def analyze(self, fragment: str) -> list[ProviderFinding]:
        """Devuelve hallazgos sobre el fragmento. No modifica nada."""
        ...


def _simulated_factory() -> AnalysisProvider:
    from app.analysis.simulated import SimulatedAnalyzer

    return SimulatedAnalyzer()


PROVIDER_FACTORIES: dict[str, Callable[[], AnalysisProvider]] = {
    "simulado": _simulated_factory,
}


def resolve_provider(name: str) -> AnalysisProvider:
    """Devuelve el proveedor configurado o lanza ``ProviderUnavailable``."""
    factory = PROVIDER_FACTORIES.get(name)
    if factory is None:
        available = ", ".join(sorted(PROVIDER_FACTORIES))
        raise ProviderUnavailable(
            f"El proveedor '{name}' no está autorizado ni configurado en esta instalación. "
            f"Proveedores disponibles: {available}."
        )
    return factory()
