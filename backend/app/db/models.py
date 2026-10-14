"""Modelos de persistencia de textos, versiones y comentarios editoriales.

Inmutabilidad: las versiones, las revisiones y sus ítems no se modifican ni
se borran. Esto se impone en dos capas:

1. El servicio (``app.texts.service``) no tiene operaciones de actualización.
2. Las migraciones crean triggers en SQLite que rechazan ``UPDATE`` y ``DELETE``
   (ver ``migrations/versions/0001_textos_y_versiones.py``).

Los comentarios guardan la cita literal y su ubicación en la versión a la que
pertenecen. El contenido original vive en ``manuscript_versions.content``; los
desplazamientos nunca se usan para reconstruirlo.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utc_now


class Manuscript(Base):
    """Manuscrito: agrupa sus versiones. No tiene contenido propio."""

    __tablename__ = "manuscripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)

    versions: Mapped[list[ManuscriptVersion]] = relationship(
        back_populates="manuscript",
        order_by="ManuscriptVersion.number",
    )


class ManuscriptVersion(Base):
    """Versión inmutable de un manuscrito.

    ``number`` es correlativo por manuscrito. ``parent_version_id`` registra de
    qué versión procede, si el autor partió de una anterior; no implica
    modificación alguna de esa versión.
    """

    __tablename__ = "manuscript_versions"
    __table_args__ = (
        UniqueConstraint("manuscript_id", "number", name="uq_manuscript_version_number"),
        CheckConstraint("number >= 1", name="ck_version_number_positive"),
        CheckConstraint("char_count >= 0", name="ck_version_char_count_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    manuscript_id: Mapped[int] = mapped_column(
        ForeignKey("manuscripts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    parent_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("manuscript_versions.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)

    manuscript: Mapped[Manuscript] = relationship(back_populates="versions")


class EditorialReview(Base):
    """Conjunto de comentarios editoriales hechos sobre una versión concreta."""

    __tablename__ = "editorial_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_id: Mapped[int] = mapped_column(
        ForeignKey("manuscript_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    reviewer: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)

    items: Mapped[list[ReviewItem]] = relationship(
        back_populates="review",
        order_by="ReviewItem.id",
    )


class ReviewItem(Base):
    """Un comentario con su cita literal.

    ``kind`` es texto libre en la base de datos. Los tipos permitidos se
    definen en ``app.texts.kinds``, así que añadir un tipo no exige cambiar el
    esquema. ``intent_status`` admite solo ``no_declarada`` por ahora: el
    evaluador no puede afirmar intenciones del autor.
    """

    __tablename__ = "review_items"
    __table_args__ = (
        CheckConstraint("start_offset >= 0", name="ck_item_start_non_negative"),
        CheckConstraint("end_offset > start_offset", name="ck_item_end_after_start"),
        CheckConstraint("line_number >= 1", name="ck_item_line_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_id: Mapped[int] = mapped_column(
        ForeignKey("editorial_reviews.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    version_id: Mapped[int] = mapped_column(
        ForeignKey("manuscript_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    inference_basis: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    dimension: Mapped[str | None] = mapped_column(String(40), nullable=True)
    intent_status: Mapped[str] = mapped_column(String(40), nullable=False, default="no_declarada")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)

    review: Mapped[EditorialReview] = relationship(back_populates="items")
