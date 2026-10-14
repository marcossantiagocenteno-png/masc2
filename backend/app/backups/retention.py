"""Retención de puntos de recuperación: métricas y vista previa de candidatos. No borra nada.

Por qué no hay eliminación automática en esta fase: los triggers de
``draft_recovery_points`` rechazan ``DELETE`` (D-016, migración 0005), y la
inmutabilidad debe mantenerse. Quitar esa protección exige una decisión explícita
con su propia migración y sus pruebas. Mientras tanto, esta vista previa dice qué
se podría retirar algún día y por qué el resto se conserva.

Reglas de la vista previa. Un punto solo es candidato si se cumplen todas:

1. Su motivo es ``periodico`` o ``significativo``. Los de ``conflicto``, ``antes_de_sobrescribir``
   y ``antes_de_restaurar`` nunca son candidatos.
2. Tiene más de ``min_age`` de antigüedad.
3. No está entre los ``keep_per_manuscript`` más recientes de su manuscrito.
4. Existe una copia verificada que contiene ese mismo punto (mismo id y mismo hash).
   Si no hay copia verificada del contenido, se conserva.
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.backups.files import list_backups
from app.backups.verify import read_only_connection
from app.db.models import DraftRecoveryPoint, ManuscriptDraft, ManuscriptVersion

REMOVABLE_REASONS = frozenset({"periodico", "significativo"})
GROWTH_WINDOW = timedelta(days=30)


@dataclass(frozen=True)
class RetentionPolicy:
    keep_per_manuscript: int
    min_age: timedelta


@dataclass(frozen=True)
class Candidate:
    point_id: int
    manuscript_id: int
    reason: str
    created_at: datetime


@dataclass(frozen=True)
class RetentionPreview:
    points_total: int
    points_by_reason: dict[str, int]
    growth_per_day: float
    candidates: tuple[Candidate, ...]
    kept_because: dict[str, int] = field(default_factory=dict)
    versions_total: int = 0
    drafts_total: int = 0


def points_in_backup(path: Path) -> dict[int, str]:
    """Puntos de una copia verificada, como ``{id: sha256}``. Vacío si la copia no se puede leer."""
    try:
        with closing(read_only_connection(path)) as connection:
            rows = connection.execute("SELECT id, sha256 FROM draft_recovery_points").fetchall()
    except Exception:  # Una copia ilegible no respalda nada.
        return {}
    return {int(point_id): str(sha) for point_id, sha in rows}


def newest_backup_points(directory: Path) -> dict[int, str]:
    """Puntos de la copia más reciente de la carpeta, o vacío si no hay ninguna."""
    backups = list_backups(directory)
    return points_in_backup(backups[0]) if backups else {}


def preview(
    session: Session,
    now: datetime,
    policy: RetentionPolicy,
    backed_up: dict[int, str],
) -> RetentionPreview:
    """Calcula métricas y candidatos. Solo lee la base de datos."""
    points = session.scalars(
        select(DraftRecoveryPoint).order_by(DraftRecoveryPoint.manuscript_id, DraftRecoveryPoint.id.desc())
    ).all()

    by_reason: dict[str, int] = {}
    kept: dict[str, int] = {}
    candidates: list[Candidate] = []
    rank_in_manuscript: dict[int, int] = {}
    recent_cutoff = now - GROWTH_WINDOW
    recent_count = 0

    for point in points:
        by_reason[point.reason] = by_reason.get(point.reason, 0) + 1
        if point.created_at >= recent_cutoff:
            recent_count += 1
        rank = rank_in_manuscript.get(point.manuscript_id, 0)
        rank_in_manuscript[point.manuscript_id] = rank + 1

        reason_kept = _kept_reason(point, rank, now, policy, backed_up)
        if reason_kept is None:
            candidates.append(Candidate(point.id, point.manuscript_id, point.reason, point.created_at))
        else:
            kept[reason_kept] = kept.get(reason_kept, 0) + 1

    versions_total = session.scalar(select(func.count(ManuscriptVersion.id))) or 0
    drafts_total = session.scalar(select(func.count(ManuscriptDraft.id))) or 0
    return RetentionPreview(
        points_total=len(points),
        points_by_reason=by_reason,
        growth_per_day=recent_count / GROWTH_WINDOW.days,
        candidates=tuple(candidates),
        kept_because=kept,
        versions_total=versions_total,
        drafts_total=drafts_total,
    )


def _kept_reason(
    point: DraftRecoveryPoint,
    rank: int,
    now: datetime,
    policy: RetentionPolicy,
    backed_up: dict[int, str],
) -> str | None:
    if point.reason not in REMOVABLE_REASONS:
        return f"motivo protegido ({point.reason})"
    if now - point.created_at < policy.min_age:
        return "reciente"
    if rank < policy.keep_per_manuscript:
        return "entre los más recientes del manuscrito"
    if backed_up.get(point.id) != point.sha256:
        return "sin copia verificada que lo contenga"
    return None

