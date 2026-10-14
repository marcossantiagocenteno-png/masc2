"""Esquemas HTTP de borradores y puntos de recuperación."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DraftOut(BaseModel):
    """Borrador actual. ``revision`` es la que el cliente debe enviar en su próxima escritura."""

    model_config = ConfigDict(from_attributes=True)

    manuscript_id: int
    revision: int
    content: str
    char_count: int
    sha256: str
    base_version_id: int | None
    created_at: datetime
    updated_at: datetime


class DraftInitOut(BaseModel):
    """Resultado de inicializar: ``created`` indica si el borrador es nuevo."""

    created: bool
    draft: DraftOut


class DraftSave(BaseModel):
    content: str
    base_revision: int = Field(ge=1)
    # Guarda el contenido anterior como punto antes_de_sobrescribir (p. ej. «Mantener mi texto»).
    keep_previous: bool = False


class RestoreIn(BaseModel):
    base_revision: int = Field(ge=1)


class RecoveryPointSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    manuscript_id: int
    reason: str
    char_count: int
    sha256: str
    draft_revision: int
    created_at: datetime


class RecoveryPointOut(RecoveryPointSummary):
    content: str
