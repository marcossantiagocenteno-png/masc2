"""Planificación narrativa: modelo, relaciones, canon, aislamiento, atomicidad y persistencia.

Todas las pruebas usan la API real sobre una base migrada. El reloj es controlado.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.backups.service import BackupService
from app.backups.verify import schema_order, verify_sqlite
from app.config import Settings
from tests.backup_fakes import FakeClock


@pytest.fixture
def api(client: TestClient, clock: FakeClock) -> TestClient:
    client.app.state.clock = clock
    return client


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def _project(api: TestClient, name: str = "Novela") -> int:
    response = api.post("/projects", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _url(project_id: int, path: str = "") -> str:
    return f"/projects/{project_id}/planificacion{path}"


def _create(api: TestClient, project_id: int, route: str, body: dict) -> dict:
    response = api.post(_url(project_id, f"/{route}"), json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _scene(api: TestClient, project_id: int, title: str, parent_id: int | None = None) -> dict:
    response = api.post(_url(project_id, "/estructura"), json={"kind": "escena", "parent_id": parent_id, "title": title})
    assert response.status_code == 201, response.text
    return response.json()


# ----------------------------------------------------------------------
# Planificación incompleta
# ----------------------------------------------------------------------


def test_crear_una_planificacion_incompleta_es_valido(api: TestClient) -> None:
    project_id = _project(api)
    narrative = api.patch(_url(project_id, "/narrativa"), json={"premise": "Una idea a medias."})
    assert narrative.status_code == 200
    assert narrative.json()["premise"] == "Una idea a medias."
    assert narrative.json()["synopsis"] is None

    character = _create(api, project_id, "personajes", {"name": "Sin descripción todavía"})
    assert character["description"] is None
    assert character["estado"] == "provisional"
    assert character["origen"] == "autor"

    scene = _scene(api, project_id, "Escena sin prosa")
    assert scene["kind"] == "escena" and scene["summary"] is None


# ----------------------------------------------------------------------
# Crear y modificar
# ----------------------------------------------------------------------


def test_crear_y_modificar_personajes_lugares_acontecimientos_y_escenas(api: TestClient) -> None:
    project_id = _project(api)
    character = _create(api, project_id, "personajes", {"name": "Ana", "goals": "Recuperar la casa"})
    place = _create(api, project_id, "lugares", {"name": "La casa", "features": "Tres plantas"})
    event = _create(api, project_id, "acontecimientos", {"title": "La boda", "narrative_order": 3, "story_time": "hace diez años"})
    plot = _create(api, project_id, "elementos-trama", {"kind": "misterio", "title": "La carta"})
    scene = _scene(api, project_id, "Escena inicial")

    edited = api.patch(_url(project_id, f"/personajes/{character['id']}"), json={"motivations": "Culpa"})
    assert edited.status_code == 200
    assert edited.json()["motivations"] == "Culpa" and edited.json()["goals"] == "Recuperar la casa"

    assert api.patch(_url(project_id, f"/lugares/{place['id']}"), json={"notes": "Se vende"}).json()["notes"] == "Se vende"
    assert api.patch(_url(project_id, f"/acontecimientos/{event['id']}"), json={"narrative_order": 1}).json()["narrative_order"] == 1
    assert api.patch(_url(project_id, f"/elementos-trama/{plot['id']}"), json={"kind": "conflicto"}).json()["kind"] == "conflicto"
    assert api.patch(_url(project_id, f"/estructura/{scene['id']}"), json={"summary": "Llega Ana"}).json()["summary"] == "Llega Ana"


def test_un_tipo_de_trama_no_valido_se_rechaza(api: TestClient) -> None:
    project_id = _project(api)
    response = api.post(_url(project_id, "/elementos-trama"), json={"kind": "romance_inventado", "title": "x"})
    assert response.status_code == 422


# ----------------------------------------------------------------------
# Relaciones
# ----------------------------------------------------------------------


def test_las_relaciones_se_crean_y_se_consultan_desde_la_escena(api: TestClient) -> None:
    project_id = _project(api)
    ana = _create(api, project_id, "personajes", {"name": "Ana"})
    casa = _create(api, project_id, "lugares", {"name": "La casa"})
    scene = _scene(api, project_id, "Llegada")

    api.post(_url(project_id, "/vinculos"), json={
        "origen": {"tipo": "personaje", "id": ana["id"]},
        "destino": {"tipo": "escena", "id": scene["id"]},
        "relacion": "participa_en",
    })
    api.post(_url(project_id, "/vinculos"), json={
        "origen": {"tipo": "lugar", "id": casa["id"]},
        "destino": {"tipo": "escena", "id": scene["id"]},
        "relacion": "ocurre_en",
    })

    links = api.get(_url(project_id, f"/estructura/{scene['id']}/vinculos")).json()
    assert {(link["source_kind"], link["relation"]) for link in links} == {("personaje", "participa_en"), ("lugar", "ocurre_en")}
    assert api.get(_url(project_id, f"/personajes/{ana['id']}/vinculos")).json()[0]["target_kind"] == "escena"


def test_una_relacion_no_permitida_se_rechaza_sin_crear_nada(api: TestClient) -> None:
    project_id = _project(api)
    lugar = _create(api, project_id, "lugares", {"name": "Lugar"})
    lugar_b = _create(api, project_id, "lugares", {"name": "Otro lugar"})
    response = api.post(_url(project_id, "/vinculos"), json={
        "origen": {"tipo": "lugar", "id": lugar["id"]},
        "destino": {"tipo": "lugar", "id": lugar_b["id"]},
        "relacion": "ocurre_en",
    })
    assert response.status_code == 422
    assert api.get(_url(project_id, "/vinculos")).json() == []


def test_un_vinculo_duplicado_se_rechaza(api: TestClient) -> None:
    project_id = _project(api)
    ana = _create(api, project_id, "personajes", {"name": "Ana"})
    scene = _scene(api, project_id, "Escena")
    body = {"origen": {"tipo": "personaje", "id": ana["id"]}, "destino": {"tipo": "escena", "id": scene["id"]}, "relacion": "participa_en"}
    assert api.post(_url(project_id, "/vinculos"), json=body).status_code == 201
    assert api.post(_url(project_id, "/vinculos"), json=body).status_code == 409
    assert len(api.get(_url(project_id, "/vinculos")).json()) == 1


def test_una_escena_no_se_vincula_si_el_nodo_es_un_capitulo(api: TestClient) -> None:
    project_id = _project(api)
    ana = _create(api, project_id, "personajes", {"name": "Ana"})
    chapter = api.post(_url(project_id, "/estructura"), json={"kind": "capitulo", "title": "Capítulo 1"}).json()
    response = api.post(_url(project_id, "/vinculos"), json={
        "origen": {"tipo": "personaje", "id": ana["id"]},
        "destino": {"tipo": "escena", "id": chapter["id"]},
        "relacion": "participa_en",
    })
    assert response.status_code == 422


# ----------------------------------------------------------------------
# Estructura y reordenación
# ----------------------------------------------------------------------


def test_reordenar_escenas_no_cambia_su_identidad(api: TestClient) -> None:
    project_id = _project(api)
    chapter = api.post(_url(project_id, "/estructura"), json={"kind": "capitulo", "title": "Cap."}).json()
    first = _scene(api, project_id, "A", chapter["id"])
    second = _scene(api, project_id, "B", chapter["id"])
    third = _scene(api, project_id, "C", chapter["id"])

    response = api.post(_url(project_id, "/estructura/reordenar"), json={
        "parent_id": chapter["id"],
        "orden": [third["id"], first["id"], second["id"]],
    })
    assert response.status_code == 200
    reordered = response.json()
    assert [node["id"] for node in reordered] == [third["id"], first["id"], second["id"]]
    assert [node["position"] for node in reordered] == [0, 1, 2]
    assert [node["title"] for node in reordered] == ["C", "A", "B"]

    # El nodo conserva su id, su título y su relación con el padre.
    fetched = api.get(_url(project_id, f"/estructura/{first['id']}")).json()
    assert fetched["title"] == "A" and fetched["parent_id"] == chapter["id"] and fetched["position"] == 1


def test_una_jerarquia_invalida_se_rechaza(api: TestClient) -> None:
    project_id = _project(api)
    chapter = api.post(_url(project_id, "/estructura"), json={"kind": "capitulo"}).json()
    # Un capítulo no puede colgar de un capítulo, ni un acto de nada.
    assert api.post(_url(project_id, "/estructura"), json={"kind": "capitulo", "parent_id": chapter["id"]}).status_code == 422
    assert api.post(_url(project_id, "/estructura"), json={"kind": "acto", "parent_id": chapter["id"]}).status_code == 422


def test_reordenar_con_una_lista_incompleta_no_cambia_nada(api: TestClient) -> None:
    project_id = _project(api)
    first = _scene(api, project_id, "A")
    second = _scene(api, project_id, "B")
    before = api.get(_url(project_id, "/estructura")).json()
    response = api.post(_url(project_id, "/estructura/reordenar"), json={"orden": [second["id"]]})
    assert response.status_code == 422
    assert api.get(_url(project_id, "/estructura")).json() == before
    assert before[0]["id"] == first["id"]


# ----------------------------------------------------------------------
# Canon: propuestas, provisionales y canónicos
# ----------------------------------------------------------------------


def test_se_distinguen_propuestas_provisionales_y_canonicos(api: TestClient) -> None:
    project_id = _project(api)
    _create(api, project_id, "personajes", {"name": "Provisional"})
    api.post(_url(project_id, "/personajes/propuestas"), json={"name": "Propuesta"})
    canonical = _create(api, project_id, "personajes", {"name": "Canónica"})
    assert api.post(_url(project_id, f"/personajes/{canonical['id']}/aprobar"), json={"confirmar": True}).status_code == 200

    by_state = {
        estado: [c["name"] for c in api.get(_url(project_id, "/personajes"), params={"estado": estado}).json()]
        for estado in ("provisional", "propuesta_ia", "canonico")
    }
    assert by_state == {"provisional": ["Provisional"], "propuesta_ia": ["Propuesta"], "canonico": ["Canónica"]}
    proposal = api.get(_url(project_id, "/personajes"), params={"estado": "propuesta_ia"}).json()[0]
    assert proposal["origen"] == "ia"


def test_una_propuesta_no_se_convierte_en_canon_sin_aprobacion_explicita(api: TestClient) -> None:
    project_id = _project(api)
    proposal = api.post(_url(project_id, "/lugares/propuestas"), json={"name": "Propuesto por la IA"}).json()
    sin_confirmar = api.post(_url(project_id, f"/lugares/{proposal['id']}/aprobar"), json={"confirmar": False})
    assert sin_confirmar.status_code == 422

    current = api.get(_url(project_id, f"/lugares/{proposal['id']}")).json()
    assert current["estado"] == "propuesta_ia"
    assert current["approved_decision_id"] is None
    assert api.get(_url(project_id, f"/lugares/{proposal['id']}/decisiones")).json() == []


def test_editar_una_propuesta_no_la_convierte_en_canon(api: TestClient) -> None:
    project_id = _project(api)
    proposal = api.post(_url(project_id, "/lugares/propuestas"), json={"name": "Propuesta"}).json()
    edited = api.patch(_url(project_id, f"/lugares/{proposal['id']}"), json={"features": "Mucho detalle"}).json()
    assert edited["estado"] == "propuesta_ia"


def test_no_se_puede_forzar_el_estado_desde_la_edicion(api: TestClient) -> None:
    project_id = _project(api)
    proposal = api.post(_url(project_id, "/lugares/propuestas"), json={"name": "Propuesta"}).json()
    response = api.patch(_url(project_id, f"/lugares/{proposal['id']}"), json={"estado": "canonico"})
    assert response.status_code == 422
    assert api.get(_url(project_id, f"/lugares/{proposal['id']}")).json()["estado"] == "propuesta_ia"


def test_aceptar_una_propuesta_la_deja_como_provisional_no_canon(api: TestClient) -> None:
    project_id = _project(api)
    proposal = api.post(_url(project_id, "/lugares/propuestas"), json={"name": "Propuesta"}).json()
    accepted = api.post(_url(project_id, f"/lugares/{proposal['id']}/aceptar-propuesta")).json()
    assert accepted["estado"] == "provisional"
    assert accepted["origen"] == "ia"  # la procedencia no se borra
    assert accepted["approved_decision_id"] is None


def test_modificar_un_canonico_exige_confirmacion_y_no_cambia_nada_sin_ella(api: TestClient) -> None:
    project_id = _project(api)
    character = _create(api, project_id, "personajes", {"name": "Ana", "motivations": "Original"})
    api.post(_url(project_id, f"/personajes/{character['id']}/aprobar"), json={"confirmar": True})

    response = api.patch(_url(project_id, f"/personajes/{character['id']}"), json={"motivations": "Silencioso"})
    assert response.status_code == 409
    current = api.get(_url(project_id, f"/personajes/{character['id']}")).json()
    assert current["motivations"] == "Original"
    assert current["estado"] == "canonico"


def test_modificar_un_canonico_con_confirmacion_lo_devuelve_a_provisional_y_registra_la_decision(api: TestClient) -> None:
    project_id = _project(api)
    character = _create(api, project_id, "personajes", {"name": "Ana", "motivations": "Original"})
    approval = api.post(_url(project_id, f"/personajes/{character['id']}/aprobar"), json={"confirmar": True, "nota": "Cerrado"}).json()
    decision_id = approval["approved_decision_id"]
    assert decision_id is not None

    edited = api.patch(
        _url(project_id, f"/personajes/{character['id']}"),
        params={"confirmar_cambio_canon": True},
        json={"motivations": "Cambiada"},
    ).json()
    assert edited["estado"] == "provisional"
    assert edited["approved_decision_id"] is None

    decisions = api.get(_url(project_id, f"/personajes/{character['id']}/decisiones")).json()
    assert [d["accion"] for d in decisions] == ["aprobar_canon", "modificar_canon"]
    assert decisions[0]["id"] == decision_id
    assert '"motivations": "Original"' in decisions[1]["snapshot"]  # la instantánea conserva lo anterior
    assert decisions[1]["estado_previo"] == "canonico" and decisions[1]["estado_nuevo"] == "provisional"


def test_archivar_un_canonico_exige_confirmacion(api: TestClient) -> None:
    project_id = _project(api)
    character = _create(api, project_id, "personajes", {"name": "Ana"})
    api.post(_url(project_id, f"/personajes/{character['id']}/aprobar"), json={"confirmar": True})
    assert api.post(_url(project_id, f"/personajes/{character['id']}/archivar")).status_code == 409
    assert api.get(_url(project_id, f"/personajes/{character['id']}")).json()["archived_at"] is None


def test_un_elemento_archivado_no_se_lista_ni_se_edita_pero_sigue_existiendo(api: TestClient) -> None:
    project_id = _project(api)
    place = _create(api, project_id, "lugares", {"name": "Viejo"})
    assert api.post(_url(project_id, f"/lugares/{place['id']}/archivar")).status_code == 200
    assert api.get(_url(project_id, "/lugares")).json() == []
    assert [p["id"] for p in api.get(_url(project_id, "/lugares"), params={"include_archived": True}).json()] == [place["id"]]
    assert api.get(_url(project_id, f"/lugares/{place['id']}")).json()["archived_at"] is not None
    assert api.patch(_url(project_id, f"/lugares/{place['id']}"), json={"name": "Nuevo"}).status_code == 422


def test_las_decisiones_no_se_pueden_modificar_ni_borrar(settings: Settings, api: TestClient) -> None:
    project_id = _project(api)
    character = _create(api, project_id, "personajes", {"name": "Ana"})
    api.post(_url(project_id, f"/personajes/{character['id']}/aprobar"), json={"confirmar": True})
    path = Path(settings.database_url.removeprefix("sqlite:///"))
    with closing(sqlite3.connect(path)) as connection:
        with pytest.raises(sqlite3.DatabaseError, match="inmutable"):
            connection.execute("UPDATE narrative_decisions SET nota = 'alterada'")
        with pytest.raises(sqlite3.DatabaseError, match="inmutable"):
            connection.execute("DELETE FROM narrative_decisions")


# ----------------------------------------------------------------------
# Aislamiento entre proyectos
# ----------------------------------------------------------------------


def test_no_se_puede_vincular_entidades_de_proyectos_distintos(api: TestClient) -> None:
    first = _project(api, "Primera")
    second = _project(api, "Segunda")
    ana = _create(api, first, "personajes", {"name": "Ana"})
    scene_b = _scene(api, second, "Escena de otra novela")

    response = api.post(_url(first, "/vinculos"), json={
        "origen": {"tipo": "personaje", "id": ana["id"]},
        "destino": {"tipo": "escena", "id": scene_b["id"]},
        "relacion": "participa_en",
    })
    # Para la novela de origen, la escena de otra novela no existe: 404, sin revelar nada de ella.
    assert response.status_code == 404
    assert api.get(_url(first, "/vinculos")).json() == []
    assert api.get(_url(second, "/vinculos")).json() == []


def test_un_id_de_otro_proyecto_no_se_consulta_ni_se_edita(api: TestClient) -> None:
    first = _project(api, "Primera")
    second = _project(api, "Segunda")
    ana = _create(api, first, "personajes", {"name": "Ana"})
    assert api.get(_url(second, f"/personajes/{ana['id']}")).status_code == 404
    assert api.patch(_url(second, f"/personajes/{ana['id']}"), json={"name": "Robada"}).status_code == 404
    assert api.get(_url(first, f"/personajes/{ana['id']}")).json()["name"] == "Ana"


def test_las_listas_de_un_proyecto_no_muestran_elementos_de_otro(api: TestClient) -> None:
    first = _project(api, "Primera")
    second = _project(api, "Segunda")
    _create(api, first, "personajes", {"name": "Solo de la primera"})
    _create(api, second, "lugares", {"name": "Solo de la segunda"})
    assert [c["name"] for c in api.get(_url(first, "/personajes")).json()] == ["Solo de la primera"]
    assert api.get(_url(first, "/lugares")).json() == []
    assert api.get(_url(second, "/personajes")).json() == []


def test_el_reordenado_no_mezcla_hermanos_de_otro_proyecto(api: TestClient) -> None:
    first = _project(api, "Primera")
    second = _project(api, "Segunda")
    mine = _scene(api, first, "Mía")
    foreign = _scene(api, second, "Ajena")
    response = api.post(_url(first, "/estructura/reordenar"), json={"orden": [mine["id"], foreign["id"]]})
    assert response.status_code == 422
    assert api.get(_url(second, f"/estructura/{foreign['id']}")).json()["position"] == 0


# ----------------------------------------------------------------------
# Atomicidad: un fallo no deja cambios parciales
# ----------------------------------------------------------------------


def test_una_edicion_con_un_campo_invalido_no_cambia_ningun_campo(api: TestClient) -> None:
    project_id = _project(api)
    character = _create(api, project_id, "personajes", {"name": "Original", "goals": "Antes"})
    response = api.patch(_url(project_id, f"/personajes/{character['id']}"), json={"name": "Nuevo", "narrative_order": 9})
    assert response.status_code == 422
    current = api.get(_url(project_id, f"/personajes/{character['id']}")).json()
    assert current["name"] == "Original" and current["goals"] == "Antes"


def test_un_vinculo_con_destino_inexistente_no_deja_registros(api: TestClient) -> None:
    project_id = _project(api)
    ana = _create(api, project_id, "personajes", {"name": "Ana"})
    response = api.post(_url(project_id, "/vinculos"), json={
        "origen": {"tipo": "personaje", "id": ana["id"]},
        "destino": {"tipo": "escena", "id": 999999},
        "relacion": "participa_en",
    })
    assert response.status_code == 404
    assert api.get(_url(project_id, "/vinculos")).json() == []
    assert api.get(_url(project_id, f"/personajes/{ana['id']}/decisiones")).json() == []


def test_aprobar_sin_confirmacion_no_registra_decision_ni_cambia_el_estado(api: TestClient) -> None:
    project_id = _project(api)
    place = _create(api, project_id, "lugares", {"name": "Lugar"})
    assert api.post(_url(project_id, f"/lugares/{place['id']}/aprobar"), json={"confirmar": False}).status_code == 422
    assert api.get(_url(project_id, f"/lugares/{place['id']}")).json()["estado"] == "provisional"
    assert api.get(_url(project_id, f"/lugares/{place['id']}/decisiones")).json() == []


# ----------------------------------------------------------------------
# Archivado de proyecto y persistencia
# ----------------------------------------------------------------------


def test_un_proyecto_archivado_admite_lectura_pero_no_cambios_de_planificacion(api: TestClient) -> None:
    project_id = _project(api)
    character = _create(api, project_id, "personajes", {"name": "Ana"})
    assert api.post(f"/projects/{project_id}/archive").status_code == 200
    assert api.get(_url(project_id, f"/personajes/{character['id']}")).status_code == 200
    assert api.post(_url(project_id, "/lugares"), json={"name": "Nuevo"}).status_code == 422
    assert api.patch(_url(project_id, "/narrativa"), json={"premise": "x"}).status_code == 422


def test_la_planificacion_no_toca_manuscritos_versiones_ni_borradores(api: TestClient, service) -> None:  # type: ignore[no-untyped-def]
    project_id = _project(api)
    manuscript = api.post("/manuscripts", json={"title": "Texto", "content": "Versión formal."}).json()
    api.post(f"/manuscripts/{manuscript['id']}/draft")
    api.put(f"/manuscripts/{manuscript['id']}/draft", json={"content": "Borrador.", "base_revision": 1})
    versions_before = api.get(f"/manuscripts/{manuscript['id']}/versions").json()
    draft_before = api.get(f"/manuscripts/{manuscript['id']}/draft").json()

    character = _create(api, project_id, "personajes", {"name": "Ana"})
    scene = _scene(api, project_id, "Escena")
    api.post(_url(project_id, "/vinculos"), json={
        "origen": {"tipo": "personaje", "id": character["id"]},
        "destino": {"tipo": "escena", "id": scene["id"]},
        "relacion": "participa_en",
    })
    api.post(_url(project_id, f"/personajes/{character['id']}/aprobar"), json={"confirmar": True})

    assert api.get(f"/manuscripts/{manuscript['id']}/versions").json() == versions_before
    assert api.get(f"/manuscripts/{manuscript['id']}/draft").json() == draft_before
    # El autoguardado sigue funcionando después de la planificación.
    saved = api.put(f"/manuscripts/{manuscript['id']}/draft", json={"content": "Borrador tras planificar.", "base_revision": draft_before["revision"]})
    assert saved.status_code == 200


def test_una_copia_tras_planificar_se_verifica_con_las_tablas_nuevas(api: TestClient, settings: Settings, tmp_path: Path, clock: FakeClock) -> None:
    project_id = _project(api)
    _create(api, project_id, "personajes", {"name": "Ana"})
    live = Path(settings.database_url.removeprefix("sqlite:///"))
    outcome = BackupService(source=live, directory=tmp_path / "copias", clock=clock, keep=5, min_keep=1, max_age=timedelta(days=30)).run()
    assert outcome.status == "creada", outcome.message
    verification = verify_sqlite(outcome.path, schema_order())  # type: ignore[arg-type]
    assert verification.ok
    assert verification.counts["characters"] == 1
