"""Concurrencia en la estructura: dos operaciones sobre la misma vista no pueden pisarse en silencio."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from app.db.session import create_engine_for, create_session_factory
from app.planning.service import PlanningService
from app.texts.errors import ConflictError
from tests.backup_fakes import FakeClock


def _factory(settings):  # type: ignore[no-untyped-def]
    engine = create_engine_for(settings.database_url)
    return create_session_factory(engine), engine


def _seed(factory, clock):  # type: ignore[no-untyped-def]
    """Proyecto con tres escenas en la raíz. Devuelve (project_id, [ids])."""
    from app.db.models import Project

    with factory() as session:
        project = Project(name="Concurrencia", status="activo", created_at=clock.now, updated_at=clock.now)
        session.add(project)
        session.commit()
        service = PlanningService(session, clock=clock)
        ids = [service.create_node(project.id, "escena", None, {"title": f"E{i}"}).id for i in range(3)]
        return project.id, ids


def _order(factory, project_id):  # type: ignore[no-untyped-def]
    with factory() as session:
        service = PlanningService(session, clock=FakeClock())
        return [n.title for n in sorted(service.list("estructura", project_id, include_archived=True), key=lambda n: (n.position, n.id))]


def test_una_reordenacion_con_vista_anterior_no_pisa_a_la_que_ya_se_confirmo(settings) -> None:  # type: ignore[no-untyped-def]
    """Hallazgo: dos reordenaciones sobre la misma vista. La segunda sobrescribía a la primera sin avisar."""
    clock = FakeClock()
    factory, engine = _factory(settings)
    try:
        project_id, (a, b, c) = _seed(factory, clock)
        original_siblings = None

        with factory() as session_a, factory() as session_b:
            service_a = PlanningService(session_a, clock=clock)
            service_b = PlanningService(session_b, clock=clock)
            real_siblings = service_a._siblings

            def stale_then_competing(project, parent):  # type: ignore[no-untyped-def]
                nonlocal original_siblings
                result = real_siblings(project, parent)
                if original_siblings is None:
                    original_siblings = result
                    # Otra petición reordena entre la lectura de A y su escritura.
                    service_b.reorder(project_id, None, [c, b, a])
                return result

            service_a._siblings = stale_then_competing  # type: ignore[method-assign]
            with pytest.raises(ConflictError):
                service_a.reorder(project_id, None, [b, a, c])

        assert _order(factory, project_id) == ["E2", "E1", "E0"]  # solo queda la reordenación confirmada
    finally:
        engine.dispose()
