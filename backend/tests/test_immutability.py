"""Inmutabilidad de versiones, revisiones e ítems, en la base de datos y en el ORM."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import ManuscriptVersion
from app.texts.service import TextService


@pytest.fixture
def version_id(service: TextService) -> int:
    manuscript = service.create_manuscript("Inmutable", "Texto original.", None)
    return service.list_versions(manuscript.id)[0].id


def test_sql_directo_no_puede_modificar_una_version(session: Session, version_id: int) -> None:
    with pytest.raises(IntegrityError, match="inmutable"):
        session.execute(
            text("UPDATE manuscript_versions SET content = 'alterado' WHERE id = :id"),
            {"id": version_id},
        )
        session.commit()
    session.rollback()


def test_sql_directo_no_puede_borrar_una_version(session: Session, version_id: int) -> None:
    with pytest.raises(IntegrityError, match="inmutable"):
        session.execute(text("DELETE FROM manuscript_versions WHERE id = :id"), {"id": version_id})
        session.commit()
    session.rollback()


def test_orm_no_puede_modificar_una_version(session: Session, version_id: int) -> None:
    version = session.get(ManuscriptVersion, version_id)
    assert version is not None
    version.content = "alterado desde el ORM"
    with pytest.raises(IntegrityError, match="inmutable"):
        session.commit()
    session.rollback()


def test_revisiones_e_items_tambien_son_inmutables(
    session: Session, service: TextService, version_id: int
) -> None:
    from app.texts.schemas import ReviewItemIn

    review = service.create_review(
        version_id,
        "Revisor",
        [ReviewItemIn(kind="observacion", quote="Texto", start_offset=0, end_offset=5, comment="Comentario.")],
    )
    with pytest.raises(IntegrityError, match="inmutable"):
        session.execute(text("UPDATE editorial_reviews SET reviewer = 'otro' WHERE id = :id"), {"id": review.id})
        session.commit()
    session.rollback()
    with pytest.raises(IntegrityError, match="inmutable"):
        session.execute(text("DELETE FROM review_items WHERE review_id = :id"), {"id": review.id})
        session.commit()
    session.rollback()
