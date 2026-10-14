"""Servicio de proyectos. Confirma cada operación."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import utc_now
from app.db.models import Manuscript, ManuscriptVersion, Project, SceneManuscript
from app.texts.errors import NotFoundError, ValidationFailed
from app.texts.service import TextService

ACTIVE = "activo"
ARCHIVED = "archivado"
STATUSES = (ACTIVE, ARCHIVED)


# Manuscritos de escena: su texto se muestra desde la estructura, no en la lista del proyecto.
_SCENE_MANUSCRIPTS = select(SceneManuscript.manuscript_id)

class ProjectService:
    """Operaciones sobre proyectos y los manuscritos que contienen."""

    def __init__(self, session: Session, texts: TextService) -> None:
        self._session = session
        self._texts = texts

    def list_projects(self, status: str | None = ACTIVE) -> Sequence[Project]:
        """Proyectos de un estado (o todos si ``status`` es nulo), del más reciente al más antiguo."""
        if status is not None and status not in STATUSES:
            raise ValidationFailed(f"estado no válido: '{status}'")
        query = select(Project).order_by(Project.updated_at.desc(), Project.id.desc())
        if status is not None:
            query = query.where(Project.status == status)
        return list(self._session.scalars(query).all())

    def get_project(self, project_id: int) -> Project:
        project = self._session.get(Project, project_id)
        if project is None:
            raise NotFoundError(f"no existe el proyecto {project_id}")
        return project

    def create_project(self, name: str) -> Project:
        now = utc_now()
        project = Project(name=name, status=ACTIVE, created_at=now, updated_at=now)
        self._session.add(project)
        self._session.commit()
        return project

    def rename_project(self, project_id: int, name: str) -> Project:
        project = self.get_project(project_id)
        project.name = name
        project.updated_at = utc_now()
        self._session.commit()
        return project

    def archive_project(self, project_id: int) -> Project:
        project = self.get_project(project_id)
        if project.status == ARCHIVED:
            raise ValidationFailed("el proyecto ya está archivado")
        now = utc_now()
        project.status = ARCHIVED
        project.archived_at = now
        project.updated_at = now
        self._session.commit()
        return project

    def restore_project(self, project_id: int) -> Project:
        project = self.get_project(project_id)
        if project.status == ACTIVE:
            raise ValidationFailed("el proyecto no está archivado")
        project.status = ACTIVE
        project.archived_at = None
        project.updated_at = utc_now()
        self._session.commit()
        return project

    def list_manuscripts(self, project_id: int) -> Sequence[Manuscript]:
        self.get_project(project_id)
        return list(
            self._session.scalars(
                select(Manuscript)
                .where(Manuscript.project_id == project_id, Manuscript.id.not_in(_SCENE_MANUSCRIPTS))
                .order_by(Manuscript.id.desc())
            ).all()
        )

    def create_manuscript(self, project_id: int, title: str, content: str, note: str | None) -> Manuscript:
        project = self.get_project(project_id)
        if project.status == ARCHIVED:
            raise ValidationFailed("el proyecto está archivado: restáuralo antes de añadir manuscritos")
        manuscript = self._texts.create_manuscript(title, content, note, project_id=project_id)
        project.updated_at = utc_now()
        self._session.commit()
        return manuscript

    def stats(self, project_id: int) -> tuple[int, datetime | None]:
        """Número de manuscritos y fecha de la última versión creada en el proyecto."""
        self.get_project(project_id)
        count = self._session.scalar(
            select(func.count(Manuscript.id)).where(
                Manuscript.project_id == project_id, Manuscript.id.not_in(_SCENE_MANUSCRIPTS)
            )
        ) or 0
        last = self._session.scalar(
            select(func.max(ManuscriptVersion.created_at))
            .join(Manuscript, Manuscript.id == ManuscriptVersion.manuscript_id)
            .where(Manuscript.project_id == project_id, Manuscript.id.not_in(_SCENE_MANUSCRIPTS))
        )
        return int(count), last
