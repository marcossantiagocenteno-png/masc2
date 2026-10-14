"""Simulacro de copia y restauración en un directorio temporal, para ejecutar en cualquier sistema.

No toca la base de datos del usuario: crea su propia base dentro de la carpeta indicada.
Sirve para comprobar en una máquina concreta (por ejemplo, Windows) que el procedimiento
funciona de extremo a extremo. Un resultado correcto allí es la única prueba real de ese sistema.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select

from app.backups.files import Clock, utc_clock
from app.backups.restore import restore_backup
from app.backups.service import BackupService
from app.backups.verify import ALEMBIC_INI, schema_order, verify_sqlite
from app.config import Settings
from app.db.models import DraftRecoveryPoint, ManuscriptDraft
from app.db.session import create_engine_for, create_session_factory
from app.drafts.service import DraftService
from app.texts.service import TextService

FIRST_TEXT = "Texto del simulacro, primera versión."
LATER_TEXT = "Texto del simulacro, cambio posterior a la copia."


@dataclass(frozen=True)
class Step:
    name: str
    ok: bool
    detail: str = ""


def run_drill(workdir: Path, clock: Clock = utc_clock) -> list[Step]:
    """Ejecuta el simulacro en ``workdir``. Devuelve el resultado de cada paso."""
    steps: list[Step] = []

    def check(name: str, ok: bool, detail: str = "") -> bool:
        steps.append(Step(name, ok, detail))
        return ok

    workdir.mkdir(parents=True, exist_ok=True)
    database = workdir / "simulacro.sqlite"
    url = f"sqlite:///{database.as_posix()}"
    config = Config(str(ALEMBIC_INI))
    config.attributes["database_url"] = url
    command.upgrade(config, "head")
    check("migrar base vacía a la versión actual", True)

    settings = Settings(database_url=url)
    engine = create_engine_for(url)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            manuscript = TextService(session, settings.max_version_chars).create_manuscript(
                "Simulacro", FIRST_TEXT, None
            )
            drafts = DraftService(session, settings.max_version_chars, clock)
            drafts.init_draft(manuscript.id)
            drafts.save(manuscript.id, FIRST_TEXT, 1)
            manuscript_id = manuscript.id
        check("crear manuscrito, borrador y punto de recuperación", True)
    finally:
        engine.dispose()

    directory = workdir / "copias"
    outcome = BackupService(
        source=database, directory=directory, clock=clock, keep=5, min_keep=1, max_age=timedelta(days=30)
    ).run()
    if not check("crear copia verificada", outcome.status == "creada", outcome.message):
        return steps
    backup = outcome.path
    assert backup is not None

    engine = create_engine_for(url)
    try:
        with create_session_factory(engine)() as session:
            DraftService(session, settings.max_version_chars, clock).save(manuscript_id, LATER_TEXT, 2)
    finally:
        engine.dispose()
    check("cambiar el borrador después de la copia", True)

    restored = restore_backup(database, directory, backup, clock)
    if not check("restaurar la copia", restored.status == "restaurada", restored.message):
        return steps

    final = verify_sqlite(database, schema_order())
    check("base restaurada íntegra y con esquema conocido", final.ok, "; ".join(final.problems))
    engine = create_engine_for(url)
    try:
        with create_session_factory(engine)() as session:
            draft = session.scalar(select(ManuscriptDraft).where(ManuscriptDraft.manuscript_id == manuscript_id))
            points = session.scalars(select(DraftRecoveryPoint)).all()
            restored_text = draft.content if draft else None
            point_count = len(points)
    finally:
        engine.dispose()
    check("el borrador recuperado es el de la copia", restored_text == FIRST_TEXT, f"contenido: {restored_text!r}")
    check("los puntos de recuperación siguen presentes", point_count >= 1, f"puntos: {point_count}")

    preventive = restored.preventive
    kept = preventive is not None and preventive.exists()
    preventive_has_later = False
    if kept:
        assert preventive is not None
        preventive_check = verify_sqlite(preventive, schema_order())
        preventive_has_later = preventive_check.ok and _draft_text(preventive) == LATER_TEXT
    check("la copia preventiva conserva el estado reemplazado", preventive_has_later)
    return steps


def _draft_text(path: Path) -> str | None:
    import sqlite3
    from contextlib import closing

    with closing(sqlite3.connect(path)) as connection:
        row = connection.execute("SELECT content FROM manuscript_drafts").fetchone()
    return row[0] if row else None
