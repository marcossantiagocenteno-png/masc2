"""Recomendaciones de estructura (F2): ranking, explicaciones, propuestas de etapas y ausencia de cambios en el canon.

Las pruebas usan solo la API. Cada operación que escribe se compara con el estado anterior de la premisa, los géneros,
las directrices, los personajes, los manuscritos y las decisiones, para demostrar que no cambian nada del canon.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.planning import recomendaciones as RC

PREMISA = "Una archivista descubre que los registros de su ciudad fueron alterados por alguien de dentro."


@pytest.fixture
def api(client: TestClient) -> TestClient:
    return client


def _project(api: TestClient, name: str = "Novela") -> int:
    response = api.post("/projects", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _url(project_id: int, path: str = "") -> str:
    return f"/projects/{project_id}/planificacion{path}"


def _premisa(api: TestClient, project_id: int, premisa: str | None = PREMISA) -> None:
    response = api.patch(_url(project_id, "/narrativa"), json={"premise": premisa})
    assert response.status_code == 200, response.text


def _directrices(api: TestClient, project_id: int, **valores: str) -> None:
    campos = {"voz": None, "persona": None, "tiempo_verbal": None, "tipo_narrador": None,
              "punto_de_vista": None, "focalizacion": None, "estilo": None, "intencion": None,
              "limites": None, "instrucciones": None}
    response = api.put(_url(project_id, "/directrices"), json=campos | valores)
    assert response.status_code == 200, response.text


def _generos(api: TestClient, project_id: int, *claves: str) -> None:
    response = api.put(_url(project_id, "/generos"), json={"generos": [{"key": clave} for clave in claves]})
    assert response.status_code == 200, response.text


def _ranking(api: TestClient, project_id: int) -> dict:
    response = api.get(_url(project_id, "/estructura-recomendada"))
    assert response.status_code == 200, response.text
    return response.json()


def _claves(data: dict) -> list[str]:
    return [item["clave"] for item in data["ranking"]]


def _elegir(api: TestClient, project_id: int, clave: str) -> None:
    response = api.put(_url(project_id, "/estructura-recomendada/modelo"), json={"model_key": clave})
    assert response.status_code == 200, response.text


def _generar(api: TestClient, project_id: int, clave: str | None = None) -> list[dict]:
    body = {} if clave is None else {"model_key": clave}
    response = api.post(_url(project_id, "/estructura-recomendada/propuestas"), json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _estado_del_canon(api: TestClient, project_id: int) -> dict:
    """Todo lo que una operación de F2 no debe cambiar: premisa, géneros, directrices, personajes y manuscritos."""
    return {
        "narrativa": api.get(_url(project_id, "/narrativa")).json(),
        "directrices": api.get(_url(project_id, "/directrices")).json(),
        "personajes": api.get(_url(project_id, "/personajes")).json(),
        "manuscritos": api.get(f"/projects/{project_id}/manuscripts").json(),
    }


# ---------------------------------------------------------------------------------------------
# Ranking y explicaciones
# ---------------------------------------------------------------------------------------------


def test_sin_datos_los_tres_modelos_empatan_y_se_mantiene_el_orden_del_catalogo(api: TestClient) -> None:
    project_id = _project(api)
    data = _ranking(api, project_id)
    assert _claves(data) == ["freytag", "siete_puntos", "save_the_cat"]
    assert all(item["puntaje"] == 0 for item in data["ranking"])
    assert all(
        "Tus datos no distinguen" in razon["texto"] for item in data["ranking"] for razon in item["razones"]
    )
    assert all("orden de referencia" in item["motivo_de_posicion"] for item in data["ranking"])
    assert data["modelo_elegido"] is None
    assert data["propuestas"] == []


def test_el_ranking_es_determinista(api: TestClient) -> None:
    project_id = _project(api)
    _premisa(api, project_id)
    _directrices(api, project_id, punto_de_vista="un_personaje")
    assert _ranking(api, project_id)["ranking"] == _ranking(api, project_id)["ranking"]


def test_un_solo_personaje_pone_siete_puntos_primero_con_su_motivo_confirmado(api: TestClient) -> None:
    project_id = _project(api)
    _premisa(api, project_id)
    _directrices(api, project_id, punto_de_vista="un_personaje")
    data = _ranking(api, project_id)
    assert _claves(data)[0] == "siete_puntos"
    primero = data["ranking"][0]
    assert primero["puntaje"] == 2
    assert primero["razones"][0]["tipo"] == RC.TIPO_INFERENCIA
    assert primero["razones"][0]["regla"] == "un_personaje"
    assert "un solo personaje" in primero["razones"][0]["texto"]
    assert primero["motivo_de_posicion"].startswith("Primera por")


def test_varios_personajes_pone_freytag_primero(api: TestClient) -> None:
    project_id = _project(api)
    _premisa(api, project_id)
    _directrices(api, project_id, punto_de_vista="varios_personajes")
    data = _ranking(api, project_id)
    assert _claves(data)[0] == "freytag"
    assert data["ranking"][0]["razones"][0]["regla"] == "varios_personajes"


def test_el_genero_de_misterio_suma_como_convencion_y_se_marca_como_tal(api: TestClient) -> None:
    project_id = _project(api)
    _premisa(api, project_id)
    _generos(api, project_id, "misterio")
    data = _ranking(api, project_id)
    siete = next(item for item in data["ranking"] if item["clave"] == "siete_puntos")
    assert siete["razones"][0]["tipo"] == RC.TIPO_CONVENCION
    assert "no una exigencia" in siete["razones"][0]["texto"]


def test_la_tragedia_suma_a_freytag_como_convencion_historica(api: TestClient) -> None:
    project_id = _project(api)
    _generos(api, project_id, "tragedia")
    data = _ranking(api, project_id)
    freytag = next(item for item in data["ranking"] if item["clave"] == "freytag")
    assert freytag["razones"][0]["tipo"] == RC.TIPO_CONVENCION
    assert freytag["razones"][0]["regla"] == "genero_tragedia"


def test_un_genero_sin_directrices_no_cambia_el_orden_de_los_modelos_con_puntaje_cero(api: TestClient) -> None:
    project_id = _project(api)
    _generos(api, project_id, "fantasia")
    assert _claves(_ranking(api, project_id)) == ["freytag", "siete_puntos", "save_the_cat"]


def test_cada_modelo_explica_pertinencia_favorece_y_limitaciones(api: TestClient) -> None:
    data = _ranking(api, _project(api))
    for item in data["ranking"]:
        assert item["pertinencia"] and item["favorece"] and item["limitaciones"]
        assert item["origen"] and item["ambito"]
        assert item["numero_de_etapas"] in (5, 7, 15)
        for razon in item["razones"]:
            assert razon["tipo"] in {RC.TIPO_CONFIRMADO, RC.TIPO_INFERENCIA, RC.TIPO_CONVENCION, RC.TIPO_PREGUNTA}


def test_save_the_cat_se_describe_como_metodo_y_no_como_estructura_dramatica(api: TestClient) -> None:
    project_id = _project(api)
    data = _ranking(api, project_id)
    save = next(item for item in data["ranking"] if item["clave"] == "save_the_cat")
    assert "método" in save["origen"].lower()
    assert "guion" in save["ambito"].lower()


def test_sin_premisa_y_sin_punto_de_vista_se_piden_las_decisiones_pendientes(api: TestClient) -> None:
    project_id = _project(api)
    preguntas = _ranking(api, project_id)["preguntas_pendientes"]
    assert any("premisa" in pregunta for pregunta in preguntas)
    assert any("punto de vista" in pregunta for pregunta in preguntas)


def test_la_premisa_se_muestra_como_dato_usado_y_no_se_copia_en_los_motivos(api: TestClient) -> None:
    project_id = _project(api)
    _premisa(api, project_id)
    datos = _ranking(api, project_id)["datos"]
    assert datos["premisa"] == PREMISA
    textos = [razon["texto"] for item in _ranking(api, project_id)["ranking"] for razon in item["razones"]]
    assert not any(PREMISA in texto for texto in textos)


# ---------------------------------------------------------------------------------------------
# Etapas y propuestas
# ---------------------------------------------------------------------------------------------


def test_las_etapas_son_funciones_y_preguntas_no_acontecimientos(api: TestClient) -> None:
    for modelo in RC.MODELOS:
        for etapa in modelo.etapas:
            assert etapa.funcion and etapa.pregunta.endswith("?")
            assert PREMISA not in etapa.funcion and PREMISA not in etapa.pregunta


def test_generar_propuestas_crea_etapas_pendientes_con_los_datos_usados(api: TestClient) -> None:
    project_id = _project(api)
    _premisa(api, project_id)
    _directrices(api, project_id, punto_de_vista="un_personaje")
    _generos(api, project_id, "misterio")
    _elegir(api, project_id, "siete_puntos")

    propuestas = _generar(api, project_id)
    assert [p["title"] for p in propuestas] == [e.nombre for e in RC.etapas_de("siete_puntos")]
    assert all(p["estado"] == "pendiente" for p in propuestas)
    assert all(p["base_tipo"] == RC.TIPO_CONFIRMADO for p in propuestas)
    assert all(p["summary"] is None for p in propuestas)

    entradas = propuestas[0]["entradas"]
    assert entradas["premisa"] == PREMISA
    assert entradas["generos"] == ["Misterio e investigación"]
    assert entradas["directrices"]["punto_de_vista"] == "un_personaje"
    assert entradas["modelo"] == "siete_puntos"
    assert "un_personaje" in entradas["reglas"] and "genero_misterio" in entradas["reglas"]


def test_las_entradas_de_una_propuesta_no_cambian_si_luego_cambia_la_premisa(api: TestClient) -> None:
    project_id = _project(api)
    _premisa(api, project_id)
    _elegir(api, project_id, "freytag")
    propuestas = _generar(api, project_id)
    _premisa(api, project_id, "Otra premisa completamente distinta.")
    despues = _ranking(api, project_id)["propuestas"]
    assert despues[0]["entradas"]["premisa"] == PREMISA
    assert despues[0]["entradas"] == propuestas[0]["entradas"]


def test_sin_premisa_la_base_es_una_pregunta_pendiente(api: TestClient) -> None:
    project_id = _project(api)
    _elegir(api, project_id, "freytag")
    propuestas = _generar(api, project_id)
    assert all(p["base_tipo"] == RC.TIPO_PREGUNTA for p in propuestas)
    assert propuestas[0]["entradas"]["premisa"] is None


def test_generar_sin_modelo_elegido_ni_indicado_se_rechaza(api: TestClient) -> None:
    project_id = _project(api)
    response = api.post(_url(project_id, "/estructura-recomendada/propuestas"), json={})
    assert response.status_code == 422, response.text


def test_un_modelo_desconocido_se_rechaza(api: TestClient) -> None:
    project_id = _project(api)
    response = api.put(_url(project_id, "/estructura-recomendada/modelo"), json={"model_key": "heroes_viaje"})
    assert response.status_code == 422, response.text


def test_no_se_genera_un_segundo_lote_mientras_haya_pendientes_del_mismo_modelo(api: TestClient) -> None:
    project_id = _project(api)
    _generar(api, project_id, "freytag")
    response = api.post(_url(project_id, "/estructura-recomendada/propuestas"), json={"model_key": "freytag"})
    assert response.status_code == 409, response.text


def test_elegir_otro_modelo_conserva_el_anterior_y_permite_comparar(api: TestClient) -> None:
    project_id = _project(api)
    _elegir(api, project_id, "freytag")
    _elegir(api, project_id, "save_the_cat")
    data = _ranking(api, project_id)
    assert data["modelo_elegido"] == "save_the_cat"
    # El historial no se borra: las dos elecciones siguen en la base.
    assert api.get(_url(project_id, "/estructura-recomendada")).json()["modelo_elegido"] == "save_the_cat"


# ---------------------------------------------------------------------------------------------
# Aceptar, editar y rechazar: nunca canon
# ---------------------------------------------------------------------------------------------


def test_aceptar_crea_un_acto_provisional_de_origen_ia_y_no_canon(api: TestClient) -> None:
    project_id = _project(api)
    _premisa(api, project_id)
    _directrices(api, project_id, punto_de_vista="varios_personajes")
    _generos(api, project_id, "drama")
    personaje = api.post(_url(project_id, "/personajes"), json={"name": "Lucía"}).json()
    _elegir(api, project_id, "freytag")
    propuesta = _generar(api, project_id)[0]
    antes = _estado_del_canon(api, project_id)

    response = api.post(_url(project_id, f"/estructura-recomendada/propuestas/{propuesta['id']}/aceptar"))
    assert response.status_code == 200, response.text
    nodo = response.json()
    assert nodo["kind"] == "acto"
    assert nodo["estado"] == "provisional"
    assert nodo["origen"] == "ia"
    assert nodo["approved_decision_id"] is None
    assert nodo["title"] == propuesta["title"]

    # Nada del canon cambia: premisa, géneros, directrices, personajes y manuscritos siguen igual.
    despues = _estado_del_canon(api, project_id)
    for clave in ("narrativa", "directrices", "personajes", "manuscritos"):
        assert despues[clave] == antes[clave], clave
    assert personaje["id"] in [p["id"] for p in despues["personajes"]]

    decisiones = api.get(_url(project_id, f"/estructura/{nodo['id']}/decisiones")).json()
    assert [d["accion"] for d in decisiones] == ["crear_desde_propuesta"]
    assert all(d["estado_nuevo"] == "provisional" for d in decisiones)
    assert not any(d["accion"] == "aprobar_canon" for d in decisiones)


def test_la_propuesta_aceptada_sigue_en_la_lista_y_no_se_edita_ni_se_rechaza_despues(api: TestClient) -> None:
    project_id = _project(api)
    _elegir(api, project_id, "freytag")
    propuesta = _generar(api, project_id)[0]
    api.post(_url(project_id, f"/estructura-recomendada/propuestas/{propuesta['id']}/aceptar"))
    tras = next(p for p in _ranking(api, project_id)["propuestas"] if p["id"] == propuesta["id"])
    assert tras["estado"] == "aceptada" and tras["node_id"] is not None and tras["decided_at"] is not None

    editar = api.patch(_url(project_id, f"/estructura-recomendada/propuestas/{propuesta['id']}"), json={"title": "Cambio"})
    assert editar.status_code == 422
    rechazar = api.post(_url(project_id, f"/estructura-recomendada/propuestas/{propuesta['id']}/rechazar"))
    assert rechazar.status_code == 422


def test_las_etapas_se_aceptan_en_orden(api: TestClient) -> None:
    project_id = _project(api)
    _elegir(api, project_id, "freytag")
    propuestas = _generar(api, project_id)
    fuera_de_orden = api.post(_url(project_id, f"/estructura-recomendada/propuestas/{propuestas[1]['id']}/aceptar"))
    assert fuera_de_orden.status_code == 422, fuera_de_orden.text
    assert "anteriores" in fuera_de_orden.text


def test_rechazar_conserva_la_propuesta_y_no_crea_acto(api: TestClient) -> None:
    project_id = _project(api)
    _elegir(api, project_id, "freytag")
    propuesta = _generar(api, project_id)[0]
    estructura_antes = api.get(_url(project_id, "/estructura")).json()

    response = api.post(_url(project_id, f"/estructura-recomendada/propuestas/{propuesta['id']}/rechazar"))
    assert response.status_code == 200, response.text
    assert response.json()["estado"] == "rechazada"
    assert api.get(_url(project_id, "/estructura")).json() == estructura_antes
    assert any(p["id"] == propuesta["id"] for p in _ranking(api, project_id)["propuestas"])


def test_editar_una_propuesta_pendiente_cambia_titulo_y_resumen(api: TestClient) -> None:
    project_id = _project(api)
    _elegir(api, project_id, "freytag")
    propuesta = _generar(api, project_id)[0]
    response = api.patch(
        _url(project_id, f"/estructura-recomendada/propuestas/{propuesta['id']}"),
        json={"title": "Planteamiento de Lucía", "summary": "Lo que el autor decide."},
    )
    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Planteamiento de Lucía"
    assert response.json()["summary"] == "Lo que el autor decide."
    assert response.json()["entradas"] == propuesta["entradas"]


def test_editar_con_titulo_vacio_o_campo_no_editable_se_rechaza(api: TestClient) -> None:
    project_id = _project(api)
    _elegir(api, project_id, "freytag")
    propuesta = _generar(api, project_id)[0]
    url = _url(project_id, f"/estructura-recomendada/propuestas/{propuesta['id']}")
    assert api.patch(url, json={"title": "   "}).status_code == 422
    assert api.patch(url, json={"estado": "aceptada"}).status_code == 422


def test_las_propuestas_no_cambian_la_estructura_ni_su_revision(api: TestClient) -> None:
    project_id = _project(api)
    estructura_antes = api.get(_url(project_id, "/estructura")).json()
    _elegir(api, project_id, "save_the_cat")
    _generar(api, project_id)
    assert api.get(_url(project_id, "/estructura")).json() == estructura_antes


def test_propuesta_de_otra_novela_no_se_ve_ni_se_acepta(api: TestClient) -> None:
    propia = _project(api, "Propia")
    ajena = _project(api, "Ajena")
    _elegir(api, propia, "freytag")
    propuesta = _generar(api, propia)[0]
    assert api.post(_url(ajena, f"/estructura-recomendada/propuestas/{propuesta['id']}/aceptar")).status_code == 404
    assert api.post(_url(ajena, f"/estructura-recomendada/propuestas/{propuesta['id']}/rechazar")).status_code == 404
    assert _ranking(api, ajena)["propuestas"] == []


def test_archivar_la_novela_impide_generar_y_decidir(api: TestClient) -> None:
    project_id = _project(api)
    _elegir(api, project_id, "freytag")
    propuesta = _generar(api, project_id)[0]
    assert api.post(f"/projects/{project_id}/archive").status_code == 200
    assert api.post(_url(project_id, "/estructura-recomendada/propuestas"), json={"model_key": "freytag"}).status_code == 422
    assert api.post(_url(project_id, f"/estructura-recomendada/propuestas/{propuesta['id']}/aceptar")).status_code == 422
