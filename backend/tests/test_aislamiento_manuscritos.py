"""Aislamiento de manuscritos entre proyectos, consistencia del título e integridad de la unión con escenas.

Las pruebas negativas usan identificadores válidos de OTRO proyecto. Cada una comprueba que la operación
se rechaza y que ningún dato cambia. El aislamiento aquí es entre novelas, no autenticación.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

import pytest

from tests.backup_fakes import FakeClock


@pytest.fixture
def api(client: TestClient) -> TestClient:
    client.app.state.clock = FakeClock()
    return client


def _project(api: TestClient, name: str) -> int:
    return api.post("/projects", json={"name": name}).json()["id"]


def _manuscript(api: TestClient, project: int, title: str) -> dict:
    response = api.post(f"/projects/{project}/manuscripts", json={"title": title, "content": f"Texto de {title}"})
    assert response.status_code == 201, response.text
    return response.json()


def _scene(api: TestClient, project: int, title: str) -> dict:
    response = api.post(f"/projects/{project}/planificacion/estructura", json={"kind": "escena", "parent_id": None, "title": title})
    assert response.status_code == 201, response.text
    return response.json()


def _at(api: TestClient, manuscript_id: int) -> str:
    """Ruta acotada del manuscrito, con el proyecto que indica su metadato. Las pruebas la usan para preparar datos."""
    project = api.get(f"/manuscripts/{manuscript_id}").json()["project_id"]
    return f"/projects/{project}/manuscripts/{manuscript_id}"


def _draft(api: TestClient, manuscript_id: int) -> dict:
    """Borrador del manuscrito, creándolo si no existe (es lo que hace la interfaz al abrirlo)."""
    return api.post(_at(api, manuscript_id) + "/draft").json()["draft"]


def _snapshot(api: TestClient, manuscript_id: int) -> dict:
    """Estado observable de un manuscrito: borrador, versiones y puntos. Para comprobar que nada cambia."""
    draft = _draft(api, manuscript_id)
    versions = api.get(_at(api, manuscript_id) + "/versions").json()
    points = api.get(_at(api, manuscript_id) + "/recovery-points").json()
    return {
        "draft": (draft["content"], draft["revision"]),
        "versions": [(item["number"], item["sha256"]) for item in versions],
        "points": sorted(item["id"] for item in points),
    }


# ----------------------------------------------------------------------
# Negativas: identificadores válidos de otro proyecto
# ----------------------------------------------------------------------


@pytest.fixture
def two_novels(api: TestClient) -> dict:
    project_a = _project(api, "Novela A")
    project_b = _project(api, "Novela B")
    manuscript_a = _manuscript(api, project_a, "Manuscrito A")
    # Un punto de recuperación real en A: un guardado que cambia el texto.
    base = _draft(api, manuscript_a["id"])["revision"]
    api.put(_at(api, manuscript_a["id"]) + "/draft", json={"content": "Cambio en A", "base_revision": base, "keep_previous": False})
    return {"a": project_a, "b": project_b, "manuscript_a": manuscript_a["id"]}


def test_leer_un_manuscrito_de_otro_proyecto_por_ruta_acotada_responde_404(api: TestClient, two_novels: dict) -> None:
    m = two_novels["manuscript_a"]
    assert api.get(f"/projects/{two_novels['b']}/manuscripts/{m}").status_code == 404
    assert api.get(f"/projects/{two_novels['a']}/manuscripts/{m}").status_code == 200


def test_las_versiones_de_otro_proyecto_no_se_leen_ni_se_crean_por_ruta_acotada(api: TestClient, two_novels: dict) -> None:
    m = two_novels["manuscript_a"]
    version_id = api.get(_at(api, m) + "/versions").json()[0]["id"]
    before = _snapshot(api, m)
    assert api.get(f"/projects/{two_novels['b']}/manuscripts/{m}/versions").status_code == 404
    assert api.get(f"/projects/{two_novels['b']}/manuscripts/{m}/versions/{version_id}").status_code == 404
    created = api.post(
        f"/projects/{two_novels['b']}/manuscripts/{m}/versions",
        json={"content": "Intruso", "note": None, "based_on_version_id": None},
    )
    assert created.status_code == 404
    assert _snapshot(api, m) == before


def test_el_borrador_de_otro_proyecto_no_se_lee_ni_se_guarda_por_ruta_acotada(api: TestClient, two_novels: dict) -> None:
    m = two_novels["manuscript_a"]
    before = _snapshot(api, m)
    base = before["draft"][1]
    assert api.get(f"/projects/{two_novels['b']}/manuscripts/{m}/draft").status_code == 404
    assert api.post(f"/projects/{two_novels['b']}/manuscripts/{m}/draft").status_code == 404
    intruder = api.put(
        f"/projects/{two_novels['b']}/manuscripts/{m}/draft",
        json={"content": "Intruso", "base_revision": base, "keep_previous": False},
    )
    assert intruder.status_code == 404
    assert _snapshot(api, m) == before


def test_los_puntos_de_otro_proyecto_no_se_leen_ni_se_restauran_por_ruta_acotada(api: TestClient, two_novels: dict) -> None:
    m = two_novels["manuscript_a"]
    point_id = api.get(_at(api, m) + "/recovery-points").json()[0]["id"]
    before = _snapshot(api, m)
    assert api.get(f"/projects/{two_novels['b']}/manuscripts/{m}/recovery-points").status_code == 404
    assert api.get(f"/projects/{two_novels['b']}/manuscripts/{m}/recovery-points/{point_id}").status_code == 404
    restored = api.post(
        f"/projects/{two_novels['b']}/manuscripts/{m}/recovery-points/{point_id}/restore",
        json={"base_revision": before["draft"][1]},
    )
    assert restored.status_code == 404
    assert _snapshot(api, m) == before


def test_un_punto_de_otro_manuscrito_del_mismo_proyecto_no_se_restaura(api: TestClient) -> None:
    project = _project(api, "Mismo proyecto")
    first = _manuscript(api, project, "Primero")
    second = _manuscript(api, project, "Segundo")
    # Un guardado real en el primero crea un punto de recuperación.
    base_first = _draft(api, first["id"])["revision"]
    api.put(_at(api, first["id"]) + "/draft", json={"content": "Cambio del primero", "base_revision": base_first, "keep_previous": False})
    point_of_first = api.get(_at(api, first["id"]) + "/recovery-points").json()[0]["id"]
    before = _snapshot(api, second["id"])

    response = api.post(
        f"/projects/{project}/manuscripts/{second['id']}/recovery-points/{point_of_first}/restore",
        json={"base_revision": before["draft"][1]},
    )
    assert response.status_code == 404
    assert _snapshot(api, second["id"]) == before


def test_una_version_de_otro_manuscrito_del_mismo_proyecto_no_se_lee_por_su_ruta(api: TestClient) -> None:
    project = _project(api, "Versiones cruzadas")
    first = _manuscript(api, project, "Uno")
    second = _manuscript(api, project, "Dos")
    version_of_first = api.get(_at(api, first["id"]) + "/versions").json()[0]["id"]
    assert api.get(f"/projects/{project}/manuscripts/{second['id']}/versions/{version_of_first}").status_code == 404


def test_un_proyecto_archivado_no_admite_escrituras_acotadas_pero_si_lecturas(api: TestClient, two_novels: dict) -> None:
    m = two_novels["manuscript_a"]
    api.post(f"/projects/{two_novels['a']}/archive")
    before = _snapshot(api, m)
    assert api.get(f"/projects/{two_novels['a']}/manuscripts/{m}/draft").status_code == 200
    base = before["draft"][1]
    assert api.put(f"/projects/{two_novels['a']}/manuscripts/{m}/draft", json={"content": "x", "base_revision": base, "keep_previous": False}).status_code == 422
    assert api.post(f"/projects/{two_novels['a']}/manuscripts/{m}/versions", json={"content": "x", "note": None, "based_on_version_id": None}).status_code == 422
    assert _snapshot(api, m) == before


def test_proyecto_inexistente_responde_404_sin_tocar_nada(api: TestClient, two_novels: dict) -> None:
    m = two_novels["manuscript_a"]
    assert api.get(f"/projects/999999/manuscripts/{m}").status_code == 404
    assert api.post(f"/projects/999999/manuscripts/{m}/versions", json={"content": "x", "note": None, "based_on_version_id": None}).status_code == 404


def test_las_rutas_heredadas_no_atienden_manuscritos_de_proyecto(api: TestClient, two_novels: dict) -> None:
    """Un manuscrito con proyecto no se lee ni se escribe por la ruta heredada: 404 en lectura, 422 en escritura."""
    m = two_novels["manuscript_a"]
    before = _snapshot(api, m)
    assert api.get(f"/manuscripts/{m}/draft").status_code == 404
    assert api.get(f"/manuscripts/{m}/versions").status_code == 404
    assert api.get(f"/manuscripts/{m}/recovery-points").status_code == 404
    write = api.put(f"/manuscripts/{m}/draft", json={"content": "Por la ruta heredada", "base_revision": before["draft"][1], "keep_previous": False})
    assert write.status_code == 422
    assert _snapshot(api, m) == before


# ----------------------------------------------------------------------
# Escenas: la unión nunca da acceso a otro proyecto
# ----------------------------------------------------------------------


def test_una_escena_no_escribe_el_manuscrito_de_otro_proyecto(api: TestClient) -> None:
    project_a = _project(api, "Escena A")
    project_b = _project(api, "Escena B")
    scene_a = _scene(api, project_a, "Escena de A")
    scene_b = _scene(api, project_b, "Escena de B")
    api.post(f"/projects/{project_a}/planificacion/estructura/{scene_a['id']}/escritura")
    manuscript_a = api.get(f"/projects/{project_a}/planificacion/estructura/{scene_a['id']}/escritura").json()["manuscript_id"]
    before = _snapshot(api, manuscript_a)

    # Con la escena de B, la escritura de B nunca apunta al manuscrito de A.
    read_b = api.get(f"/projects/{project_b}/planificacion/estructura/{scene_b['id']}/escritura")
    assert read_b.json()["manuscript_id"] is None
    assert api.get(f"/projects/{project_b}/planificacion/estructura/{scene_a['id']}/escritura").status_code == 404
    assert api.put(
        f"/projects/{project_b}/planificacion/estructura/{scene_a['id']}/escritura/borrador",
        json={"content": "Intruso", "base_revision": 1, "keep_previous": False},
    ).status_code == 404
    assert _snapshot(api, manuscript_a) == before


def test_la_escritura_de_escena_no_se_puede_aplicar_sobre_su_manuscrito_por_ruta_heredada(api: TestClient) -> None:
    project_a = _project(api, "Heredada A")
    scene_a = _scene(api, project_a, "Heredada escena")
    api.post(f"/projects/{project_a}/planificacion/estructura/{scene_a['id']}/escritura")
    manuscript_a = api.get(f"/projects/{project_a}/planificacion/estructura/{scene_a['id']}/escritura").json()["manuscript_id"]
    before = _snapshot(api, manuscript_a)
    base = before["draft"][1]
    assert api.put(f"/manuscripts/{manuscript_a}/draft", json={"content": "x", "base_revision": base, "keep_previous": False}).status_code == 422
    assert api.post(f"/manuscripts/{manuscript_a}/versions", json={"content": "x", "note": None, "based_on_version_id": None}).status_code == 422
    assert _snapshot(api, manuscript_a) == before


# ----------------------------------------------------------------------
# Título: una sola fuente de verdad
# ----------------------------------------------------------------------


def test_el_titulo_de_un_manuscrito_de_escena_lo_marca_la_escena(api: TestClient) -> None:
    project = _project(api, "Título")
    scene = _scene(api, project, "Título de escena")
    api.post(f"/projects/{project}/planificacion/estructura/{scene['id']}/escritura")
    manuscript_id = api.get(f"/projects/{project}/planificacion/estructura/{scene['id']}/escritura").json()["manuscript_id"]
    summary = api.get(f"/projects/{project}/manuscripts/{manuscript_id}").json()
    assert summary["scene_node_id"] == scene["id"]
    assert summary["title"] == "Título de escena"


def test_renombrar_la_escena_actualiza_su_manuscrito_y_no_toca_los_independientes(api: TestClient) -> None:
    project = _project(api, "Renombrar título")
    ordinary = _manuscript(api, project, "Llegada")
    scene = _scene(api, project, "Llegada")
    api.post(f"/projects/{project}/planificacion/estructura/{scene['id']}/escritura")
    scene_manuscript = api.get(f"/projects/{project}/planificacion/estructura/{scene['id']}/escritura").json()["manuscript_id"]

    api.patch(f"/projects/{project}/planificacion/estructura/{scene['id']}", json={"title": "Nueva llegada"})
    assert api.get(f"/manuscripts/{scene_manuscript}").json()["title"] == "Nueva llegada"
    assert api.get(f"/manuscripts/{ordinary['id']}").json()["title"] == "Llegada"
    assert api.get(f"/manuscripts/{ordinary['id']}").json()["scene_node_id"] is None


def test_no_existe_ninguna_via_para_cambiar_el_titulo_de_un_manuscrito(api: TestClient) -> None:
    """Regla: el título de un manuscrito lo fija su creación o, si es de escena, la escena. Ninguna ruta lo edita."""
    project = _project(api, "Sin edición")
    manuscript = _manuscript(api, project, "Fijo")
    scene = _scene(api, project, "Escena fija")
    api.post(f"/projects/{project}/planificacion/estructura/{scene['id']}/escritura")
    scene_manuscript = api.get(f"/projects/{project}/planificacion/estructura/{scene['id']}/escritura").json()["manuscript_id"]
    for target in (f"/manuscripts/{manuscript['id']}", f"/projects/{project}/manuscripts/{manuscript['id']}", f"/manuscripts/{scene_manuscript}"):
        assert api.patch(target, json={"title": "Otro"}).status_code in (404, 405)
        assert api.put(target, json={"title": "Otro"}).status_code in (404, 405)
    assert api.get(f"/manuscripts/{scene_manuscript}").json()["title"] == "Escena fija"


def test_si_la_sincronizacion_falla_el_renombrado_no_deja_titulos_contradictorios(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _project(api, "Atomicidad título")
    scene = _scene(api, project, "Antes")
    api.post(f"/projects/{project}/planificacion/estructura/{scene['id']}/escritura")
    manuscript_id = api.get(f"/projects/{project}/planificacion/estructura/{scene['id']}/escritura").json()["manuscript_id"]

    import app.planning.service as planning_service

    def failing_sync(session, node_id, title):  # type: ignore[no-untyped-def]
        raise RuntimeError("fallo simulado en la sincronización")

    monkeypatch.setattr(planning_service, "sync_title", failing_sync)
    with pytest.raises(RuntimeError):
        api.patch(f"/projects/{project}/planificacion/estructura/{scene['id']}", json={"title": "Después"})
    monkeypatch.undo()
    assert api.get(f"/projects/{project}/planificacion/estructura/{scene['id']}").json()["title"] == "Antes"
    assert api.get(f"/manuscripts/{manuscript_id}").json()["title"] == "Antes"


# ----------------------------------------------------------------------
# Integridad: archivar, restaurar y no borrar
# ----------------------------------------------------------------------


def test_archivar_y_restaurar_una_escena_o_un_proyecto_conserva_la_union_y_el_texto(api: TestClient) -> None:
    project = _project(api, "Archivado conserva")
    scene = _scene(api, project, "Conservada")
    api.post(f"/projects/{project}/planificacion/estructura/{scene['id']}/escritura")
    manuscript_id = api.get(f"/projects/{project}/planificacion/estructura/{scene['id']}/escritura").json()["manuscript_id"]
    base = _draft(api, manuscript_id)["revision"]
    api.put(f"/projects/{project}/planificacion/estructura/{scene['id']}/escritura/borrador", json={"content": "Texto", "base_revision": base, "keep_previous": False})
    before = _snapshot(api, manuscript_id)

    api.post(f"/projects/{project}/planificacion/estructura/{scene['id']}/archivar")
    assert api.get(f"/projects/{project}/planificacion/estructura/{scene['id']}/escritura").json()["manuscript_id"] == manuscript_id
    api.post(f"/projects/{project}/archive")
    api.post(f"/projects/{project}/restore")
    assert api.get(f"/projects/{project}/planificacion/estructura/{scene['id']}/escritura").json()["manuscript_id"] == manuscript_id
    assert _snapshot(api, manuscript_id) == before


def test_no_hay_rutas_de_borrado_sobre_manuscritos_versiones_borradores_ni_puntos(api: TestClient) -> None:
    deletes = {route.path for route in api.app.routes if "DELETE" in getattr(route, "methods", set())}
    assert not [path for path in deletes if any(word in path for word in ("manuscript", "version", "draft", "recovery", "escritura"))]


def test_la_base_no_permite_borrar_manuscritos_con_versiones_ni_escenas_con_manuscrito(api: TestClient, client: TestClient) -> None:
    project = _project(api, "FK")
    manuscript = _manuscript(api, project, "Con versiones")
    scene = _scene(api, project, "Con escritura")
    api.post(f"/projects/{project}/planificacion/estructura/{scene['id']}/escritura")
    session = client.app.state.session_factory()
    try:
        with pytest.raises(IntegrityError):
            session.execute(text("DELETE FROM manuscripts WHERE id = :id"), {"id": manuscript["id"]})
        session.rollback()
        with pytest.raises(IntegrityError):
            session.execute(text("DELETE FROM structure_nodes WHERE id = :id"), {"id": scene["id"]})
        session.rollback()
    finally:
        session.close()
    assert api.get(f"/manuscripts/{manuscript['id']}").status_code == 200
    assert api.get(f"/projects/{project}/planificacion/estructura/{scene['id']}/escritura").status_code == 200


# ----------------------------------------------------------------------
# Conservación: conflictos de guardado y restauración por la ruta acotada
# ----------------------------------------------------------------------


def test_un_guardado_con_revision_antigua_por_la_ruta_acotada_da_409_y_conserva_ambos_textos(api: TestClient) -> None:
    project = _project(api, "Conflicto acotado")
    manuscript = _manuscript(api, project, "Conflicto")
    base = _draft(api, manuscript["id"])["revision"]
    first = api.put(
        f"/projects/{project}/manuscripts/{manuscript['id']}/draft",
        json={"content": "Ventana A", "base_revision": base, "keep_previous": False},
    )
    assert first.status_code == 200
    stale = api.put(
        f"/projects/{project}/manuscripts/{manuscript['id']}/draft",
        json={"content": "Ventana B", "base_revision": base, "keep_previous": False},
    )
    assert stale.status_code == 409
    assert stale.json()["current_content"] == "Ventana A"
    points = api.get(f"/projects/{project}/manuscripts/{manuscript['id']}/recovery-points").json()
    conflict = [item for item in points if item["reason"] == "conflicto"]
    assert len(conflict) == 1
    kept = api.get(f"/projects/{project}/manuscripts/{manuscript['id']}/recovery-points/{conflict[0]['id']}").json()
    assert kept["content"] == "Ventana B"
    assert _draft(api, manuscript["id"])["content"] == "Ventana A"


def test_restaurar_por_la_ruta_acotada_guarda_antes_el_estado_actual(api: TestClient) -> None:
    project = _project(api, "Restaurar acotado")
    manuscript = _manuscript(api, project, "Restaurar")
    base = _draft(api, manuscript["id"])["revision"]
    api.put(f"/projects/{project}/manuscripts/{manuscript['id']}/draft", json={"content": "Antes", "base_revision": base, "keep_previous": False})
    point = api.get(f"/projects/{project}/manuscripts/{manuscript['id']}/recovery-points").json()[0]
    current = _draft(api, manuscript["id"])
    restored = api.post(
        f"/projects/{project}/manuscripts/{manuscript['id']}/recovery-points/{point['id']}/restore",
        json={"base_revision": current["revision"]},
    )
    assert restored.status_code == 200
    reasons = [item["reason"] for item in api.get(f"/projects/{project}/manuscripts/{manuscript['id']}/recovery-points").json()]
    assert "antes_de_restaurar" in reasons
    versions_after = api.get(f"/projects/{project}/manuscripts/{manuscript['id']}/versions").json()
    assert [item["number"] for item in versions_after] == [1]
