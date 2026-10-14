"""Escritura de escenas: cada escena puede tener su manuscrito propio.

Reglas:

- El texto no se copia. La escena apunta a un manuscrito (``scene_manuscripts``) y su texto de trabajo
  es el borrador de ese manuscrito; las versiones y los puntos de recuperación son los existentes.
- Iniciar la escritura crea el manuscrito, su versión 1 vacía y su borrador en una sola transacción.
  Es idempotente: si la escena ya tiene manuscrito, lo devuelve sin crear nada.
- Guardar el texto reutiliza ``DraftService``: escritura condicional por revisión y 409 sin pérdida.
- Ninguna operación cambia la unión al mover o renombrar la escena, ni permite acceder a un manuscrito
  de otro proyecto: todo se resuelve desde el nodo, dentro del proyecto indicado.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Manuscript, ManuscriptDraft, ManuscriptVersion, Project, SceneManuscript, StructureNode
from app.drafts.service import DraftService
from app.texts.errors import NotFoundError, ValidationFailed
from app.texts.normalization import content_sha256

SIN_ESCRITURA = "sin_escritura"
SIN_TEXTO = "sin_texto"
CON_TEXTO = "con_texto"
DEFAULT_TITLE = "Escena sin título"


class SceneWritingService:
    """Escritura de escenas. Las escrituras confirman; las lecturas no modifican nada."""

    def __init__(self, session: Session, clock: Any, max_chars: int) -> None:
        self._session = session
        self._clock = clock
        self._max_chars = max_chars

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------

    def read(self, project_id: int, node_id: int) -> dict[str, Any]:
        """Estado de la escritura de una escena y su borrador (o ``None`` si no tiene escritura)."""
        self._scene(project_id, node_id)
        link = self._link(project_id, node_id)
        if link is None:
            return {"node_id": node_id, "manuscript_id": None, "state": SIN_ESCRITURA, "draft": None, "versions_count": 0}
        draft = self._session.scalar(
            select(ManuscriptDraft).where(ManuscriptDraft.manuscript_id == link.manuscript_id)
        )
        count = self._session.scalar(
            select(func.count(ManuscriptVersion.id)).where(ManuscriptVersion.manuscript_id == link.manuscript_id)
        )
        return {
            "node_id": node_id,
            "manuscript_id": link.manuscript_id,
            "state": self._state_of(link.manuscript_id),
            "draft": draft,
            "versions_count": count or 0,
        }

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------

    def start(self, project_id: int, node_id: int) -> tuple[SceneManuscript, bool]:
        """Inicia la escritura de una escena. Devuelve ``(unión, creada)``. Nunca duplica."""
        self._active(project_id)
        scene = self._scene(project_id, node_id)
        if scene.archived_at is not None:
            raise ValidationFailed("la escena está archivada; no se puede empezar a escribirla")
        existing = self._link(project_id, node_id)
        if existing is not None:
            return existing, False

        now = self._clock()
        manuscript = Manuscript(title=(scene.title or "").strip()[:200] or DEFAULT_TITLE, project_id=project_id)
        self._session.add(manuscript)
        self._session.flush()
        version = ManuscriptVersion(
            manuscript_id=manuscript.id,
            number=1,
            content="",
            sha256=content_sha256(""),
            char_count=0,
            created_at=now,
        )
        self._session.add(version)
        self._session.flush()
        self._session.add(
            ManuscriptDraft(
                manuscript_id=manuscript.id,
                content="",
                revision=1,
                char_count=0,
                sha256=content_sha256(""),
                base_version_id=version.id,
                created_at=now,
                updated_at=now,
            )
        )
        link = SceneManuscript(project_id=project_id, node_id=node_id, manuscript_id=manuscript.id, created_at=now)
        self._session.add(link)
        try:
            self._session.commit()
        except IntegrityError:
            # Otra petición ha iniciado la escritura a la vez: su unión gana y esta se deshace entera.
            self._session.rollback()
            existing = self._link(project_id, node_id)
            if existing is None:
                raise
            return existing, False
        return link, True

    def save(
        self,
        project_id: int,
        node_id: int,
        content: str,
        base_revision: int,
        keep_previous: bool = False,
    ) -> ManuscriptDraft:
        """Guarda el texto de la escena con escritura condicional. Lanza 409 si la revisión no es la actual."""
        self._active(project_id)
        scene = self._scene(project_id, node_id)
        if scene.archived_at is not None:
            raise ValidationFailed("la escena está archivada; no se puede modificar su texto")
        link = self._link(project_id, node_id)
        if link is None:
            raise NotFoundError("la escena todavía no tiene escritura; empieza a escribirla primero")
        drafts = DraftService(self._session, max_chars=self._max_chars, clock=self._clock)
        return drafts.save(link.manuscript_id, content, base_revision, keep_previous=keep_previous)

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _active(self, project_id: int) -> Project:
        project = self._session.get(Project, project_id)
        if project is None:
            raise NotFoundError(f"no existe el proyecto {project_id}")
        if project.status == "archivado":
            raise ValidationFailed("el proyecto está archivado; no admite cambios de escritura")
        return project

    def _scene(self, project_id: int, node_id: int) -> StructureNode:
        node = self._session.scalar(
            select(StructureNode).where(
                StructureNode.id == node_id, StructureNode.project_id == project_id, StructureNode.kind == "escena"
            )
        )
        if node is None:
            raise NotFoundError(f"no existe la escena {node_id} en el proyecto {project_id}")
        return node

    def _link(self, project_id: int, node_id: int) -> SceneManuscript | None:
        return self._session.scalar(
            select(SceneManuscript).where(
                SceneManuscript.node_id == node_id, SceneManuscript.project_id == project_id
            )
        )

    def _state_of(self, manuscript_id: int) -> str:
        return state_of(self._session, manuscript_id)


def scene_states(session: Session, project_id: int) -> dict[int, str]:
    """Estado de escritura de cada escena escrita del proyecto. Las escenas sin fila son «sin_escritura»."""
    rows = session.execute(
        select(SceneManuscript.node_id, SceneManuscript.manuscript_id).where(SceneManuscript.project_id == project_id)
    ).all()
    return {node_id: state_of(session, manuscript_id) for node_id, manuscript_id in rows}


def state_of(session: Session, manuscript_id: int) -> str:
    """«con_texto» si el borrador o alguna versión tienen caracteres; si no, «sin_texto»."""
    draft_has_text = session.scalar(
        select(exists().where(ManuscriptDraft.manuscript_id == manuscript_id, ManuscriptDraft.char_count > 0))
    )
    version_has_text = session.scalar(
        select(exists().where(ManuscriptVersion.manuscript_id == manuscript_id, ManuscriptVersion.char_count > 0))
    )
    return CON_TEXTO if draft_has_text or version_has_text else SIN_TEXTO


def sync_title(session: Session, node_id: int, title: str | None) -> None:
    """Copia el título de la escena al manuscrito que la escribe. Así el nombre de ambos no se separa."""
    link = session.scalar(select(SceneManuscript).where(SceneManuscript.node_id == node_id))
    if link is None:
        return
    manuscript = session.get(Manuscript, link.manuscript_id)
    if manuscript is not None:
        manuscript.title = (title or "").strip()[:200] or DEFAULT_TITLE


__all__ = ["SceneWritingService", "scene_states", "sync_title", "SIN_ESCRITURA", "SIN_TEXTO", "CON_TEXTO"]
