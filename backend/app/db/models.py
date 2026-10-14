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

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utc_now


class Project(Base):
    """Proyecto (novela). Contenedor aislado de manuscritos.

    No se borra: se archiva y puede restaurarse. ``status`` vale ``activo`` o ``archivado``.
    """

    __tablename__ = "projects"
    __table_args__ = (CheckConstraint("status IN ('activo', 'archivado')", name="ck_project_status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="activo")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Manuscript(Base):
    """Manuscrito: agrupa sus versiones. No tiene contenido propio.

    ``project_id`` es nulo solo para manuscritos creados fuera de un proyecto
    (flujo anterior a la tarea de proyectos).
    """

    __tablename__ = "manuscripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    # Sin ``ondelete`` en el modelo: el inspector de SQLite no reconstruye ``ON DELETE``
    # de claves añadidas con ALTER TABLE, y ``alembic check`` compararía mal. La base de
    # datos sí tiene RESTRICT (migración 0004). En la práctica, un proyecto no se borra:
    # se archiva, así que ninguna de las dos reglas llega a actuar.
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id"),
        nullable=True,
        index=True,
    )

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


class AnalysisRun(Base):
    """Análisis de un fragmento de una versión. Inmutable.

    Guarda el texto del fragmento y el proveedor usado. El proveedor simulado
    queda marcado con ``provider_simulated`` y su etiqueta visible.
    """

    __tablename__ = "analysis_runs"
    __table_args__ = (
        CheckConstraint("fragment_start >= 0", name="ck_analysis_fragment_start_non_negative"),
        CheckConstraint("fragment_end > fragment_start", name="ck_analysis_fragment_end_after_start"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_id: Mapped[int] = mapped_column(
        ForeignKey("manuscript_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    fragment_start: Mapped[int] = mapped_column(Integer, nullable=False)
    fragment_end: Mapped[int] = mapped_column(Integer, nullable=False)
    fragment_text: Mapped[str] = mapped_column(Text, nullable=False)
    provider_name: Mapped[str] = mapped_column(String(60), nullable=False)
    provider_label: Mapped[str] = mapped_column(String(300), nullable=False)
    provider_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # Modelo usado, si el proveedor lo tiene. Nulo para el simulador.
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # True si el fragmento salió del equipo hacia un servicio externo.
    sent_external: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)

    findings: Mapped[list[AnalysisFinding]] = relationship(
        back_populates="run",
        order_by="AnalysisFinding.id",
    )


class AnalysisFinding(Base):
    """Hallazgo de un análisis. Inmutable.

    ``category`` y ``provenance`` se validan en el servicio con el registro de
    ``app.analysis.categories``. Las posiciones son absolutas, dentro de la versión.
    """

    __tablename__ = "analysis_findings"
    __table_args__ = (
        CheckConstraint("start_offset >= 0", name="ck_finding_start_non_negative"),
        CheckConstraint("end_offset > start_offset", name="ck_finding_end_after_start"),
        CheckConstraint("line_number >= 1", name="ck_finding_line_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    provenance: Mapped[str] = mapped_column(String(20), nullable=False)
    source_name: Mapped[str] = mapped_column(String(60), nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    effect: Mapped[str | None] = mapped_column(Text, nullable=True)
    certainty: Mapped[str] = mapped_column(String(20), nullable=False)
    # Nula en filas anteriores a la migración 0003. Obligatoria para hallazgos nuevos de proveedor.
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)

    run: Mapped[AnalysisRun] = relationship(back_populates="findings")


class ManuscriptDraft(Base):
    """Borrador en edición de un manuscrito. Mutable, pero solo mediante escritura condicional.

    ``revision`` es un contador que sube en cada cambio. Una escritura solo se aplica
    si la revisión que conoce el cliente es la actual: así una respuesta o una escritura
    antigua no puede reemplazar un borrador más reciente.

    Un borrador no es una versión formal: no aparece en ``manuscript_versions`` hasta
    que el autor lo guarda como versión explícitamente.
    """

    __tablename__ = "manuscript_drafts"
    __table_args__ = (CheckConstraint("revision >= 1", name="ck_draft_revision_positive"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    manuscript_id: Mapped[int] = mapped_column(
        ForeignKey("manuscripts.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    base_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("manuscript_versions.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)


class DraftRecoveryPoint(Base):
    """Copia recuperable de un borrador. Inmutable.

    ``reason`` indica por qué se creó: ``periodico``, ``significativo``, ``conflicto``,
    ``antes_de_sobrescribir`` o ``antes_de_restaurar``. Ningún punto se modifica ni se
    borra: restaurar crea un estado nuevo, nunca destruye el anterior.
    """

    __tablename__ = "draft_recovery_points"
    __table_args__ = (CheckConstraint("draft_revision >= 0", name="ck_point_revision_non_negative"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    manuscript_id: Mapped[int] = mapped_column(
        ForeignKey("manuscripts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(String(40), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    draft_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
