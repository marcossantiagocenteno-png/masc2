"""Esquemas de la API de análisis."""

from __future__ import annotations

from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExternalAuthorization(BaseModel):
    """Autorización explícita para enviar el fragmento a un proveedor externo.

    Viaja en cada petición y no se guarda. ``provider`` debe coincidir con el
    proveedor configurado, y ``scope`` limita el envío al fragmento seleccionado.
    """

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1, max_length=60)
    scope: Literal["fragmento_seleccionado"]
    acknowledged: Literal[True]


class AnalysisRequest(BaseModel):
    """Fragmento a analizar. No se acepta un nombre de proveedor: lo fija la configuración."""

    model_config = ConfigDict(extra="forbid")

    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=1)
    external_authorization: ExternalAuthorization | None = None


class ProviderStatusOut(BaseModel):
    """Estado del proveedor configurado. No contiene ningún secreto."""

    configured: bool
    name: str | None
    label: str | None
    is_simulated: bool | None
    is_external: bool | None
    model_name: str | None
    reason: str | None = None


class FindingOut(BaseModel):
    """Hallazgo guardado."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    provenance: str
    source_name: str
    quote: str
    start_offset: int
    end_offset: int
    line_number: int
    explanation: str
    effect: str | None
    certainty: str
    justification: str | None


class AnalysisRunOut(BaseModel):
    """Análisis con su fragmento, el proveedor usado y sus hallazgos."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    version_id: int
    fragment_start: int
    fragment_end: int
    fragment_text: str
    provider_name: str
    provider_label: str
    provider_simulated: bool
    model_name: str | None
    sent_external: bool
    created_at: datetime
    findings: list[FindingOut]
