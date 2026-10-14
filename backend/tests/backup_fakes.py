"""Herramientas comunes de las pruebas de copias: reloj controlable y datos de ejemplo."""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

from app.config import Settings
from app.db.session import create_engine_for, create_session_factory
from app.drafts.errors import DraftConflict
from app.drafts.service import DraftService
from app.projects.service import ProjectService
from app.texts.service import TextService

T0 = datetime(2026, 1, 1, 12, 0, 0)


class FakeClock:
    """Reloj que solo avanza cuando la prueba lo indica. Sustituye a ``utc_now``."""

    def __init__(self, start: datetime = T0) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def counts(path: Path) -> dict[str, int]:
    tables = ("projects", "manuscripts", "manuscript_versions", "manuscript_drafts", "draft_recovery_points")
    with closing(sqlite3.connect(path)) as connection:
        return {t: connection.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}


def populate(settings: Settings, clock: FakeClock) -> int:
    """Crea proyecto, manuscrito con dos versiones, borrador y puntos (periódico y conflicto).

    Devuelve el id del manuscrito. Cada punto se crea con el reloj controlado.
    """
    engine = create_engine_for(settings.database_url)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            texts = TextService(session, max_version_chars=settings.max_version_chars)
            project = ProjectService(session, texts).create_project("Proyecto de copia")
            manuscript = texts.create_manuscript("Novela de copia", "Texto formal uno.", None, project_id=project.id)
            texts.add_version(manuscript.id, "Texto formal dos.", None, based_on_version_id=None)
            drafts = DraftService(session, settings.max_version_chars, clock)
            drafts.init_draft(manuscript.id)
            drafts.save(manuscript.id, "Borrador con cambios.", 1)  # punto periódico
            try:
                drafts.save(manuscript.id, "Escritura tardía.", 1)  # conflicto: queda como punto
            except DraftConflict:
                pass
            return manuscript.id
    finally:
        engine.dispose()
