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
    """Visión general. «synopsis» se acepta para no tocar datos existentes, pero la interfaz ya no lo envía.
    Los géneros tienen su propio endpoint (``GenerosIn``)."""

    premise: OptNarrativeText = None
    synopsis: OptText = None
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
    confirmar_cambio_canon: bool = False


class MoverIn(_Strict):
    parent_id: int | None = None
    posicion: int | None = Field(default=None, ge=0, le=5000)
    confirmar_cambio_canon: bool = False


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


class GeneroIn(_Strict):
    key: str = Field(min_length=1, max_length=40)
    custom_label: OptShort = None


class GenerosIn(_Strict):
    generos: list[GeneroIn] = Field(default_factory=list, max_length=30)


class DirectricesIn(_Strict):
    voz: OptShort = None
    persona: Literal["primera", "segunda", "tercera"] | None = None
    tiempo_verbal: Literal["presente", "pasado", "futuro", "mixto"] | None = None
    tipo_narrador: Literal["narrador_personaje", "narrador_externo"] | None = None
    punto_de_vista: Literal["un_personaje", "varios_personajes", "omnisciente"] | None = None
    focalizacion: Literal["interna_fija", "interna_variable", "externa", "omnisciente"] | None = None
    estilo: OptText = None
    intencion: OptText = None
    limites: OptText = None
    instrucciones: OptText = None



class ModeloEstructuraIn(_Strict):
    model_key: str = Field(min_length=1, max_length=40)


class GenerarPropuestasIn(_Strict):
    model_key: str | None = Field(default=None, min_length=1, max_length=40)


class PropuestaEstructuraPatch(_Strict):
    title: str | None = Field(default=None, max_length=200)
    summary: str | None = Field(default=None, max_length=4000)
