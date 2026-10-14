"""Esquemas de la API de análisis."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AnalysisRequest(BaseModel):
    """Fragmento a analizar. No se acepta un nombre de proveedor: lo fija la configuración."""

    model_config = ConfigDict(extra="forbid")

    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=1)


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
    created_at: datetime
    findings: list[FindingOut]
