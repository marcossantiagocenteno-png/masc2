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
    """Versión del manuscrito, dentro del proyecto. Inexistente, de otro manuscrito o de otro proyecto: el mismo 404."""
    # El mismo mensaje para «no existe» y «es de otro proyecto»: no debe revelar ni el id ni la novela.
    not_found = NotFoundError("no existe esa versión en este manuscrito del proyecto indicado")
    version = session.get(ManuscriptVersion, version_id)
    if version is None or version.manuscript_id != manuscript_id:
        raise not_found
    manuscript = session.get(Manuscript, manuscript_id)
    if manuscript is None or manuscript.project_id != project_id:
        raise not_found
    return version


def require_writable(session: Session, project_id: int) -> None:
    """Las escrituras acotadas no se admiten en proyectos archivados, igual que la planificación."""
    if project_or_404(session, project_id).status == "archivado":
        raise ValidationFailed("el proyecto está archivado; no admite cambios en sus manuscritos")


def scene_node_id(session: Session, manuscript_id: int) -> int | None:
    """Escena que escribe este manuscrito, o ``None`` si no es de escena."""
    return session.scalar(select(SceneManuscript.node_id).where(SceneManuscript.manuscript_id == manuscript_id))


LEGACY_HINT = (
    "este manuscrito pertenece a un proyecto: usa la ruta /projects/{p}/manuscripts/{m}/… "
    "(las rutas sin proyecto no lo atienden)"
)


def guard_manuscript_legacy(session: Session, manuscript_id: int, *, write: bool) -> None:
    """Las rutas heredadas no atienden contenido de manuscritos con proyecto.

    Sin esta guarda, un id de cualquier novela sería accesible por una ruta que no comprueba pertenencia.
    La lectura responde 404 y la escritura 422, y ninguna escribe nada. Los manuscritos sin proyecto siguen igual.
    El metadato (``GET /manuscripts/{id}``) no pasa por aquí: sirve para descubrir el proyecto.
    """
    manuscript = session.get(Manuscript, manuscript_id)
    if manuscript is None or manuscript.project_id is None:
        return
    if write:
        raise ValidationFailed(LEGACY_HINT)
    raise NotFoundError(LEGACY_HINT)


def guard_version_legacy(session: Session, version_id: int, *, write: bool) -> None:
    version = session.get(ManuscriptVersion, version_id)
    if version is not None:
        guard_manuscript_legacy(session, version.manuscript_id, write=write)
