"""Esquemas Pydantic de entrada y salida de la API de textos."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Reviewer = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
CommentText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ManuscriptCreate(_Strict):
    """Creación de un manuscrito con su versión 1."""

    title: Title
    content: str = Field(default="")
    note: Note | None = None


class VersionCreate(_Strict):
    """Nueva versión. ``based_on_version_id`` registra el origen; nunca modifica la versión base."""

    content: str
    note: Note | None = None
    based_on_version_id: int | None = Field(default=None, ge=1)


class ReviewItemIn(_Strict):
    """Un comentario con cita. La cita no se recorta: debe coincidir con el texto exacto."""

    kind: str = Field(min_length=1, max_length=40)
    quote: str = Field(min_length=1, max_length=4000)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=1)
    comment: CommentText
    inference_basis: CommentText | None = None
    suggestion: CommentText | None = None
    dimension: str | None = Field(default=None, max_length=40)


class ReviewCreate(_Strict):
    """Revisión editorial de una versión concreta."""

    reviewer: Reviewer
    items: list[ReviewItemIn] = Field(min_length=1, max_length=200)


class ReviewItemOut(BaseModel):
    """Ítem de revisión tal como se guardó."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    quote: str
    start_offset: int
    end_offset: int
    line_number: int
    comment: str
    inference_basis: str | None
    suggestion: str | None
    dimension: str | None
    intent_status: str


class ReviewOut(BaseModel):
    """Revisión con sus ítems."""

    id: int
    version_id: int
    reviewer: str
    created_at: datetime
    items: list[ReviewItemOut]


class VersionSummary(BaseModel):
    """Metadatos de una versión, sin contenido."""

    id: int
    manuscript_id: int
    number: int
    sha256: str
    char_count: int
    note: str | None
    parent_version_id: int | None
    created_at: datetime


class VersionOut(VersionSummary):
    """Versión completa, con su contenido normalizado."""

    content: str
    review_count: int


class ManuscriptSummary(BaseModel):
    """Manuscrito con el número de su última versión."""

    id: int
    title: str
    created_at: datetime
    version_count: int
    latest_version_number: int
