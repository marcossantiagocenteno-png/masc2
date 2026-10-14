"""Servicio de borradores y puntos de recuperación.

Reglas:

- Escritura condicional: ``save`` y ``restore`` solo se aplican si la revisión
  enviada es la actual. La comprobación y la escritura son una sola sentencia SQL
  (``UPDATE ... WHERE revision = ?``), así que dos escrituras simultáneas no pueden
  aplicarse las dos sobre la misma revisión.
- Un conflicto nunca sobrescribe: el texto rechazado se guarda en un punto
  ``conflicto`` antes de responder 409.
- Restaurar guarda primero el estado actual como punto ``antes_de_restaurar`` y
  después cambia el borrador. Todo ocurre en una transacción.
- El borrador nunca crea versiones formales. Las versiones de ``manuscript_versions``
  no se tocan.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import DraftRecoveryPoint, Manuscript, ManuscriptDraft, ManuscriptVersion
from app.drafts import policy
from app.drafts.errors import DraftConflict, DraftNotFound
from app.texts.errors import ContentTooLarge, NotFoundError
from app.texts.normalization import content_sha256, normalize_content

Clock = Callable[[], datetime]


class DraftService:
    """Operaciones sobre borradores y puntos de recuperación. Confirma cada operación."""

    def __init__(self, session: Session, max_chars: int, clock: Clock) -> None:
        self._session = session
        self._max_chars = max_chars
        self._clock = clock

    # ------------------------------------------------------------------
    # Lectura e inicialización
    # ------------------------------------------------------------------

    def get_draft(self, manuscript_id: int) -> ManuscriptDraft:
        """Borrador del manuscrito, o ``DraftNotFound`` si todavía no existe."""
        self._require_manuscript(manuscript_id)
        draft = self._load_draft(manuscript_id)
        if draft is None:
            raise DraftNotFound(f"el manuscrito {manuscript_id} no tiene borrador")
        return draft

    def init_draft(self, manuscript_id: int) -> tuple[ManuscriptDraft, bool]:
        """Devuelve el borrador existente, o lo crea a partir de la última versión.

        Devuelve ``(borrador, creado)``. Si ya existe, nunca lo reemplaza. Si dos
        peticiones lo crean a la vez, la segunda recibe el borrador de la primera.
        """
        existing = self._load_draft(manuscript_id)
        if existing is not None:
            return existing, False
        self._require_manuscript(manuscript_id)
        latest = self._latest_version(manuscript_id)
        now = self._clock()
        draft = ManuscriptDraft(
            manuscript_id=manuscript_id,
            content=latest.content,
            revision=1,
            char_count=latest.char_count,
            sha256=latest.sha256,
            base_version_id=latest.id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(draft)
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            existing = self._load_draft(manuscript_id)
            if existing is None:
                raise
            return existing, False
        return draft, True

    # ------------------------------------------------------------------
    # Escritura condicional
    # ------------------------------------------------------------------

    def save(
        self,
        manuscript_id: int,
        content: str,
        base_revision: int,
        keep_previous: bool = False,
    ) -> ManuscriptDraft:
        """Guarda ``content`` si ``base_revision`` es la revisión actual.

        Si no lo es, guarda el texto rechazado como punto ``conflicto`` y lanza
        ``DraftConflict``. Crea un punto de recuperación según la política.

        Con ``keep_previous``, el contenido anterior del borrador se guarda antes como
        punto ``antes_de_sobrescribir`` en la misma transacción.
        """
        normalized = self._prepare(content)
        draft = self._load_draft(manuscript_id)
        if draft is None:
            raise DraftNotFound(f"el manuscrito {manuscript_id} no tiene borrador")
        if draft.revision != base_revision:
            raise self._conflict(manuscript_id, normalized, base_revision)

        now = self._clock()
        new_revision = base_revision + 1
        if keep_previous and draft.content != normalized:
            self._session.add(
                self._point(manuscript_id, policy.ANTES_DE_SOBRESCRIBIR, draft.content, draft.revision, now)
            )
        applied = self._apply(draft.id, base_revision, normalized, new_revision, now)
        if not applied:
            raise self._conflict(manuscript_id, normalized, base_revision)

        reason = policy.reason_for_new_point(self._last_point_state(manuscript_id), len(normalized), now)
        if reason is not None:
            self._session.add(self._point(manuscript_id, reason, normalized, new_revision, now))
        self._session.commit()
        return self._refreshed(manuscript_id)

    # ------------------------------------------------------------------
    # Puntos de recuperación
    # ------------------------------------------------------------------

    def list_points(self, manuscript_id: int) -> list[DraftRecoveryPoint]:
        """Puntos del manuscrito, del más reciente al más antiguo."""
        self._require_manuscript(manuscript_id)
        return list(
            self._session.scalars(
                select(DraftRecoveryPoint)
                .where(DraftRecoveryPoint.manuscript_id == manuscript_id)
                .order_by(DraftRecoveryPoint.id.desc())
            ).all()
        )

    def get_point(self, manuscript_id: int, point_id: int) -> DraftRecoveryPoint:
        """Punto de recuperación; debe pertenecer al manuscrito indicado."""
        point = self._session.get(DraftRecoveryPoint, point_id)
        if point is None or point.manuscript_id != manuscript_id:
            raise DraftNotFound(f"no existe el punto de recuperación {point_id} en el manuscrito {manuscript_id}")
        return point

    def restore(self, manuscript_id: int, point_id: int, base_revision: int) -> ManuscriptDraft:
        """Sustituye el borrador por el contenido de un punto, en una transacción.

        El estado anterior se guarda como punto ``antes_de_restaurar``. La restauración
        crea una revisión nueva: no borra el borrador anterior ni toca las versiones.
        """
        point = self.get_point(manuscript_id, point_id)
        draft = self._load_draft(manuscript_id)
        if draft is None:
            raise DraftNotFound(f"el manuscrito {manuscript_id} no tiene borrador")
        if draft.revision != base_revision:
            raise self._conflict(manuscript_id, None, base_revision)

        now = self._clock()
        self._session.add(self._point(manuscript_id, policy.ANTES_DE_RESTAURAR, draft.content, draft.revision, now))
        applied = self._apply(draft.id, base_revision, point.content, base_revision + 1, now)
        if not applied:
            raise self._conflict(manuscript_id, None, base_revision)
        self._session.commit()
        return self._refreshed(manuscript_id)

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _apply(self, draft_id: int, expected_revision: int, content: str, new_revision: int, now: datetime) -> bool:
        """Escritura condicional. Devuelve ``False`` si la revisión ya no coincide."""
        result = self._session.execute(
            update(ManuscriptDraft)
            .where(ManuscriptDraft.id == draft_id, ManuscriptDraft.revision == expected_revision)
            .values(
                content=content,
                revision=new_revision,
                char_count=len(content),
                sha256=content_sha256(content),
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 0:
            self._session.rollback()
            return False
        return True

    def _conflict(self, manuscript_id: int, rejected: str | None, base_revision: int) -> DraftConflict:
        """Guarda el texto rechazado (si lo hay) y construye el error 409."""
        point_id = None
        if rejected is not None:
            point = self._point(manuscript_id, policy.CONFLICTO, rejected, base_revision, self._clock())
            self._session.add(point)
            self._session.commit()
            point_id = point.id
        current = self._refreshed(manuscript_id)
        payload: dict[str, Any] = {
            "code": "draft_conflict",
            "current_revision": current.revision,
            "current_content": current.content,
            "current_updated_at": current.updated_at.isoformat(),
            "preserved_point_id": point_id,
        }
        return DraftConflict(
            "la revisión enviada no es la actual; el borrador no se ha sobrescrito",
            payload,
        )

    def _point(
        self, manuscript_id: int, reason: str, content: str, draft_revision: int, now: datetime
    ) -> DraftRecoveryPoint:
        return DraftRecoveryPoint(
            manuscript_id=manuscript_id,
            reason=reason,
            content=content,
            char_count=len(content),
            sha256=content_sha256(content),
            draft_revision=draft_revision,
            created_at=now,
        )

    def _last_point_state(self, manuscript_id: int) -> tuple[datetime, int] | None:
        row = self._session.execute(
            select(DraftRecoveryPoint.created_at, DraftRecoveryPoint.char_count)
            .where(DraftRecoveryPoint.manuscript_id == manuscript_id)
            .order_by(DraftRecoveryPoint.id.desc())
            .limit(1)
        ).first()
        return None if row is None else (row[0], row[1])

    def _prepare(self, raw: str) -> str:
        normalized = normalize_content(raw)
        if len(normalized) > self._max_chars:
            raise ContentTooLarge(
                f"el borrador supera el límite de {self._max_chars} caracteres"
            )
        return normalized

    def _load_draft(self, manuscript_id: int) -> ManuscriptDraft | None:
        return self._session.scalar(
            select(ManuscriptDraft)
            .where(ManuscriptDraft.manuscript_id == manuscript_id)
            .execution_options(populate_existing=True)
        )

    def _refreshed(self, manuscript_id: int) -> ManuscriptDraft:
        draft = self._load_draft(manuscript_id)
        if draft is None:
            raise DraftNotFound(f"el manuscrito {manuscript_id} no tiene borrador")
        return draft

    def _latest_version(self, manuscript_id: int) -> ManuscriptVersion:
        version = self._session.scalar(
            select(ManuscriptVersion)
            .where(ManuscriptVersion.manuscript_id == manuscript_id)
            .order_by(ManuscriptVersion.number.desc())
            .limit(1)
        )
        if version is None:
            raise NotFoundError(f"el manuscrito {manuscript_id} no tiene versiones")
        return version

    def _require_manuscript(self, manuscript_id: int) -> Manuscript:
        manuscript = self._session.get(Manuscript, manuscript_id)
        if manuscript is None:
            raise NotFoundError(f"no existe el manuscrito {manuscript_id}")
        return manuscript
