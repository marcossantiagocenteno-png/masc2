"""Esquemas HTTP de planificación. Todos los campos son opcionales: el autor puede empezar con una idea incompleta."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.planning.kinds import DEVELOPMENT_STATUSES, PLOT_KINDS

OptShort = Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=200)]
OptText = Annotated[str | None, StringConstraints(max_length=20000)]
OptNarrativeText = Annotated[str | None, StringConstraints(max_length=5000)]
PlotKind = Literal["acontecimiento", "conflicto", "subtrama", "misterio", "pregunta_abierta"]
StructureKind = Literal["acto", "capitulo", "escena"]
DevelopmentStatus = Literal["idea", "planificacion", "escritura", "revision", "terminada"]

assert set(PLOT_KINDS) == set(PlotKind.__args__)  # type: ignore[attr-defined]
assert set(DEVELOPMENT_STATUSES) == set(DevelopmentStatus.__args__)  # type: ignore[attr-defined]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NarrativeIn(_Strict):
    premise: OptNarrativeText = None
    synopsis: OptText = None
    genre: OptShort = None
    theme: OptNarrativeText = None
    tone: OptShort = None
    development_status: DevelopmentStatus | None = None


class PersonajeIn(_Strict):
    name: OptShort = None
    description: OptText = None
    goals: OptText = None
    motivations: OptText = None
    conflicts: OptText = None
    evolution: OptText = None
    notes: OptText = None


class LugarIn(_Strict):
    name: OptShort = None
    description: OptText = None
    features: OptText = None
    notes: OptText = None


class ElementoTramaIn(_Strict):
    kind: PlotKind | None = None
    title: OptShort = None
    description: OptText = None
    notes: OptText = None


class AcontecimientoIn(_Strict):
    title: OptShort = None
    description: OptText = None
    narrative_order: int | None = Field(default=None, ge=0, le=100000)
    story_time: OptShort = None
    notes: OptText = None


class EstructuraCreate(_Strict):
    kind: StructureKind
    parent_id: int | None = None
    title: OptShort = None
    summary: OptText = None
    notes: OptText = None


class EstructuraPatch(_Strict):
    title: OptShort = None
    summary: OptText = None
    notes: OptText = None


class ReordenarIn(_Strict):
    parent_id: int | None = None
    orden: list[int] = Field(min_length=0, max_length=5000)


class ExtremoIn(_Strict):
    tipo: str = Field(min_length=1, max_length=30)
    id: int


class VinculoIn(_Strict):
    origen: ExtremoIn
    destino: ExtremoIn
    relacion: str = Field(min_length=1, max_length=40)
    propuesta: bool = False


class AprobacionIn(_Strict):
    confirmar: bool = False
    nota: OptText = None
