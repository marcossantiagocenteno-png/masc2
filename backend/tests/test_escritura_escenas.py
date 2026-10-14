"""Escritura de escenas: manuscrito propio por escena, sin copias, con versiones y recuperación intactas."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.db.models import Manuscript, ManuscriptDraft, SceneManuscript
from app.planning.escritura import SceneWritingService
from app.texts.errors import ConflictError
from tests.backup_fakes import FakeClock
from tests.test_migrations import _config


@pytest.fixture
def api(client: TestClient) -> TestClient:
    client.app.state.clock = FakeClock()
    return client


def _p(project_id: int, path: str = "") -> str:
    return f"/projects/{project_id}/planificacion{path}"


def _project(api: TestClient, name: str) -> int:
    return api.post("/projects", json={"name": name}).json()["id"]


def _node(api: TestClient, project_id: int, kind: str, parent: int | None = None, title: str = "") -> dict:
    response = api.post(_p(project_id, "/estructura"), json={"kind": kind, "parent_id": parent, "title": title or kind})
    assert response.status_code == 201, response.text
    return response.json()


def _start(api: TestClient, project_id: int, scene_id: int):  # type: ignore[no-untyped-def]
    return api.post(_p(project_id, f"/estructura/{scene_id}/escritura"))


def _save(api: TestClient, project_id: int, scene_id: int, content: str, base: int):  # type: ignore[no-untyped-def]
    return api.put(_p(project_id, f"/estructura/{scene_id}/escritura/borrador"), json={"content": content, "base_revision": base, "keep_previous": False})


def _read(api: TestClient, project_id: int, scene_id: int) -> dict:
    response = api.get(_p(project_id, f"/estructura/{scene_id}/escritura"))
    assert response.status_code == 200, response.text
    return response.json()


def _scene_with_chapters(api: TestClient, name: str) -> tuple[int, dict, dict, dict]:
    project = _project(api, name)
    act = _node(api, project, "acto", title="Acto")
    cap_1 = _node(api, project, "capitulo", act["id"], title="Cap 1")
    cap_2 = _node(api, project, "capitulo", act["id"], title="Cap 2")
    scene = _node(api, project, "escena", cap_1["id"], title="Llegada")
    return project, scene, cap_1, cap_2


# ----------------------------------------------------------------------
# Vincular y estados
# ----------------------------------------------------------------------


def test_iniciar_la_escritura_crea_un_manuscrito_propio_sin_texto(api: TestClient) -> None:
    project, scene, _, _ = _scene_with_chapters(api, "Inicio")
    assert _read(api, project, scene["id"])["state"] == "sin_escritura"

    response = _start(api, project, scene["id"])
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["state"] == "sin_texto"
    assert body["manuscript_id"] is not None
    assert body["draft"]["content"] == ""
    assert body["draft"]["revision"] == 1
    assert body["versions_count"] == 1  # versión 1 vacía, creada al iniciar


def test_iniciar_otra_vez_no_duplica_nada(api: TestClient) -> None:
    project, scene, _, _ = _scene_with_chapters(api, "Idempotente")
    first = _start(api, project, scene["id"]).json()
    manuscripts_before = len(api.get("/manuscripts").json())
    second = _start(api, project, scene["id"])
    assert second.status_code == 200
    assert second.json()["manuscript_id"] == first["manuscript_id"]
    assert len(api.get("/manuscripts").json()) == manuscripts_before


def test_el_texto_persiste_tras_guardar_y_recargar(api: TestClient) -> None:
    project, scene, _, _ = _scene_with_chapters(api, "Persistir")
    _start(api, project, scene["id"])
    saved = _save(api, project, scene["id"], "Llegó tarde a la estación.", 1)
    assert saved.status_code == 200, saved.text
    assert saved.json()["revision"] == 2

    reloaded = _read(api, project, scene["id"])  # una lectura nueva, como tras recargar la página
    assert reloaded["state"] == "con_texto"
    assert reloaded["draft"]["content"] == "Llegó tarde a la estación."
    assert reloaded["draft"]["revision"] == 2


def test_la_escena_sin_texto_y_la_que_tiene_contenido_se_distinguen_en_la_estructura(api: TestClient) -> None:
    project, scene, _, _ = _scene_with_chapters(api, "Estados")
    other = _node(api, project, "escena", title="Sin escribir")
    untouched = _node(api, project, "escena", title="Nada")
    _start(api, project, scene["id"])
    _save(api, project, scene["id"], "Texto", 1)
    _start(api, project, other["id"])
    states = {node["id"]: node.get("escritura") for node in api.get(_p(project, "/estructura")).json()}
    assert states[scene["id"]] == "con_texto"
    assert states[other["id"]] == "sin_texto"
    assert states[untouched["id"]] == "sin_escritura"


def test_guardar_con_una_revision_antigua_responde_409_y_conserva_el_texto_rechazado(api: TestClient) -> None:
    project, scene, _, _ = _scene_with_chapters(api, "Conflicto")
    manuscript_id = _start(api, project, scene["id"]).json()["manuscript_id"]
    assert _save(api, project, scene["id"], "Versión de la ventana A", 1).status_code == 200

    stale = _save(api, project, scene["id"], "Versión de la ventana B", 1)
    assert stale.status_code == 409
    assert stale.json()["current_content"] == "Versión de la ventana A"
    assert _read(api, project, scene["id"])["draft"]["content"] == "Versión de la ventana A"
    points = api.get(f"/manuscripts/{manuscript_id}/recovery-points").json()
    conflict = [point for point in points if point["reason"] == "conflicto"]
    assert len(conflict) == 1
    assert api.get(f"/manuscripts/{manuscript_id}/recovery-points/{conflict[0]['id']}").json()["content"] == "Versión de la ventana B"


def test_guardar_sin_haber_iniciado_la_escritura_se_rechaza(api: TestClient) -> None:
    project, scene, _, _ = _scene_with_chapters(api, "Sin iniciar")
    response = _save(api, project, scene["id"], "Texto", 1)
    assert response.status_code == 404


# ----------------------------------------------------------------------
# Mover y renombrar
# ----------------------------------------------------------------------


def test_mover_la_escena_conserva_su_texto_y_su_union(api: TestClient) -> None:
    project, scene, cap_1, cap_2 = _scene_with_chapters(api, "Mover")
    manuscript_id = _start(api, project, scene["id"]).json()["manuscript_id"]
    _save(api, project, scene["id"], "Texto que no debe perderse.", 1)

    moved = api.post(_p(project, f"/estructura/{scene['id']}/mover"), json={"parent_id": cap_2["id"], "posicion": None, "confirmar_cambio_canon": False})
    assert moved.status_code == 200

    after = _read(api, project, scene["id"])
    assert after["manuscript_id"] == manuscript_id
    assert after["draft"]["content"] == "Texto que no debe perderse."


def test_renombrar_la_escena_conserva_la_union_y_actualiza_el_titulo_del_manuscrito(api: TestClient) -> None:
    project, scene, _, _ = _scene_with_chapters(api, "Renombrar")
    manuscript_id = _start(api, project, scene["id"]).json()["manuscript_id"]
    _save(api, project, scene["id"], "Texto", 1)

    response = api.patch(_p(project, f"/estructura/{scene['id']}"), json={"title": "Nuevo nombre"})
    assert response.status_code == 200, response.text

    after = _read(api, project, scene["id"])
    assert after["manuscript_id"] == manuscript_id
    assert after["draft"]["content"] == "Texto"
    manuscripts = {item["id"]: item for item in api.get("/manuscripts").json()}
    assert manuscripts[manuscript_id]["title"] == "Nuevo nombre"


def test_el_manuscrito_de_escena_no_aparece_en_la_lista_del_proyecto_pero_si_el_normal(api: TestClient) -> None:
    project, scene, _, _ = _scene_with_chapters(api, "Lista")
    scene_manuscript = _start(api, project, scene["id"]).json()["manuscript_id"]
    ordinary = api.post(_p(project).replace("/planificacion", "") + "/manuscripts", json={"title": "Capítulo suelto", "content": "Texto"})
    assert ordinary.status_code == 201, ordinary.text
    listed = [item["id"] for item in api.get(f"/projects/{project}/manuscripts").json()]
    assert ordinary.json()["id"] in listed
    assert scene_manuscript not in listed


# ----------------------------------------------------------------------
# Versiones y recuperación siguen funcionando
# ----------------------------------------------------------------------


def test_las_versiones_y_los_puntos_de_recuperacion_del_manuscrito_de_escena_siguen_funcionando(api: TestClient) -> None:
    project, scene, _, _ = _scene_with_chapters(api, "Versiones")
    manuscript_id = _start(api, project, scene["id"]).json()["manuscript_id"]
    _save(api, project, scene["id"], "Primera idea", 1)
    _save(api, project, scene["id"], "Segunda idea", 2)

    version = api.post(
        f"/manuscripts/{manuscript_id}/versions",
        json={"content": "Segunda idea", "note": "Versión formal", "based_on_version_id": None},
    )
    assert version.status_code == 201, version.text
    versions = api.get(f"/manuscripts/{manuscript_id}/versions").json()
    assert [item["number"] for item in versions] == [1, 2]
    assert versions[0]["char_count"] == 0  # la versión 1 vacía no cambia

    # El borrador no se convierte en versión: la versión formal no cambia el borrador.
    assert _read(api, project, scene["id"])["draft"]["content"] == "Segunda idea"

    points = api.get(f"/manuscripts/{manuscript_id}/recovery-points").json()
    assert points, "debe haber puntos de recuperación tras los guardados"
    first_point = points[-1]
    restored = api.post(
        f"/manuscripts/{manuscript_id}/recovery-points/{first_point['id']}/restore",
        json={"base_revision": _read(api, project, scene["id"])["draft"]["revision"]},
    )
    assert restored.status_code == 200, restored.text
    point_content = api.get(f"/manuscripts/{manuscript_id}/recovery-points/{first_point['id']}").json()["content"]
    assert _read(api, project, scene["id"])["draft"]["content"] == point_content


# ----------------------------------------------------------------------
# Aislamiento y restricciones de la base
# ----------------------------------------------------------------------


def test_una_escena_de_otro_proyecto_no_se_lee_ni_se_escribe_desde_este(api: TestClient) -> None:
    project_a, scene_a, _, _ = _scene_with_chapters(api, "Proyecto A")
    project_b, _, _, _ = _scene_with_chapters(api, "Proyecto B")
    _start(api, project_a, scene_a["id"])
    assert api.get(_p(project_b, f"/estructura/{scene_a['id']}/escritura")).status_code == 404
    assert api.post(_p(project_b, f"/estructura/{scene_a['id']}/escritura")).status_code == 404
    assert _save(api, project_b, scene_a["id"], "Intruso", 1).status_code == 404
    assert _read(api, project_a, scene_a["id"])["draft"]["content"] == ""


def test_la_base_rechaza_unir_una_escena_con_un_manuscrito_de_otro_proyecto(client: TestClient, settings: Settings) -> None:
    client.app.state.clock = FakeClock()
    project_a = _project(client, "Base A")
    project_b = _project(client, "Base B")
    scene_a = _node(client, project_a, "escena", title="Escena A")
    other = client.post(f"/projects/{project_b}/manuscripts", json={"title": "De B", "content": "x"}).json()
    session = client.app.state.session_factory()
    try:
        session.add(SceneManuscript(project_id=project_a, node_id=scene_a["id"], manuscript_id=other["id"], created_at=FakeClock().now))
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()


def test_la_base_rechaza_unir_un_acto_o_modificar_o_borrar_la_union(client: TestClient) -> None:
    client.app.state.clock = FakeClock()
    project = _project(client, "Base inmutable")
    act = _node(client, project, "acto", title="Acto")
    scene = _node(client, project, "escena", title="Escena")
    manuscript = client.post(f"/projects/{project}/manuscripts", json={"title": "M", "content": ""}).json()
    session = client.app.state.session_factory()
    try:
        session.add(SceneManuscript(project_id=project, node_id=act["id"], manuscript_id=manuscript["id"], created_at=FakeClock().now))
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()

    _start(client, project, scene["id"])
    session = client.app.state.session_factory()
    try:
        row = session.query(SceneManuscript).one()
        with pytest.raises(IntegrityError):
            session.execute(SceneManuscript.__table__.update().where(SceneManuscript.id == row.id).values(node_id=act["id"]))
        with pytest.raises(IntegrityError):
            session.execute(SceneManuscript.__table__.delete().where(SceneManuscript.id == row.id))
    finally:
        session.rollback()
        session.close()


def test_un_proyecto_archivado_no_admite_iniciar_ni_guardar(api: TestClient) -> None:
    project, scene, _, _ = _scene_with_chapters(api, "Archivado")
    _start(api, project, scene["id"])
    api.post(f"/projects/{project}/archive")
    assert _start(api, project, scene["id"]).status_code == 422
    assert _save(api, project, scene["id"], "Nuevo", 1).status_code == 422


def test_una_escena_archivada_no_admite_escribir_pero_conserva_su_texto(api: TestClient) -> None:
    project, scene, _, _ = _scene_with_chapters(api, "Escena archivada")
    _start(api, project, scene["id"])
    _save(api, project, scene["id"], "Antes de archivar", 1)
    api.post(_p(project, f"/estructura/{scene['id']}/archivar"))
    assert _save(api, project, scene["id"], "Después", 2).status_code == 422
    assert _read(api, project, scene["id"])["draft"]["content"] == "Antes de archivar"


# ----------------------------------------------------------------------
# Concurrencia
# ----------------------------------------------------------------------


def test_dos_inicios_simultaneos_crean_una_sola_escritura(settings: Settings, client: TestClient) -> None:
    """Una lectura obsoleta no duplica la escritura: la unión de la primera gana y la segunda se deshace."""
    client.app.state.clock = FakeClock()
    project, scene, _, _ = _scene_with_chapters(client, "Carrera")
    factory = client.app.state.session_factory
    with factory() as first_session, factory() as second_session:
        first = SceneWritingService(first_session, clock=FakeClock(), max_chars=settings.max_version_chars)
        second = SceneWritingService(second_session, clock=FakeClock(), max_chars=settings.max_version_chars)
        winner, created = first.start(project, scene["id"])
        assert created

        real_link = second._link
        calls = {"n": 0}

        def stale_then_real(project_id: int, node_id: int):  # type: ignore[no-untyped-def]
            calls["n"] += 1
            return None if calls["n"] == 1 else real_link(project_id, node_id)

        second._link = stale_then_real  # type: ignore[method-assign]
        loser, created_second = second.start(project, scene["id"])
    assert not created_second
    assert loser.manuscript_id == winner.manuscript_id
    with factory() as session:
        assert session.query(SceneManuscript).count() == 1
        assert session.query(Manuscript).filter(Manuscript.project_id == project).count() == 1


def test_dos_guardados_con_la_misma_revision_no_se_pisan(settings: Settings, client: TestClient) -> None:
    client.app.state.clock = FakeClock()
    project, scene, _, _ = _scene_with_chapters(client, "Doble guardado")
    _start(client, project, scene["id"])
    factory = client.app.state.session_factory
    with factory() as session_a, factory() as session_b:
        service_a = SceneWritingService(session_a, clock=FakeClock(), max_chars=settings.max_version_chars)
        service_b = SceneWritingService(session_b, clock=FakeClock(), max_chars=settings.max_version_chars)
        service_a.save(project, scene["id"], "Del primero", 1)
        with pytest.raises(ConflictError):
            # `DraftConflict` hereda de `TextError`; el comportamiento importante es que no se aplica.
            service_b.save(project, scene["id"], "Del segundo", 1)
    assert _read(client, project, scene["id"])["draft"]["content"] == "Del primero"


# ----------------------------------------------------------------------
# Migración 0009
# ----------------------------------------------------------------------


def test_la_migracion_0009_conserva_escenas_y_textos_existentes(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'previa.sqlite').as_posix()}"
    db_path = Path(url.removeprefix("sqlite:///"))
    command.upgrade(_config(url), "0008_revision_estructura")
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("INSERT INTO projects (name, status, created_at, updated_at, structure_version) VALUES ('Previa', 'activo', '2026-01-01 10:00:00', '2026-01-01 10:00:00', 0)")
        connection.execute(
            "INSERT INTO structure_nodes (project_id, parent_id, kind, position, title, estado, origen, created_at, updated_at) "
            "VALUES (1, NULL, 'escena', 0, 'Escena previa', 'provisional', 'autor', '2026-01-01 10:00:00', '2026-01-01 10:00:00')"
        )
        connection.commit()

    command.upgrade(_config(url), "head")

    with closing(sqlite3.connect(db_path)) as connection:
        assert connection.execute("SELECT title FROM structure_nodes").fetchall() == [("Escena previa",)]
        assert connection.execute("SELECT COUNT(*) FROM scene_manuscripts").fetchone() == (0,)
