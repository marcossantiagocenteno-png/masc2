"""Proyectos: aislamiento entre novelas, archivado, restauración y sin borrado."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient


def _project(client: TestClient, name: str) -> dict[str, Any]:
    response = client.post("/projects", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def _manuscript(client: TestClient, project_id: int, title: str, content: str) -> dict[str, Any]:
    response = client.post(f"/projects/{project_id}/manuscripts", json={"title": title, "content": content})
    assert response.status_code == 201, response.text
    return response.json()


def test_dos_proyectos_son_independientes(client: TestClient) -> None:
    first = _project(client, "Novela A")
    second = _project(client, "Novela B")
    a_text = _manuscript(client, first["id"], "Manuscrito A", "Texto exclusivo de A.")
    b_text = _manuscript(client, second["id"], "Manuscrito B", "Texto exclusivo de B.")

    a_titles = [m["title"] for m in client.get(f"/projects/{first['id']}/manuscripts").json()]
    b_titles = [m["title"] for m in client.get(f"/projects/{second['id']}/manuscripts").json()]
    assert a_titles == ["Manuscrito A"]
    assert b_titles == ["Manuscrito B"]

    # Ningún dato de A aparece en B, ni en sus versiones.
    a_version = client.get(f"/manuscripts/{a_text['id']}/versions").json()[0]
    b_versions = client.get(f"/manuscripts/{b_text['id']}/versions").json()
    assert all(v["id"] != a_version["id"] for v in b_versions)
    assert "Texto exclusivo de A." not in str(client.get(f"/projects/{second['id']}").json())
    assert a_text["project_id"] == first["id"]
    assert b_text["project_id"] == second["id"]


def test_listado_general_sigue_mostrando_todos_los_manuscritos(client: TestClient) -> None:
    project = _project(client, "Visible")
    created = _manuscript(client, project["id"], "Dentro del proyecto", "Texto.")
    listed = client.get("/manuscripts").json()
    assert any(m["id"] == created["id"] and m["project_id"] == project["id"] for m in listed)


def test_renombrar_y_validar_el_nombre(client: TestClient) -> None:
    project = _project(client, "Nombre inicial")
    renamed = client.patch(f"/projects/{project['id']}", json={"name": "  Nuevo nombre  "})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Nuevo nombre"
    assert client.patch(f"/projects/{project['id']}", json={"name": "   "}).status_code == 422
    assert client.post("/projects", json={"name": ""}).status_code == 422


def test_archivar_conserva_la_lectura_y_bloquea_nuevos_manuscritos(client: TestClient) -> None:
    project = _project(client, "Para archivar")
    manuscript = _manuscript(client, project["id"], "Antiguo", "Contenido que sigue existiendo.")

    archived = client.post(f"/projects/{project['id']}/archive")
    assert archived.status_code == 200
    assert archived.json()["status"] == "archivado"
    assert archived.json()["archived_at"] is not None

    # Sigue siendo legible: no se pierde nada al archivar.
    assert client.get(f"/manuscripts/{manuscript['id']}").status_code == 200
    assert client.get(f"/projects/{project['id']}/manuscripts").json()[0]["id"] == manuscript["id"]

    blocked = client.post(f"/projects/{project['id']}/manuscripts", json={"title": "Nuevo", "content": "x"})
    assert blocked.status_code == 422
    assert "archivado" in blocked.json()["detail"]


def test_archivar_dos_veces_y_restaurar_con_validacion(client: TestClient) -> None:
    project = _project(client, "Ciclo")
    client.post(f"/projects/{project['id']}/archive")
    assert client.post(f"/projects/{project['id']}/archive").status_code == 422

    active_ids = [p["id"] for p in client.get("/projects").json()]
    archived_ids = [p["id"] for p in client.get("/projects", params={"status_filter": "archivado"}).json()]
    assert project["id"] not in active_ids
    assert project["id"] in archived_ids

    restored = client.post(f"/projects/{project['id']}/restore")
    assert restored.status_code == 200
    assert restored.json()["status"] == "activo"
    assert restored.json()["archived_at"] is None
    assert client.post(f"/projects/{project['id']}/restore").status_code == 422


def test_restaurado_admite_manuscritos_otra_vez(client: TestClient) -> None:
    project = _project(client, "Vuelve")
    client.post(f"/projects/{project['id']}/archive")
    client.post(f"/projects/{project['id']}/restore")
    assert _manuscript(client, project["id"], "Nuevo tras restaurar", "Texto.")["project_id"] == project["id"]


def test_detalle_muestra_recuento_y_ultima_actividad(client: TestClient) -> None:
    project = _project(client, "Actividad")
    empty = client.get(f"/projects/{project['id']}").json()
    assert empty["manuscript_count"] == 0
    assert empty["last_activity_at"] is None

    manuscript = _manuscript(client, project["id"], "Con actividad", "Texto.")
    client.post(f"/manuscripts/{manuscript['id']}/versions", json={"content": "Otra versión."})
    detail = client.get(f"/projects/{project['id']}").json()
    assert detail["manuscript_count"] == 1
    assert detail["last_activity_at"] is not None


def test_no_hay_borrado_de_proyectos(client: TestClient) -> None:
    project = _project(client, "Intocable")
    assert client.delete(f"/projects/{project['id']}").status_code == 405
    assert client.get(f"/projects/{project['id']}").status_code == 200


def test_proyecto_inexistente_responde_404(client: TestClient) -> None:
    assert client.get("/projects/999999").status_code == 404
    assert client.post("/projects/999999/archive").status_code == 404
    assert client.post("/projects/999999/manuscripts", json={"title": "x", "content": "y"}).status_code == 404


def test_estado_no_valido_se_rechaza(client: TestClient) -> None:
    assert client.get("/projects", params={"status_filter": "borrado"}).status_code == 422
