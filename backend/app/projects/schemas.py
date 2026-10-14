"""Esquemas de la API de proyectos."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

ProjectName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ProjectName


class ProjectRename(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ProjectName


class ProjectOut(BaseModel):
    id: int
    name: str
    status: str
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class ProjectDetail(ProjectOut):
    manuscript_count: int
    last_activity_at: datetime | None
