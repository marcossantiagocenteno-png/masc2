"""Servicio de textos: manuscritos, versiones inmutables y revisiones editoriales.

Reglas principales:

- Una versión nunca se modifica. Cualquier cambio, incluido partir de una
  versión anterior, crea una versión nueva con el siguiente número.
- Una revisión pertenece a una única versión. Crearla no altera la versión ni
  se traslada a otras versiones.
- Cada cita debe coincidir exactamente con el contenido de la versión
  almacenada en el momento de crear el comentario.
- Antes de devolver una versión se comprueba su hash. Si no coincide, se
  lanza ``IntegrityFailure`` y no se devuelve el contenido.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.benchmark.models import Dimension
from app.db.models import EditorialReview, Manuscript, ManuscriptVersion, ReviewItem
from app.texts.errors import (
    ConflictError,
    ContentTooLarge,
    IntegrityFailure,
    NotFoundError,
    ValidationFailed,
)
from app.texts.kinds import INTENT_NOT_DECLARED, ITEM_KINDS
from app.texts.normalization import content_sha256, normalize_content
from app.texts.schemas import ReviewItemIn


class TextService:
    """Operaciones sobre manuscritos, versiones y revisiones. Confirma cada operación."""

    def __init__(self, session: Session, max_version_chars: int) -> None:
        self._session = session
        self._max_chars = max_version_chars

    # ------------------------------------------------------------------
    # Manuscritos
    # ------------------------------------------------------------------

    def create_manuscript(
        self,
        title: str,
        content: str,
        note: str | None,
        project_id: int | None = None,
    ) -> Manuscript:
        """Crea un manuscrito con su versión 1, dentro de ``project_id`` si se indica."""
        normalized = self._prepare_content(content)
        manuscript = Manuscript(title=title, project_id=project_id)
        self._session.add(manuscript)
        self._session.flush()
        self._insert_version(manuscript.id, 1, normalized, note, parent_version_id=None)
        self._session.commit()
        return manuscript

    def list_manuscripts(self) -> Sequence[Manuscript]:
        """Todos los manuscritos, del más reciente al más antiguo."""
        return list(
            self._session.scalars(select(Manuscript).order_by(Manuscript.id.desc())).all()
        )

    def get_manuscript(self, manuscript_id: int) -> Manuscript:
        """Devuelve el manuscrito o lanza ``NotFoundError``."""
        manuscript = self._session.get(Manuscript, manuscript_id)
        if manuscript is None:
            raise NotFoundError(f"no existe el manuscrito {manuscript_id}")
        return manuscript

    # ------------------------------------------------------------------
    # Versiones
    # ------------------------------------------------------------------

    def add_version(
        self,
        manuscript_id: int,
        content: str,
        note: str | None,
        based_on_version_id: int | None,
    ) -> ManuscriptVersion:
        """Añade una versión nueva. Nunca modifica las anteriores."""
        self.get_manuscript(manuscript_id)
        normalized = self._prepare_content(content)

        if based_on_version_id is not None:
            base = self._session.get(ManuscriptVersion, based_on_version_id)
            if base is None or base.manuscript_id != manuscript_id:
                raise ValidationFailed(
                    "based_on_version_id debe ser una versión del mismo manuscrito"
                )

        next_number = (
            self._session.scalar(
                select(func.max(ManuscriptVersion.number)).where(
                    ManuscriptVersion.manuscript_id == manuscript_id
                )
            )
            or 0
        ) + 1

        try:
            version = self._insert_version(
                manuscript_id, next_number, normalized, note, based_on_version_id
            )
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            raise ConflictError("otra operación creó la misma versión; reintenta") from error
        return version

    def list_versions(self, manuscript_id: int) -> Sequence[ManuscriptVersion]:
        """Versiones del manuscrito, por número ascendente."""
        self.get_manuscript(manuscript_id)
        return list(
            self._session.scalars(
                select(ManuscriptVersion)
                .where(ManuscriptVersion.manuscript_id == manuscript_id)
                .order_by(ManuscriptVersion.number)
            ).all()
        )

    def get_version(self, version_id: int) -> ManuscriptVersion:
        """Devuelve la versión tras comprobar su hash. Lanza ``IntegrityFailure`` si no coincide."""
        version = self._session.get(ManuscriptVersion, version_id)
        if version is None:
            raise NotFoundError(f"no existe la versión {version_id}")
        if (
            content_sha256(version.content) != version.sha256
            or len(version.content) != version.char_count
        ):
            raise IntegrityFailure(
                f"la versión {version_id} no coincide con su hash almacenado"
            )
        return version

    def review_count(self, version_id: int) -> int:
        """Número de revisiones vinculadas a una versión."""
        return int(
            self._session.scalar(
                select(func.count(EditorialReview.id)).where(EditorialReview.version_id == version_id)
            )
            or 0
        )

    # ------------------------------------------------------------------
    # Revisiones editoriales
    # ------------------------------------------------------------------

    def create_review(
        self,
        version_id: int,
        reviewer: str,
        items: Sequence[ReviewItemIn],
    ) -> EditorialReview:
        """Crea una revisión sobre una versión. Valida todas las citas antes de guardar nada."""
        version = self.get_version(version_id)

        prepared = [
            self._build_item(index, item, version.content, version.id)
            for index, item in enumerate(items)
        ]

        review = EditorialReview(version_id=version.id, reviewer=reviewer)
        review.items = prepared
        self._session.add(review)
        self._session.commit()
        return review

    def list_reviews(self, version_id: int) -> Sequence[EditorialReview]:
        """Revisiones de una versión, de la más antigua a la más reciente."""
        self.get_version(version_id)
        return list(
            self._session.scalars(
                select(EditorialReview)
                .where(EditorialReview.version_id == version_id)
                .order_by(EditorialReview.id)
            ).all()
        )

    # ------------------------------------------------------------------
    # Auxiliares internos
    # ------------------------------------------------------------------

    def _prepare_content(self, raw: str) -> str:
        normalized = normalize_content(raw)
        if len(normalized) > self._max_chars:
            raise ContentTooLarge(
                f"el contenido tiene {len(normalized)} caracteres; el límite es {self._max_chars}"
            )
        return normalized

    def _insert_version(
        self,
        manuscript_id: int,
        number: int,
        content: str,
        note: str | None,
        parent_version_id: int | None,
    ) -> ManuscriptVersion:
        version = ManuscriptVersion(
            manuscript_id=manuscript_id,
            number=number,
            content=content,
            sha256=content_sha256(content),
            char_count=len(content),
            note=note or None,
            parent_version_id=parent_version_id,
        )
        self._session.add(version)
        self._session.flush()
        return version

    def _build_item(
        self,
        index: int,
        item: ReviewItemIn,
        content: str,
        version_id: int,
    ) -> ReviewItem:
        where = f"items[{index}]"

        kind = ITEM_KINDS.get(item.kind)
        if kind is None:
            raise ValidationFailed(f"{where}: tipo no permitido '{item.kind}'")

        if kind.requires_inference_basis and not item.inference_basis:
            raise ValidationFailed(f"{where}: una inferencia necesita su cadena de inferencia")
        if not kind.requires_inference_basis and item.inference_basis:
            raise ValidationFailed(f"{where}: solo las inferencias llevan cadena de inferencia")

        if item.dimension is not None:
            try:
                Dimension(item.dimension)
            except ValueError as error:
                raise ValidationFailed(
                    f"{where}: dimensión no válida '{item.dimension}'"
                ) from error

        if item.end_offset > len(content):
            raise ValidationFailed(
                f"{where}: la posición final {item.end_offset} supera la longitud de la versión ({len(content)})"
            )
        if item.start_offset >= item.end_offset:
            raise ValidationFailed(f"{where}: la posición inicial debe ser menor que la final")

        if content[item.start_offset : item.end_offset] != item.quote:
            raise ValidationFailed(
                f"{where}: la cita no coincide exactamente con la versión {version_id} en esas posiciones"
            )

        line_number = content.count("\n", 0, item.start_offset) + 1

        return ReviewItem(
            version_id=version_id,
            kind=item.kind,
            quote=item.quote,
            start_offset=item.start_offset,
            end_offset=item.end_offset,
            line_number=line_number,
            comment=item.comment,
            inference_basis=item.inference_basis,
            suggestion=item.suggestion,
            dimension=item.dimension,
            intent_status=INTENT_NOT_DECLARED,
        )
