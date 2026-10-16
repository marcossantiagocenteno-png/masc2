"""Aislamiento entre novelas en versiones: un identificador de otra novela no revela nada ni cambia datos.

Criterio decidido: ``based_on_version_id`` de otra novela, de otro manuscrito o inexistente responde lo mismo
(422, mismo cuerpo). Así la respuesta no permite saber si una versión ajena existe.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import ManuscriptVersion
from app.main import create_app


@pytest.fixture
def api(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def _novela_con_manuscrito(api: TestClient, nombre: str) -> tuple[int, int, int]:
    proyecto = api.post("/projects", json={"name": nombre}).json()["id"]
    manuscrito = api.post(f"/projects/{proyecto}/manuscripts", json={"title": f"Cap {nombre}", "content": f"Texto de {nombre}"})
    assert manuscrito.status_code == 201, manuscrito.text
    mid = manuscrito.json()["id"]
    versiones = api.get(f"/projects/{proyecto}/manuscripts/{mid}/versions").json()
    return proyecto, mid, versiones[0]["id"]


def _total_versiones(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(ManuscriptVersion))


def test_based_on_de_otra_novela_responde_igual_que_un_id_inexistente(api: TestClient, session: Session) -> None:
    _, _, version_a = _novela_con_manuscrito(api, "A")
    proyecto_b, mid_b, _ = _novela_con_manuscrito(api, "B")
    antes = _total_versiones(session)

    ajena = api.post(
        f"/projects/{proyecto_b}/manuscripts/{mid_b}/versions",
        json={"content": "Intento de enlazar", "based_on_version_id": version_a},
    )
    inexistente = api.post(
        f"/projects/{proyecto_b}/manuscripts/{mid_b}/versions",
        json={"content": "Intento de enlazar", "based_on_version_id": 987654},
    )

    assert ajena.status_code == inexistente.status_code == 422
    assert ajena.json() == inexistente.json()
    assert _total_versiones(session) == antes


def test_based_on_de_otro_manuscrito_de_la_misma_novela_responde_igual(api: TestClient) -> None:
    proyecto, mid_a, _ = _novela_con_manuscrito(api, "Misma novela")
    otro = api.post(f"/projects/{proyecto}/manuscripts", json={"title": "Otro cap", "content": "Otro"}).json()["id"]
    version_otro = api.get(f"/projects/{proyecto}/manuscripts/{otro}/versions").json()[0]["id"]

    respuesta = api.post(
        f"/projects/{proyecto}/manuscripts/{mid_a}/versions",
        json={"content": "Enlace cruzado", "based_on_version_id": version_otro},
    )
    assert respuesta.status_code == 422


def test_una_version_valida_de_la_misma_novela_sí_se_enlaza(api: TestClient, session: Session) -> None:
    proyecto, mid, version = _novela_con_manuscrito(api, "Enlace valido")
    respuesta = api.post(
        f"/projects/{proyecto}/manuscripts/{mid}/versions",
        json={"content": "Versión derivada", "based_on_version_id": version},
    )
    assert respuesta.status_code == 201
    nueva = session.get(ManuscriptVersion, respuesta.json()["id"])
    session.refresh(nueva)
    assert nueva.parent_version_id == version


@pytest.mark.parametrize("valor", [0, -1, 2**63, "abc"])
def test_identificadores_base_no_validos_responden_422_sin_500(api: TestClient, valor) -> None:
    proyecto, mid, _ = _novela_con_manuscrito(api, f"Invalido {valor}")
    respuesta = api.post(
        f"/projects/{proyecto}/manuscripts/{mid}/versions",
        json={"content": "x", "based_on_version_id": valor},
    )
    assert respuesta.status_code == 422


def test_leer_o_cambiar_una_version_ajena_responde_404_y_no_cambia_nada(api: TestClient) -> None:
    _, _, version_a = _novela_con_manuscrito(api, "Ajena A")
    proyecto_b, mid_b, _ = _novela_con_manuscrito(api, "Ajena B")
    proyecto_a = api.get("/projects").json()[0]["id"]
    antes = api.get(f"/projects/{proyecto_a}/manuscripts").json()

    lectura = api.get(f"/projects/{proyecto_b}/manuscripts/{mid_b}/versions/{version_a}")
    escritura = api.post(f"/projects/{proyecto_b}/manuscripts/{mid_b}/versions/{version_a}/reviews", json={"items": []})

    assert lectura.status_code == 404
    assert escritura.status_code in (404, 422)
    assert api.get(f"/projects/{proyecto_a}/manuscripts").json() == antes
