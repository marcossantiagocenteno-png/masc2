"""Aislamiento de análisis y revisiones editoriales por proyecto (fase 2f).

Las pruebas negativas usan identificadores válidos de OTRO proyecto. Comprueban que la operación se
rechaza con la misma respuesta que una versión inexistente, que no se crea ni se modifica ningún registro,
y que ningún proveedor llega a resolverse.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.backup_fakes import FakeClock

TEXT = "La lluvia cae sobre la casa vacía."


@pytest.fixture
def api(client: TestClient) -> TestClient:
    client.app.state.clock = FakeClock()
    return client


def _project(api: TestClient, name: str) -> int:
    return api.post("/projects", json={"name": name}).json()["id"]


def _version(api: TestClient, project: int, title: str) -> tuple[int, int]:
    """Crea un manuscrito con texto en el proyecto. Devuelve (manuscrito, versión)."""
    created = api.post(f"/projects/{project}/manuscripts", json={"title": title, "content": TEXT})
    assert created.status_code == 201, created.text
    manuscript = created.json()["id"]
    version = api.get(f"/projects/{project}/manuscripts/{manuscript}/versions").json()[0]["id"]
    return manuscript, version


def _review_body(quote: str = "lluvia") -> dict:
    start = TEXT.index(quote)
    return {
        "reviewer": "Editora",
        "items": [
            {"kind": "observacion", "quote": quote, "start_offset": start, "end_offset": start + len(quote), "comment": "Revisar."}
        ],
    }


def _counts(api: TestClient, project: int, manuscript: int, version: int) -> tuple[int, int]:
    base = f"/projects/{project}/manuscripts/{manuscript}/versions/{version}"
    return len(api.get(base + "/analyses").json()), len(api.get(base + "/reviews").json())


def _no_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si una petición rechazada llega a resolver un proveedor, la prueba falla."""
    import app.analysis.routes as analysis_routes

    def forbidden(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("un proveedor se resolvió para una petición que debía rechazarse")

    monkeypatch.setattr(analysis_routes, "resolve_provider", forbidden)


# ----------------------------------------------------------------------
# Los usuarios legítimos siguen usando análisis y revisiones
# ----------------------------------------------------------------------


def test_una_revision_se_crea_y_se_lee_por_la_ruta_del_proyecto(api: TestClient) -> None:
    project = _project(api, "Revisiones")
    manuscript, version = _version(api, project, "Revisado")
    base = f"/projects/{project}/manuscripts/{manuscript}/versions/{version}"
    created = api.post(base + "/reviews", json=_review_body())
    assert created.status_code == 201, created.text
    listed = api.get(base + "/reviews").json()
    assert [item["id"] for item in listed] == [created.json()["id"]]


def test_un_analisis_se_crea_y_se_lee_por_la_ruta_del_proyecto(api: TestClient) -> None:
    project = _project(api, "Analisis")
    manuscript, version = _version(api, project, "Analizado")
    base = f"/projects/{project}/manuscripts/{manuscript}/versions/{version}"
    created = api.post(base + "/analyses", json={"start_offset": 0, "end_offset": 10})
    assert created.status_code == 201, created.text
    assert [run["id"] for run in api.get(base + "/analyses").json()] == [created.json()["id"]]


# ----------------------------------------------------------------------
# Negativas: identificadores válidos de otro proyecto
# ----------------------------------------------------------------------


@pytest.fixture
def two_novels(api: TestClient) -> dict:
    project_a = _project(api, "Novela A")
    project_b = _project(api, "Novela B")
    manuscript_a, version_a = _version(api, project_a, "A")
    return {"a": project_a, "b": project_b, "ms_a": manuscript_a, "v_a": version_a}


def test_leer_analisis_o_revisiones_de_otro_proyecto_responde_como_una_version_inexistente(api: TestClient, two_novels: dict) -> None:
    b, ms, v = two_novels["b"], two_novels["ms_a"], two_novels["v_a"]
    missing = api.get(f"/projects/{b}/manuscripts/{ms}/versions/999999/reviews")
    foreign = api.get(f"/projects/{b}/manuscripts/{ms}/versions/{v}/reviews")
    assert missing.status_code == foreign.status_code == 404
    assert missing.json() == foreign.json()
    assert api.get(f"/projects/{b}/manuscripts/{ms}/versions/{v}/analyses").status_code == 404


def test_crear_revision_o_analisis_en_otro_proyecto_se_rechaza_sin_crear_nada(
    api: TestClient, two_novels: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b, ms, v = two_novels["a"], two_novels["b"], two_novels["ms_a"], two_novels["v_a"]
    before = _counts(api, a, ms, v)
    _no_provider(monkeypatch)

    foreign_review = api.post(f"/projects/{b}/manuscripts/{ms}/versions/{v}/reviews", json=_review_body())
    foreign_analysis = api.post(f"/projects/{b}/manuscripts/{ms}/versions/{v}/analyses", json={"start_offset": 0, "end_offset": 10})
    missing = api.post(f"/projects/{b}/manuscripts/{ms}/versions/999999/reviews", json=_review_body())

    assert foreign_review.status_code == 404
    assert foreign_analysis.status_code == 404
    assert foreign_review.json() == missing.json()
    assert _counts(api, a, ms, v) == before  # ningún registro nuevo en la novela de origen


def test_proyecto_que_no_contiene_el_manuscrito_no_ve_nada_aunque_use_el_id_correcto(api: TestClient, two_novels: dict) -> None:
    b, ms = two_novels["b"], two_novels["ms_a"]
    other_version = api.get(f"/projects/{two_novels['a']}/manuscripts/{ms}/versions").json()[0]["id"]
    assert api.get(f"/projects/{b}/manuscripts/{ms}/versions/{other_version}/analyses").status_code == 404


def test_la_autorizacion_externa_no_llega_a_un_proveedor_si_la_version_es_de_otro_proyecto(
    api: TestClient, two_novels: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    b, ms, v = two_novels["b"], two_novels["ms_a"], two_novels["v_a"]
    _no_provider(monkeypatch)
    response = api.post(
        f"/projects/{b}/manuscripts/{ms}/versions/{v}/analyses",
        json={
            "start_offset": 0,
            "end_offset": 10,
            "external_authorization": {"provider": "anthropic", "scope": "fragmento_seleccionado", "acknowledged": True},
        },
    )
    assert response.status_code == 404


def test_archivar_el_proyecto_propio_no_permite_escribir_revisiones_ni_analisis(api: TestClient, two_novels: dict) -> None:
    a, ms, v = two_novels["a"], two_novels["ms_a"], two_novels["v_a"]
    before = _counts(api, a, ms, v)
    api.post(f"/projects/{a}/archive")
    base = f"/projects/{a}/manuscripts/{ms}/versions/{v}"
    assert api.post(base + "/reviews", json=_review_body()).status_code == 422
    assert api.post(base + "/analyses", json={"start_offset": 0, "end_offset": 10}).status_code == 422
    assert _counts(api, a, ms, v) == before


# ----------------------------------------------------------------------
# Rutas heredadas: no atienden manuscritos de proyecto
# ----------------------------------------------------------------------


def test_las_rutas_heredadas_de_revision_y_analisis_no_atienden_manuscritos_de_proyecto(
    api: TestClient, two_novels: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, ms, v = two_novels["a"], two_novels["ms_a"], two_novels["v_a"]
    before = _counts(api, a, ms, v)
    _no_provider(monkeypatch)
    assert api.get(f"/versions/{v}/reviews").status_code == 404
    assert api.get(f"/versions/{v}/analyses").status_code == 404
    assert api.post(f"/versions/{v}/reviews", json=_review_body()).status_code == 422
    assert api.post(f"/versions/{v}/analyses", json={"start_offset": 0, "end_offset": 10}).status_code == 422
    assert _counts(api, a, ms, v) == before


def test_las_rutas_heredadas_siguen_sirviendo_a_manuscritos_sin_proyecto(api: TestClient) -> None:
    created = api.post("/manuscripts", json={"title": "Suelto", "content": TEXT})
    assert created.status_code == 201
    version = api.get(f"/manuscripts/{created.json()['id']}/versions").json()[0]["id"]
    assert api.post(f"/versions/{version}/reviews", json=_review_body()).status_code == 201
    assert len(api.get(f"/versions/{version}/reviews").json()) == 1
