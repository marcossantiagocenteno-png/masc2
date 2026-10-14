"""Pertenencia de manuscritos a proyectos y guardas de escritura.

Contrato: una operación acotada a un proyecto (``/projects/{p}/manuscripts/{m}/...``) solo actúa si el
manuscrito pertenece a ese proyecto. Si no pertenece, o no existe, la respuesta es la misma 404: no se
revela si el id existe en otra novela. Esto es aislamiento entre proyectos, no autenticación: la aplicación
es local y de un solo usuario.

Las rutas heredadas (``/manuscripts/{m}/...``) no reciben proyecto y se mantienen para los manuscritos sin
proyecto. Para un manuscrito de escena, sus escrituras heredadas se rechazan: el texto solo se escribe por
la ruta de escena o por la ruta acotada, que sí comprueban el archivado.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Manuscript, ManuscriptVersion, Project, SceneManuscript
from app.texts.errors import NotFoundError, ValidationFailed


def project_or_404(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"no existe el proyecto {project_id}")
    return project


def manuscript_in_project(session: Session, project_id: int, manuscript_id: int) -> Manuscript:
    """Manuscrito del proyecto, o 404. Mismo mensaje si no existe o es de otra novela."""
    project_or_404(session, project_id)
    manuscript = session.get(Manuscript, manuscript_id)
    if manuscript is None or manuscript.project_id != project_id:
        raise NotFoundError(f"no existe el manuscrito {manuscript_id} en el proyecto {project_id}")
    return manuscript


def version_in_manuscript(session: Session, project_id: int, manuscript_id: int, version_id: int) -> ManuscriptVersion:
    manuscript_in_project(session, project_id, manuscript_id)
    version = session.get(ManuscriptVersion, version_id)
    if version is None or version.manuscript_id != manuscript_id:
        raise NotFoundError(f"no existe la versión {version_id} en el manuscrito {manuscript_id}")
    return version


def require_writable(session: Session, project_id: int) -> None:
    """Las escrituras acotadas no se admiten en proyectos archivados, igual que la planificación."""
    if project_or_404(session, project_id).status == "archivado":
        raise ValidationFailed("el proyecto está archivado; no admite cambios en sus manuscritos")


def scene_node_id(session: Session, manuscript_id: int) -> int | None:
    """Escena que escribe este manuscrito, o ``None`` si no es de escena."""
    return session.scalar(select(SceneManuscript.node_id).where(SceneManuscript.manuscript_id == manuscript_id))


def reject_legacy_write_for_scene(session: Session, manuscript_id: int) -> None:
    """Las rutas heredadas no escriben sobre el texto de una escena: se usa su ruta o la acotada."""
    if scene_node_id(session, manuscript_id) is not None:
        raise ValidationFailed(
            "este manuscrito es el texto de una escena: escríbelo desde la estructura o con la ruta del proyecto"
        )
