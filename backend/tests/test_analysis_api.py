"""API del análisis: proveedor por configuración, respuestas y conservación del texto."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

CONTENT = "Dijo que que no lo sabía.\nLa lluvia caía sobre el tejado."


def _manuscript_and_version(client: TestClient) -> tuple[int, int]:
    manuscript = client.post("/manuscripts", json={"title": "API análisis", "content": CONTENT}).json()
    version = client.get(f"/manuscripts/{manuscript['id']}/versions").json()[0]
    return manuscript["id"], version["id"]


def test_analisis_por_defecto_usa_el_simulado_y_lo_indica(client: TestClient) -> None:
    _, version_id = _manuscript_and_version(client)
    response = client.post(f"/versions/{version_id}/analyses", json={"start_offset": 0, "end_offset": len(CONTENT)})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["provider_simulated"] is True
    assert body["provider_name"] == "simulado"
    assert "SIMULADO" in body["provider_label"]
    assert body["fragment_text"] == CONTENT
    categories = {finding["category"] for finding in body["findings"]}
    assert "problema_verificable" in categories
    assert categories <= {
        "problema_verificable",
        "observacion_literaria",
        "preferencia_de_gusto",
    }


def test_cada_hallazgo_expone_cita_posicion_explicacion_y_certeza(client: TestClient) -> None:
    _, version_id = _manuscript_and_version(client)
    body = client.post(f"/versions/{version_id}/analyses", json={"start_offset": 0, "end_offset": len(CONTENT)}).json()
    for finding in body["findings"]:
        assert CONTENT[finding["start_offset"] : finding["end_offset"]] == finding["quote"]
        assert finding["explanation"]
        assert finding["certainty"]


def test_proveedor_no_autorizado_responde_503(settings: Settings) -> None:
    configured = Settings(database_url=settings.database_url, analysis_provider="openai")
    with TestClient(create_app(configured)) as client:
        _, version_id = _manuscript_and_version(client)
        response = client.post(f"/versions/{version_id}/analyses", json={"start_offset": 0, "end_offset": 10})
        assert response.status_code == 503
        assert "no está autorizado" in response.json()["detail"]


def test_el_cliente_no_puede_elegir_proveedor(client: TestClient) -> None:
    _, version_id = _manuscript_and_version(client)
    response = client.post(
        f"/versions/{version_id}/analyses",
        json={"start_offset": 0, "end_offset": 10, "provider": "openai"},
    )
    assert response.status_code == 422


def test_rango_invalido_responde_422(client: TestClient) -> None:
    _, version_id = _manuscript_and_version(client)
    response = client.post(f"/versions/{version_id}/analyses", json={"start_offset": 9, "end_offset": 3})
    assert response.status_code == 422


def test_fragmento_demasiado_grande_responde_413(settings: Settings) -> None:
    limited = Settings(database_url=settings.database_url, max_analysis_chars=10)
    with TestClient(create_app(limited)) as client:
        _, version_id = _manuscript_and_version(client)
        response = client.post(f"/versions/{version_id}/analyses", json={"start_offset": 0, "end_offset": 11})
        assert response.status_code == 413


def test_analisis_no_altera_la_version_ni_su_hash(client: TestClient) -> None:
    _, version_id = _manuscript_and_version(client)
    before = client.get(f"/versions/{version_id}").json()
    client.post(f"/versions/{version_id}/analyses", json={"start_offset": 0, "end_offset": len(CONTENT)})
    after = client.get(f"/versions/{version_id}").json()
    assert after["content"] == before["content"] == CONTENT
    assert after["sha256"] == before["sha256"]


def test_analisis_se_listan_por_version_y_no_aparecen_en_otra(client: TestClient) -> None:
    manuscript_id, version_id = _manuscript_and_version(client)
    other = client.post(
        f"/manuscripts/{manuscript_id}/versions", json={"content": "Otra versión completamente distinta."}
    ).json()
    client.post(f"/versions/{version_id}/analyses", json={"start_offset": 0, "end_offset": 10})
    assert len(client.get(f"/versions/{version_id}/analyses").json()) == 1
    assert client.get(f"/versions/{other['id']}/analyses").json() == []


def test_version_inexistente_responde_404(client: TestClient) -> None:
    assert client.post("/versions/999999/analyses", json={"start_offset": 0, "end_offset": 5}).status_code == 404
    assert client.get("/versions/999999/analyses").status_code == 404
