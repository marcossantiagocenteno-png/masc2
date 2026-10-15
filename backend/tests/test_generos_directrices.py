"""Géneros seleccionables y directrices narrativas (F1).

Comprueba la API, la integridad (nada se borra, proyectos archivados, aislamiento) y que el género de texto
heredado se sigue leyendo sin cambios.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.planning import generos as GENEROS


@pytest.fixture
def api(client: TestClient) -> TestClient:
    return client


def _project(api: TestClient, name: str = "Novela") -> int:
    response = api.post("/projects", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _url(project_id: int, path: str = "") -> str:
    return f"/projects/{project_id}/planificacion{path}"


def test_el_catalogo_expone_claves_etiquetas_y_otro(api: TestClient) -> None:
    project_id = _project(api)
    data = api.get(_url(project_id, "/narrativa")).json()
    claves = [g["key"] for g in data["genre_catalog"]]
    assert "misterio" in claves and claves[-1] == "otro"
    assert len(claves) == len(set(claves))
    assert data["genres"] == []
    assert data["genre"] is None


def test_seleccion_multiple_y_otro_con_texto(api: TestClient) -> None:
    project_id = _project(api)
    response = api.put(
        _url(project_id, "/generos"),
        json={"generos": [{"key": "misterio"}, {"key": "terror"}, {"key": "otro", "custom_label": "Gótico"}]},
    )
    assert response.status_code == 200, response.text
    data = api.get(_url(project_id, "/narrativa")).json()
    etiquetas = {g["key"]: g["custom_label"] or g["label"] for g in data["genres"]}
    assert etiquetas == {"misterio": "Misterio e investigación", "terror": "Terror", "otro": "Gótico"}
    assert set(data["genre"].split(", ")) == {"Misterio e investigación", "Terror", "Gótico"}


def test_otro_sin_texto_y_claves_desconocidas_se_rechazan(api: TestClient) -> None:
    project_id = _project(api)
    assert api.put(_url(project_id, "/generos"), json={"generos": [{"key": "otro"}]}).status_code == 422
    assert api.put(_url(project_id, "/generos"), json={"generos": [{"key": "no_existe"}]}).status_code == 422
    assert api.get(_url(project_id, "/narrativa")).json()["genres"] == []


def test_deseleccionar_no_borra_y_al_volver_a_elegir_se_reactiva(api: TestClient, settings) -> None:
    project_id = _project(api)
    api.put(_url(project_id, "/generos"), json={"generos": [{"key": "otro", "custom_label": "Gótico"}]})
    api.put(_url(project_id, "/generos"), json={"generos": []})
    assert api.get(_url(project_id, "/narrativa")).json()["genres"] == []

    db = Path(settings.database_url.removeprefix("sqlite:///"))
    with closing(sqlite3.connect(db)) as connection:
        assert connection.execute("SELECT custom_label, activo FROM project_genres").fetchall() == [("Gótico", 0)]

    api.put(_url(project_id, "/generos"), json={"generos": [{"key": "otro", "custom_label": "Gótico"}]})
    with closing(sqlite3.connect(db)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM project_genres").fetchone() == (1,)


def test_la_sinopsis_se_conserva_y_no_se_envia_desde_la_interfaz(api: TestClient) -> None:
    project_id = _project(api)
    api.patch(_url(project_id, "/narrativa"), json={"premise": "Premisa", "synopsis": "Texto heredado"})
    # Un PATCH sin «synopsis» no la toca.
    api.patch(_url(project_id, "/narrativa"), json={"tone": "sobrio"})
    data = api.get(_url(project_id, "/narrativa")).json()
    assert data["synopsis"] == "Texto heredado"
    assert data["premise"] == "Premisa"


def test_el_campo_genero_de_texto_ya_no_se_escribe(api: TestClient) -> None:
    project_id = _project(api)
    assert api.patch(_url(project_id, "/narrativa"), json={"genre": "Gótico"}).status_code == 422


def test_directrices_se_guardan_con_valores_explicitos_y_sin_valor_por_defecto(api: TestClient) -> None:
    project_id = _project(api)
    assert api.get(_url(project_id, "/directrices")).json() is None
    response = api.put(
        _url(project_id, "/directrices"),
        json={"voz": "Seca", "persona": "primera", "tiempo_verbal": "pasado", "punto_de_vista": "un_personaje", "estilo": "Frases cortas"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["persona"] == "primera"
    assert data["focalizacion"] is None  # no se impone: el autor no lo ha elegido
    assert api.get(_url(project_id, "/narrativa")).json()["directives"]["voz"] == "Seca"


def test_directrices_con_valores_no_permitidos_se_rechazan(api: TestClient) -> None:
    project_id = _project(api)
    assert api.put(_url(project_id, "/directrices"), json={"persona": "cuarta"}).status_code == 422
    assert api.put(_url(project_id, "/directrices"), json={"tono": "x"}).status_code == 422


def test_el_tono_y_el_genero_no_se_copian_en_las_directrices(api: TestClient) -> None:
    project_id = _project(api)
    api.put(_url(project_id, "/directrices"), json={"voz": "Seca"})
    row_fields = set(api.get(_url(project_id, "/directrices")).json())
    assert "tone" not in row_fields and "genre" not in row_fields


def test_escribir_en_un_proyecto_archivado_se_rechaza(api: TestClient) -> None:
    project_id = _project(api)
    api.post(f"/projects/{project_id}/archive")
    assert api.put(_url(project_id, "/generos"), json={"generos": [{"key": "misterio"}]}).status_code == 422
    assert api.put(_url(project_id, "/directrices"), json={"voz": "x"}).status_code == 422


def test_los_generos_y_directrices_de_un_proyecto_no_aparecen_en_otro(api: TestClient) -> None:
    a = _project(api, "A")
    b = _project(api, "B")
    api.put(_url(a, "/generos"), json={"generos": [{"key": "misterio"}]})
    api.put(_url(a, "/directrices"), json={"voz": "Solo de A"})
    assert api.get(_url(b, "/narrativa")).json()["genres"] == []
    assert api.get(_url(b, "/directrices")).json() is None


def test_el_catalogo_python_coincide_con_la_respuesta_de_la_api(api: TestClient) -> None:
    project_id = _project(api)
    assert api.get(_url(project_id, "/narrativa")).json()["genre_catalog"] == GENEROS.catalogo()
