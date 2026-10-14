"""Mover actos, capítulos y escenas: movimientos válidos e inválidos, identidad, vínculos, canon y atomicidad."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.texts.errors import ConflictError
from tests.backup_fakes import FakeClock


@pytest.fixture
def api(client: TestClient) -> TestClient:
    client.app.state.clock = FakeClock()
    return client


def _url(project_id: int, path: str = "") -> str:
    return f"/projects/{project_id}/planificacion{path}"


def _project(api: TestClient, name: str) -> int:
    return api.post("/projects", json={"name": name}).json()["id"]


def _node(api: TestClient, project_id: int, kind: str, parent: int | None = None, title: str = "") -> dict:
    response = api.post(_url(project_id, "/estructura"), json={"kind": kind, "parent_id": parent, "title": title or kind})
    assert response.status_code == 201, response.text
    return response.json()


def _tree(api: TestClient, project_id: int) -> dict[int | None, list[str]]:
    """Títulos por padre, en orden de posición. Clave None = raíz."""
    nodes = api.get(_url(project_id, "/estructura"), params={"include_archived": True}).json()
    result: dict[int | None, list[str]] = {}
    for node in sorted(nodes, key=lambda n: (n["parent_id"] or 0, n["position"], n["id"])):
        result.setdefault(node["parent_id"], []).append(node["title"])
    return result


def _by_id(api: TestClient, project_id: int, node_id: int) -> dict:
    return api.get(_url(project_id, f"/estructura/{node_id}")).json()


def _move(api: TestClient, project_id: int, node_id: int, parent: int | None, posicion: int | None = None, confirm: bool = False):  # type: ignore[no-untyped-def]
    body = {"parent_id": parent, "posicion": posicion, "confirmar_cambio_canon": confirm}
    return api.post(_url(project_id, f"/estructura/{node_id}/mover"), json=body)


def _build(api: TestClient, project_id: int) -> dict[str, dict]:
    """Dos actos, dos capítulos (uno en cada acto), tres escenas en el primer capítulo."""
    acto_1 = _node(api, project_id, "acto", title="Acto 1")
    acto_2 = _node(api, project_id, "acto", title="Acto 2")
    capitulo_1 = _node(api, project_id, "capitulo", acto_1["id"], title="Cap 1")
    capitulo_2 = _node(api, project_id, "capitulo", acto_2["id"], title="Cap 2")
    escena_a = _node(api, project_id, "escena", capitulo_1["id"], title="Escena A")
    escena_b = _node(api, project_id, "escena", capitulo_1["id"], title="Escena B")
    escena_c = _node(api, project_id, "escena", capitulo_1["id"], title="Escena C")
    return {
        "acto1": acto_1,
        "acto2": acto_2,
        "cap1": capitulo_1,
        "cap2": capitulo_2,
        "a": escena_a,
        "b": escena_b,
        "c": escena_c,
    }


# ----------------------------------------------------------------------
# Movimientos válidos
# ----------------------------------------------------------------------


def test_una_escena_cambia_de_capitulo_conservando_identidad_y_datos(api: TestClient) -> None:
    project = _project(api, "Mover escena")
    n = _build(api, project)
    before = _by_id(api, project, n["b"]["id"])

    response = _move(api, project, n["b"]["id"], n["cap2"]["id"])

    assert response.status_code == 200, response.text
    after = _by_id(api, project, n["b"]["id"])
    assert after["id"] == before["id"]
    assert after["title"] == "Escena B"
    assert after["estado"] == before["estado"] and after["origen"] == before["origen"]
    assert after["parent_id"] == n["cap2"]["id"]
    assert _tree(api, project)[n["cap1"]["id"]] == ["Escena A", "Escena C"]  # origen compactado
    assert _tree(api, project)[n["cap2"]["id"]] == ["Escena B"]


def test_un_capitulo_cambia_de_acto(api: TestClient) -> None:
    project = _project(api, "Mover capítulo")
    n = _build(api, project)
    assert _move(api, project, n["cap1"]["id"], n["acto2"]["id"]).status_code == 200
    tree = _tree(api, project)
    assert tree.get(n["acto1"]["id"], []) == []
    assert tree[n["acto2"]["id"]] == ["Cap 2", "Cap 1"]  # al final de los hermanos del destino


def test_un_acto_cambia_de_posicion_en_la_novela(api: TestClient) -> None:
    project = _project(api, "Mover acto")
    n = _build(api, project)
    assert _move(api, project, n["acto2"]["id"], None, posicion=0).status_code == 200
    assert _tree(api, project)[None] == ["Acto 2", "Acto 1"]


def test_una_escena_puede_pasar_a_la_raiz(api: TestClient) -> None:
    project = _project(api, "Escena suelta")
    n = _build(api, project)
    assert _move(api, project, n["a"]["id"], None).status_code == 200
    assert _tree(api, project)[None] == ["Acto 1", "Acto 2", "Escena A"]


def test_la_posicion_de_destino_se_respeta(api: TestClient) -> None:
    project = _project(api, "Posición")
    n = _build(api, project)
    assert _move(api, project, n["a"]["id"], n["cap2"]["id"], posicion=0).status_code == 200
    assert _tree(api, project)[n["cap2"]["id"]] == ["Escena A"]


def test_las_posiciones_quedan_contiguas_en_origen_y_destino(api: TestClient) -> None:
    project = _project(api, "Contiguas")
    n = _build(api, project)
    _move(api, project, n["a"]["id"], n["cap2"]["id"], posicion=0)
    nodes = api.get(_url(project, "/estructura")).json()
    for parent in (n["cap1"]["id"], n["cap2"]["id"]):
        positions = sorted(node["position"] for node in nodes if node["parent_id"] == parent)
        assert positions == list(range(len(positions)))


# ----------------------------------------------------------------------
# Movimientos inválidos: se rechazan y no cambian nada
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("node", "target", "expected"),
    [
        pytest.param("escena", "escena", 422, id="escena-dentro-de-escena"),
        pytest.param("capitulo", "capitulo", 422, id="capitulo-dentro-de-capitulo"),
        pytest.param("acto", "capitulo", 422, id="acto-dentro-de-capitulo"),
        pytest.param("acto", "acto", 422, id="acto-dentro-de-acto"),
    ],
)
def test_un_padre_incompatible_se_rechaza(api: TestClient, node: str, target: str, expected: int) -> None:
    project = _project(api, "Incompatible")
    n = _build(api, project)
    node_id = {"escena": n["a"], "capitulo": n["cap1"], "acto": n["acto1"]}[node]["id"]
    target_id = {"escena": n["b"], "capitulo": n["cap2"], "acto": n["acto2"]}[target]["id"]
    before = _tree(api, project)
    response = _move(api, project, node_id, target_id)
    assert response.status_code == expected
    assert _tree(api, project) == before


def test_un_nodo_no_puede_ser_su_propio_padre_ni_crear_un_ciclo(api: TestClient) -> None:
    project = _project(api, "Ciclos")
    n = _build(api, project)
    before = _tree(api, project)
    assert _move(api, project, n["cap1"]["id"], n["cap1"]["id"]).status_code == 422
    assert _move(api, project, n["acto1"]["id"], n["cap1"]["id"]).status_code == 422  # acto dentro de su descendiente
    assert _tree(api, project) == before


def test_un_nodo_archivado_no_se_mueve(api: TestClient) -> None:
    project = _project(api, "Archivado origen")
    n = _build(api, project)
    api.post(_url(project, f"/estructura/{n['a']['id']}/archivar"))
    before = _tree(api, project)
    assert _move(api, project, n["a"]["id"], n["cap2"]["id"]).status_code == 422
    assert _tree(api, project) == before


def test_no_se_mueve_hacia_un_destino_archivado(api: TestClient) -> None:
    project = _project(api, "Archivado destino")
    n = _build(api, project)
    api.post(_url(project, f"/estructura/{n['cap2']['id']}/archivar"))
    before = _tree(api, project)
    assert _move(api, project, n["a"]["id"], n["cap2"]["id"]).status_code == 422
    assert _tree(api, project) == before


def test_una_posicion_fuera_de_rango_se_rechaza(api: TestClient) -> None:
    project = _project(api, "Rango")
    n = _build(api, project)
    before = _tree(api, project)
    assert _move(api, project, n["a"]["id"], n["cap2"]["id"], posicion=5).status_code == 422
    assert _tree(api, project) == before


# ----------------------------------------------------------------------
# Aislamiento entre proyectos
# ----------------------------------------------------------------------


def test_no_se_mueve_a_un_padre_de_otra_novela(api: TestClient) -> None:
    first = _project(api, "Primera")
    second = _project(api, "Segunda")
    a = _build(api, first)
    b = _build(api, second)
    before = _tree(api, first)
    response = _move(api, first, a["a"]["id"], b["cap2"]["id"])
    assert response.status_code == 404
    assert _tree(api, first) == before
    assert _tree(api, second).get(b["cap2"]["id"], []) == []


def test_no_se_mueve_un_nodo_de_otra_novela(api: TestClient) -> None:
    first = _project(api, "Primera")
    second = _project(api, "Segunda")
    a = _build(api, first)
    _build(api, second)
    assert _move(api, second, a["a"]["id"], None).status_code == 404
    assert _by_id(api, first, a["a"]["id"])["parent_id"] == a["cap1"]["id"]


# ----------------------------------------------------------------------
# Vínculos y canon
# ----------------------------------------------------------------------


def test_mover_una_escena_conserva_sus_vinculos(api: TestClient, settings: Settings) -> None:
    project = _project(api, "Vínculos")
    n = _build(api, project)
    character = api.post(_url(project, "/personajes"), json={"name": "Ana"}).json()
    link = api.post(_url(project, "/vinculos"), json={
        "origen": {"tipo": "personaje", "id": character["id"]},
        "destino": {"tipo": "escena", "id": n["b"]["id"]},
        "relacion": "participa_en",
    }).json()
    _move(api, project, n["b"]["id"], n["cap2"]["id"])
    links = api.get(_url(project, f"/estructura/{n['b']['id']}/vinculos")).json()
    assert [item["id"] for item in links] == [link["id"]]
    assert links[0]["target_id"] == n["b"]["id"]


def test_mover_un_canonico_exige_confirmacion_y_no_cambia_nada_sin_ella(api: TestClient) -> None:
    project = _project(api, "Canon")
    n = _build(api, project)
    api.post(_url(project, f"/estructura/{n['b']['id']}/aprobar"), json={"confirmar": True})
    before = _tree(api, project)
    response = _move(api, project, n["b"]["id"], n["cap2"]["id"])
    assert response.status_code == 409
    assert _tree(api, project) == before
    assert _by_id(api, project, n["b"]["id"])["estado"] == "canonico"


def test_mover_un_canonico_con_confirmacion_conserva_el_estado_y_registra_la_decision(api: TestClient) -> None:
    project = _project(api, "Canon confirmado")
    n = _build(api, project)
    api.post(_url(project, f"/estructura/{n['b']['id']}/aprobar"), json={"confirmar": True})
    response = _move(api, project, n["b"]["id"], n["cap2"]["id"], confirm=True)
    assert response.status_code == 200
    moved = _by_id(api, project, n["b"]["id"])
    assert moved["estado"] == "canonico"  # el movimiento no cambia el canon en silencio
    decisions = api.get(_url(project, f"/estructura/{n['b']['id']}/decisiones")).json()
    assert [d["accion"] for d in decisions] == ["aprobar_canon", "reubicar"]
    assert '"parent_id": ' + str(n["cap1"]["id"]) in decisions[1]["snapshot"]
    assert '"parent_id": ' + str(n["cap2"]["id"]) in decisions[1]["resultado"]


def test_reordenar_canonicos_exige_confirmacion(api: TestClient) -> None:
    project = _project(api, "Canon reordenar")
    n = _build(api, project)
    api.post(_url(project, f"/estructura/{n['a']['id']}/aprobar"), json={"confirmar": True})
    siblings = [n["a"]["id"], n["b"]["id"], n["c"]["id"]]
    response = api.post(_url(project, "/estructura/reordenar"), json={"parent_id": n["cap1"]["id"], "orden": [n["b"]["id"], n["a"]["id"], n["c"]["id"]]})
    assert response.status_code == 409
    assert api.get(_url(project, f"/estructura/{n['a']['id']}")).json()["position"] == siblings.index(n["a"]["id"])


# ----------------------------------------------------------------------
# Atomicidad y concurrencia
# ----------------------------------------------------------------------


def test_un_fallo_al_persistir_no_deja_la_estructura_a_medias(settings: Settings, client: TestClient) -> None:
    client.app.state.clock = FakeClock()
    project = _project(client, "Fallo")
    n = _build(client, project)
    before = _tree(client, project)
    from app.planning.service import PlanningService
    from app.db.session import create_engine_for, create_session_factory

    engine = create_engine_for(settings.database_url)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            service = PlanningService(session, clock=FakeClock())

            def failing_commit() -> None:
                raise sqlite3.OperationalError("fallo simulado al confirmar")

            session.commit = failing_commit  # type: ignore[method-assign]
            with pytest.raises(sqlite3.OperationalError):
                service.move_node(project, n["a"]["id"], n["cap2"]["id"])
    finally:
        engine.dispose()
    assert _tree(client, project) == before
    assert _by_id(client, project, n["a"]["id"])["parent_id"] == n["cap1"]["id"]


def test_mover_y_editar_dos_veces_no_pisan_la_revision(settings: Settings, client: TestClient) -> None:
    """Un movimiento con la revisión ya superada se rechaza sin escribir (ver test_concurrencia_estructura)."""
    client.app.state.clock = FakeClock()
    project = _project(client, "Revisión")
    n = _build(client, project)
    assert _move(client, project, n["a"]["id"], n["cap2"]["id"]).status_code == 200
    assert _move(client, project, n["b"]["id"], n["cap2"]["id"]).status_code == 200
    tree = _tree(client, project)
    assert tree[n["cap2"]["id"]] == ["Escena A", "Escena B"]
    assert tree[n["cap1"]["id"]] == ["Escena C"]
