"""Comprobaciones de un archivo SQLite: que se puede abrir, que es íntegro y que su esquema es conocido.

La apertura es de solo lectura. Ninguna comprobación modifica el archivo.
"""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
SQLITE_HEADER = b"SQLite format 3\x00"

BASE_TABLES = frozenset(
    {
        "alembic_version",
        "projects",
        "manuscripts",
        "manuscript_versions",
        "editorial_reviews",
        "review_items",
        "analysis_runs",
        "analysis_findings",
    }
)
DRAFT_TABLES = frozenset({"manuscript_drafts", "draft_recovery_points"})
# Primera revisión que crea las tablas de borradores. Las copias anteriores no las tienen.
DRAFT_REVISION = "0005_borradores_y_recuperacion"
COUNTED_TABLES = (
    "projects",
    "manuscripts",
    "manuscript_versions",
    "editorial_reviews",
    "review_items",
    "analysis_runs",
    "analysis_findings",
    "manuscript_drafts",
    "draft_recovery_points",
)


@dataclass(frozen=True)
class SchemaOrder:
    """Revisiones conocidas por el código, de la más reciente a la más antigua."""

    newest_first: tuple[str, ...]

    def includes_drafts(self, revision: str | None) -> bool:
        """``True`` si ``revision`` es la de los borradores o una posterior."""
        if revision is None or revision not in self.newest_first or DRAFT_REVISION not in self.newest_first:
            return False
        return self.newest_first.index(revision) <= self.newest_first.index(DRAFT_REVISION)

    def classify(self, revision: str | None) -> str:
        """``actual``, ``anterior`` (conocida, pero no la última) o ``desconocida``."""
        if revision is None or revision not in self.newest_first:
            return "desconocida"
        return "actual" if revision == self.newest_first[0] else "anterior"


def schema_order() -> SchemaOrder:
    script = ScriptDirectory.from_config(Config(str(ALEMBIC_INI)))
    return SchemaOrder(tuple(revision.revision for revision in script.walk_revisions()))


def sqlite_path(database_url: str) -> Path | None:
    """Ruta del archivo de una URL SQLite, o ``None`` si no es SQLite o es memoria."""
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        return None
    return Path(url.database).resolve()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_only_connection(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=30)


@dataclass(frozen=True)
class Verification:
    problems: tuple[str, ...] = ()
    revision: str | None = None
    schema_status: str = "desconocida"
    counts: dict[str, int] = field(default_factory=dict)
    sha256: str | None = None
    size_bytes: int = 0

    @property
    def ok(self) -> bool:
        return not self.problems


def verify_sqlite(path: Path, order: SchemaOrder) -> Verification:
    """Comprueba que el archivo es SQLite, que supera ``PRAGMA integrity_check`` y que su esquema es conocido.

    Devuelve los problemas encontrados en lugar de lanzar excepción, para que el
    llamador pueda rechazar el archivo sin tocar nada más.
    """
    if not path.is_file():
        return Verification(problems=("el archivo no existe",))
    with path.open("rb") as handle:
        header = handle.read(len(SQLITE_HEADER))
    if header != SQLITE_HEADER:
        return Verification(problems=("no es un archivo SQLite",))

    problems: list[str] = []
    try:
        with closing(read_only_connection(path)) as connection:
            integrity = [row[0] for row in connection.execute("PRAGMA integrity_check").fetchall()]
            if integrity != ["ok"]:
                problems.append("la integridad no es correcta: " + "; ".join(integrity[:3]))
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            revision = None
            if "alembic_version" in tables:
                row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
                revision = row[0] if row else None
            required = set(BASE_TABLES)
            if order.includes_drafts(revision):
                required |= DRAFT_TABLES
            missing = sorted(required - tables)
            if missing:
                problems.append("faltan tablas: " + ", ".join(missing))
            counts = {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in COUNTED_TABLES
                if table in tables
            }
    except sqlite3.DatabaseError as error:
        return Verification(problems=(f"SQLite no puede leer el archivo ({type(error).__name__})",))

    status = order.classify(revision)
    if status == "desconocida":
        problems.append(f"versión de esquema desconocida para este código: {revision}")
    return Verification(
        problems=tuple(problems),
        revision=revision,
        schema_status=status,
        counts=counts,
        sha256=file_sha256(path),
        size_bytes=path.stat().st_size,
    )
