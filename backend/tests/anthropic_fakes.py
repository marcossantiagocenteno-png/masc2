"""Doble del SDK de Anthropic para pruebas. Nunca hace ninguna petición de red.

Registra cada llamada a ``messages.create`` y devuelve la respuesta preparada
por el test, o lanza el error indicado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.analysis.anthropic_provider import TOOL_NAME

API_KEY = "sk-ant-api03-SECRETO-DE-PRUEBA-NO-REAL"
MODEL = "modelo-de-prueba"


@dataclass
class FakeBlock:
    type: str
    name: str | None = None
    input: Any = None


@dataclass
class FakeMessage:
    content: list[FakeBlock] = field(default_factory=list)
    stop_reason: str = "tool_use"


def tool_response(findings: list[dict[str, Any]], stop_reason: str = "tool_use") -> FakeMessage:
    """Respuesta correcta: un bloque ``tool_use`` con el diagnóstico."""
    return FakeMessage(
        content=[FakeBlock(type="tool_use", name=TOOL_NAME, input={"findings": findings})],
        stop_reason=stop_reason,
    )


def valid_finding(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "category": "observacion_literaria",
        "quote": "La lluvia caía",
        "occurrence": 1,
        "observation": "La imagen abre la escena con un fenómeno exterior.",
        "effect": "Sitúa al lector antes de cualquier personaje.",
        "justification": "La cita contiene el sintagma nominal que sostiene la observación.",
        "certainty": "media",
    }
    data.update(overrides)
    return data


class _Messages:
    def __init__(self, owner: FakeClaude) -> None:
        self._owner = owner

    def create(self, **kwargs: Any) -> FakeMessage:
        self._owner.calls.append(kwargs)
        if self._owner.error is not None:
            raise self._owner.error
        return self._owner.response


class FakeClient:
    def __init__(self, owner: FakeClaude) -> None:
        self.messages = _Messages(owner)


class FakeClaude:
    """Fábrica de clientes falsos. ``calls`` cuenta las llamadas reales al proveedor."""

    def __init__(self, response: FakeMessage | None = None, error: BaseException | None = None) -> None:
        self.response = response if response is not None else tool_response([valid_finding()])
        self.error = error
        self.calls: list[dict[str, Any]] = []
        self.constructed: list[tuple[str, float]] = []

    def factory(self, api_key: str, timeout_seconds: float) -> FakeClient:
        self.constructed.append((api_key, timeout_seconds))
        return FakeClient(self)
