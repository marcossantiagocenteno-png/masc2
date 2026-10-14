"""Dobles de prueba de proveedores de análisis.

No son analizadores. Sirven para comprobar que el servicio rechaza hallazgos
inválidos y guarda los válidos. Nunca se registran en la aplicación.
"""

from __future__ import annotations

from collections.abc import Callable

from app.analysis.provider import ProviderFinding

FindingsFn = Callable[[str], list[ProviderFinding]]


class ScriptedProvider:
    """Proveedor de prueba cuyos hallazgos define cada test."""

    name = "doble-de-prueba"
    label = "DOBLE DE PRUEBA: no es un analizador real."
    is_simulated = True

    def __init__(self, findings: FindingsFn) -> None:
        self._findings = findings

    def analyze(self, fragment: str) -> list[ProviderFinding]:
        return self._findings(fragment)


class FailingProvider:
    """Proveedor de prueba que siempre falla."""

    name = "fallido-de-prueba"
    label = "FALLIDO DE PRUEBA"
    is_simulated = True

    def analyze(self, fragment: str) -> list[ProviderFinding]:
        raise RuntimeError("fallo simulado del proveedor")


def observation(fragment: str, quote: str, offset: int | None = None, **overrides: object) -> ProviderFinding:
    """Observación literaria con valores válidos por defecto, salvo los indicados."""
    data: dict[str, object] = {
        "category": "observacion_literaria",
        "quote": quote,
        "quote_offset": fragment.index(quote) if offset is None else offset,
        "explanation": "La frase concentra la acción en una sola imagen.",
        "effect": "El lector percibe la inmovilidad del personaje.",
        "certainty": "media",
    }
    data.update(overrides)
    return ProviderFinding(**data)  # type: ignore[arg-type]
