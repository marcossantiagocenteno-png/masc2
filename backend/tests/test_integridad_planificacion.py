"""Auditoría de integridad de la planificación: vínculos, historial de canon y atomicidad.

Cada prueba reproduce un defecto concreto o fija una garantía que debe mantenerse.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.db.models import NarrativeDecision
from app.planning.service import PlanningService
from app.texts.errors import ConflictError, ValidationFailed
from tests.backup_fakes import FakeClock


@pytest.fixture
def api(client: TestClient) -> TestClient:
    client.app.state.clock = FakeClock()
    return client


def _url(project_id: int, path: str = "") -> str:
    return f"/projects/{project_id}/planificacion{path}"


def _project(api: TestClient, name: str) -> int:
    return api.post("/projects", json={"name": name}).json()["id"]


def _character(api: TestClient, project_id: int, name: str = "Ana") -> int:
    return api.post(_url(project_id, "/personajes"), json={"name": name}).json()["id"]


def _scene(api: TestClient, project_id: int) -> int:
    return api.post(_url(project_id, "/estructura"), json={"kind": "escena", "title": "E"}).json()["id"]


def _db(settings: Settings) -> sqlite3.Connection:
    return sqlite3.connect(Path(settings.database_url.removeprefix("sqlite:///")))


def _raw_link(settings: Settings, project_id: int, src_kind: str, src_id: int, dst_kind: str, dst_id: int, relation: str) -> None:
    with closing(_db(settings)) as connection:
        connection.execute(
            "INSERT INTO narrative_links (project_id, source_kind, source_id, target_kind, target_id, relation, "
            "estado, origen, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'provisional', 'autor', "
            "'2026-01-01', '2026-01-01')",
            (project_id, src_kind, src_id, dst_kind, dst_id, relation),
        )
        connection.commit()


def _link_count(settings: Settings) -> int:
    with closing(_db(settings)) as connection:
        return connection.execute("SELECT COUNT(*) FROM narrative_links").fetchone()[0]


# ----------------------------------------------------------------------
# 1. Integridad de los vínculos
# ----------------------------------------------------------------------


def test_un_vinculo_insertado_en_sql_entre_proyectos_se_rechaza(api: TestClient, settings: Settings) -> None:
    """Hallazgo: la base aceptaba cualquier par de ids. Solo el servicio lo impedía."""
    first = _project(api, "Primera")
    second = _project(api, "Segunda")
    ana_second = _character(api, second, "Ajena")
    scene_first = _scene(api, first)
    with pytest.raises(sqlite3.DatabaseError):
        _raw_link(settings, first, "personaje", ana_second, "escena", scene_first, "participa_en")
    assert _link_count(settings) == 0


def test_un_vinculo_insertado_en_sql_a_un_elemento_archivado_se_rechaza(api: TestClient, settings: Settings) -> None:
    project = _project(api, "P")
    ana = _character(api, project)
    api.post(_url(project, f"/personajes/{ana}/archivar"))
    scene = _scene(api, project)
    with pytest.raises(sqlite3.DatabaseError):
        _raw_link(settings, project, "personaje", ana, "escena", scene, "participa_en")


def test_un_vinculo_insertado_en_sql_con_tipo_desconocido_se_rechaza(api: TestClient, settings: Settings) -> None:
    project = _project(api, "P")
    ana = _character(api, project)
    with pytest.raises(sqlite3.DatabaseError):
        _raw_link(settings, project, "personaje", ana, "dragon", 1, "participa_en")


def test_un_vinculo_insertado_en_sql_valido_se_acepta(api: TestClient, settings: Settings) -> None:
    project = _project(api, "P")
    ana = _character(api, project)
    scene = _scene(api, project)
    _raw_link(settings, project, "personaje", ana, "escena", scene, "participa_en")
    assert _link_count(settings) == 1


def test_la_creacion_concurrente_de_un_duplicado_responde_409_y_no_500(
    api: TestClient, session_factory, settings: Settings  # type: ignore[no-untyped-def]
) -> None:
    """Hallazgo: la comprobación previa de duplicados no es atómica. Dos peticiones simultáneas
    pasan la comprobación y la segunda falla con IntegrityError (500). Se fuerza la carrera
    haciendo que la comprobación no vea el duplicado ya insertado."""
    project = _project(api, "P")
    ana = _character(api, project)
    scene = _scene(api, project)
    first = api.post(_url(project, "/vinculos"), json={
        "origen": {"tipo": "personaje", "id": ana}, "destino": {"tipo": "escena", "id": scene}, "relacion": "participa_en",
    })
    assert first.status_code == 201
    with session_factory() as session:
        service = PlanningService(session, clock=FakeClock())
        original = service._has_duplicate
        calls = {"n": 0}

        def first_check_misses(*args, **kwargs):  # type: ignore[no-untyped-def]
            # Solo la primera comprobación falla (la carrera). La del tratamiento del error ve el duplicado real.
            calls["n"] += 1
            return False if calls["n"] == 1 else original(*args, **kwargs)

        service._has_duplicate = first_check_misses  # type: ignore[method-assign]
        with pytest.raises(ConflictError):
            service.link(project, ("personaje", ana), ("escena", scene), "participa_en")
    assert _link_count(settings) == 1


def test_aceptar_una_propuesta_archivada_se_rechaza(api: TestClient) -> None:
    """Hallazgo: aceptar_propuesta no comprobaba que el elemento estuviera activo."""
    project = _project(api, "P")
    proposal = api.post(_url(project, "/lugares/propuestas"), json={"name": "Propuesto"}).json()
    api.post(_url(project, f"/lugares/{proposal['id']}/archivar"))
    response = api.post(_url(project, f"/lugares/{proposal['id']}/aceptar-propuesta"))
    assert response.status_code == 422
    assert api.get(_url(project, f"/lugares/{proposal['id']}")).json()["estado"] == "propuesta_ia"


def test_archivar_un_extremo_deja_el_vinculo_visible_con_su_extremo_archivado(api: TestClient) -> None:
    """Decisión documentada: archivar un elemento no archiva sus vínculos. El vínculo sigue siendo
    consultable, y ningún vínculo nuevo puede apuntar al elemento archivado."""
    project = _project(api, "P")
    ana = _character(api, project)
    scene = _scene(api, project)
    api.post(_url(project, "/vinculos"), json={
        "origen": {"tipo": "personaje", "id": ana}, "destino": {"tipo": "escena", "id": scene}, "relacion": "participa_en",
    })
    api.post(_url(project, f"/personajes/{ana}/archivar"))
    assert len(api.get(_url(project, f"/personajes/{ana}/vinculos"), params={"include_archived": True}).json()) == 1
    rejected = api.post(_url(project, "/vinculos"), json={
        "origen": {"tipo": "personaje", "id": ana}, "destino": {"tipo": "escena", "id": scene}, "relacion": "participa_en",
    })
    assert rejected.status_code == 422


# ----------------------------------------------------------------------
# 2. Historial de decisiones y atomicidad
# ----------------------------------------------------------------------


def _service(session_factory, clock: FakeClock | None = None):  # type: ignore[no-untyped-def]
    session = session_factory()
    return session, PlanningService(session, clock=clock or FakeClock())


def test_la_decision_registra_el_estado_anterior_el_resultado_y_el_actor(api: TestClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    project = _project(api, "P")
    ana = _character(api, project, "Antes")
    session, service = _service(session_factory)
    try:
        service.update("personaje", project, ana, {"name": "Antes"})  # no cambia nada: no genera decisión
        service.approve("personaje", project, ana, confirmar=True, nota="Cerrado")
        service.update("personaje", project, ana, {"name": "Después"}, confirmar_cambio_canon=True)
    finally:
        session.close()
    decisions = api.get(_url(project, f"/personajes/{ana}/decisiones")).json()
    assert [d["accion"] for d in decisions] == ["aprobar_canon", "modificar_canon"]
    approval, change = decisions
    assert all(d["actor"] == "autor" for d in decisions)
    assert '"name": "Antes"' in approval["snapshot"] and approval["estado_previo"] == "provisional"
    assert '"estado": "canonico"' in approval["resultado"] and approval["nota"] == "Cerrado"
    assert '"name": "Antes"' in change["snapshot"]  # estado anterior: el nombre antes del cambio
    assert '"name": "Después"' in change["resultado"]  # estado resultante
    assert '"estado": "provisional"' in change["resultado"]


def test_la_ia_no_puede_aprobar_aceptar_ni_modificar_canon(api: TestClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    project = _project(api, "P")
    proposal = api.post(_url(project, "/lugares/propuestas"), json={"name": "Propuesta"}).json()
    canon = api.post(_url(project, "/lugares"), json={"name": "Canon"}).json()
    api.post(_url(project, f"/lugares/{canon['id']}/aprobar"), json={"confirmar": True})
    session, service = _service(session_factory)
    try:
        with pytest.raises(ValidationFailed):
            service.approve("lugar", project, proposal["id"], confirmar=True, actor="ia")
        with pytest.raises(ValidationFailed):
            service.accept_proposal("lugar", project, proposal["id"], actor="ia")
        with pytest.raises(ValidationFailed):
            service.update("lugar", project, canon["id"], {"name": "Cambio de la IA"}, confirmar_cambio_canon=True, actor="ia")
    finally:
        session.close()
    assert api.get(_url(project, f"/lugares/{proposal['id']}")).json()["estado"] == "propuesta_ia"
    current = api.get(_url(project, f"/lugares/{canon['id']}")).json()
    assert current["name"] == "Canon" and current["estado"] == "canonico"


def test_archivar_un_canonico_deja_en_la_decision_el_estado_resultante(api: TestClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    project = _project(api, "P")
    place = _character_place = api.post(_url(project, "/lugares"), json={"name": "Lugar"}).json()
    api.post(_url(project, f"/lugares/{place['id']}/aprobar"), json={"confirmar": True})
    api.post(_url(project, f"/lugares/{place['id']}/archivar"), params={"confirmar_canon": True})
    decisions = api.get(_url(project, f"/lugares/{place['id']}/decisiones")).json()
    assert [d["accion"] for d in decisions] == ["aprobar_canon", "archivar"]
    assert '"archived_at": null' in decisions[1]["snapshot"]
    assert '"archived_at": "' in decisions[1]["resultado"]


def test_un_fallo_al_confirmar_no_deja_el_cambio_narrativo_persistido(api: TestClient, session_factory, settings: Settings) -> None:  # type: ignore[no-untyped-def]
    """Hallazgo a verificar: si la confirmación falla tras modificar atributos, la sesión conserva
    el cambio sin persistir y la siguiente operación podía guardarlo."""
    project = _project(api, "P")
    ana = _character(api, project, "Original")
    api.post(_url(project, f"/personajes/{ana}/aprobar"), json={"confirmar": True})
    session, service = _service(session_factory)
    try:
        original_commit = session.commit
        calls = {"n": 0}

        def failing_commit() -> None:
            calls["n"] += 1
            raise sqlite3.OperationalError("fallo simulado al confirmar")

        session.commit = failing_commit  # type: ignore[method-assign]
        with pytest.raises(sqlite3.OperationalError):
            service.update("personaje", project, ana, {"name": "Cambiado"}, confirmar_cambio_canon=True)
        session.commit = original_commit  # type: ignore[method-assign]
        # La siguiente operación de la misma sesión no debe arrastrar el cambio fallido.
        service.get("personaje", project, ana)
        service.list("personaje", project)
        session.commit()
    finally:
        session.close()
    assert api.get(_url(project, f"/personajes/{ana}")).json()["name"] == "Original"
    assert api.get(_url(project, f"/personajes/{ana}")).json()["estado"] == "canonico"
    assert api.get(_url(project, f"/personajes/{ana}/decisiones")).json()[-1]["accion"] == "aprobar_canon"


def test_un_fallo_al_registrar_la_decision_no_cambia_el_elemento(api: TestClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    project = _project(api, "P")
    place = api.post(_url(project, "/lugares"), json={"name": "Lugar"}).json()
    session, service = _service(session_factory)
    try:
        def failing_record(*args, **kwargs):  # type: ignore[no-untyped-def]
            raise sqlite3.OperationalError("no se puede registrar la decisión")

        service._record = failing_record  # type: ignore[method-assign]
        with pytest.raises(sqlite3.OperationalError):
            service.approve("lugar", project, place["id"], confirmar=True)
    finally:
        session.close()
    current = api.get(_url(project, f"/lugares/{place['id']}")).json()
    assert current["estado"] == "provisional"
    assert current["approved_decision_id"] is None
    assert api.get(_url(project, f"/lugares/{place['id']}/decisiones")).json() == []


# ----------------------------------------------------------------------
# 3. Datos generales de la novela: sin estado de canon (comportamiento documentado)
# ----------------------------------------------------------------------


def test_los_campos_narrativos_del_proyecto_no_tienen_estado_de_canon(api: TestClient) -> None:
    project = _project(api, "P")
    body = api.patch(_url(project, "/narrativa"), json={"premise": "Premisa cambiable"}).json()
    assert "estado" not in body and "origen" not in body
    assert api.get(_url(project, "/narrativa")).json().get("approved_decision_id") is None


def test_archivar_un_vinculo_cuyo_extremo_ya_esta_archivado_sigue_permitido(api: TestClient, settings: Settings) -> None:
    """Regresión: el disparador de vínculos no debe impedir archivar el propio vínculo."""
    project = _project(api, "P")
    ana = _character(api, project)
    scene = _scene(api, project)
    link = api.post(_url(project, "/vinculos"), json={
        "origen": {"tipo": "personaje", "id": ana}, "destino": {"tipo": "escena", "id": scene}, "relacion": "participa_en",
    }).json()
    api.post(_url(project, f"/personajes/{ana}/archivar"))
    response = api.post(_url(project, f"/vinculos/{link['id']}/archivar"))
    assert response.status_code == 200
    assert response.json()["archived_at"] is not None


def test_un_vinculo_no_puede_reapuntarse_a_otra_novela_con_sql(api: TestClient, settings: Settings) -> None:
    first = _project(api, "Primera")
    second = _project(api, "Segunda")
    ana = _character(api, first)
    scene = _scene(api, first)
    link = api.post(_url(first, "/vinculos"), json={
        "origen": {"tipo": "personaje", "id": ana}, "destino": {"tipo": "escena", "id": scene}, "relacion": "participa_en",
    }).json()
    foreign = _character(api, second, "Ajena")
    with closing(_db(settings)) as connection:
        with pytest.raises(sqlite3.DatabaseError):
            connection.execute("UPDATE narrative_links SET source_id = ? WHERE id = ?", (foreign, link["id"]))


def test_la_ia_no_puede_archivar_material_que_no_sea_propuesta(api: TestClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    project = _project(api, "P")
    place = api.post(_url(project, "/lugares"), json={"name": "Lugar del autor"}).json()
    session, service = _service(session_factory)
    try:
        with pytest.raises(ValidationFailed):
            service.archive("lugar", project, place["id"], actor="ia")
    finally:
        session.close()
    assert api.get(_url(project, f"/lugares/{place['id']}")).json()["archived_at"] is None


def test_un_actor_desconocido_se_rechaza(api: TestClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    project = _project(api, "P")
    place = api.post(_url(project, "/lugares"), json={"name": "Lugar"}).json()
    session, service = _service(session_factory)
    try:
        with pytest.raises(ValidationFailed):
            service.approve("lugar", project, place["id"], confirmar=True, actor="sistema_externo")
    finally:
        session.close()
    assert api.get(_url(project, f"/lugares/{place['id']}")).json()["estado"] == "provisional"


def test_si_la_base_rechaza_un_vinculo_no_se_responde_que_ya_existe(api: TestClient, session_factory, settings: Settings) -> None:  # type: ignore[no-untyped-def]
    """Si el disparador rechaza el INSERT (el extremo se archivó tras la comprobación), el error no es un duplicado."""
    project = _project(api, "P")
    ana = _character(api, project)
    scene = _scene(api, project)
    with closing(_db(settings)) as connection:
        connection.execute("UPDATE characters SET archived_at = '2026-01-02' WHERE id = ?", (ana,))
        connection.commit()
    session, service = _service(session_factory)
    try:
        service._endpoint = lambda *args, **kwargs: None  # type: ignore[method-assign]  # simula la carrera
        with pytest.raises(ValidationFailed) as error:
            service.link(project, ("personaje", ana), ("escena", scene), "participa_en")
        assert not isinstance(error.value, ConflictError)
    finally:
        session.close()
    assert _link_count(settings) == 0
