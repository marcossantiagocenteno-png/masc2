"""API HTTP de textos, versiones y revisiones."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def _create_manuscript(client: TestClient, title: str, content: str) -> dict:
    response = client.post("/manuscripts", json={"title": title, "content": content})
    assert response.status_code == 201, response.text
    return response.json()


def _versions(client: TestClient, manuscript_id: int) -> list[dict]:
    return client.get(f"/manuscripts/{manuscript_id}/versions").json()


def test_flujo_completo_por_api(client: TestClient) -> None:
    manuscript = _create_manuscript(client, "Flujo", "Hola mundo.\nSegunda línea.")
    assert manuscript["latest_version_number"] == 1

    v1 = _versions(client, manuscript["id"])[0]
    assert v1["number"] == 1

    created = client.post(
        f"/manuscripts/{manuscript['id']}/versions",
        json={"content": "Hola mundo, revisado.\nSegunda línea.", "note": "segunda"},
    )
    assert created.status_code == 201
    v2 = created.json()
    assert v2["number"] == 2
    assert v2["note"] == "segunda"

    old = client.get(f"/versions/{v1['id']}").json()
    assert old["content"] == "Hola mundo.\nSegunda línea."
    assert old["sha256"] == v1["sha256"]


def test_comentario_sobre_v1_no_aparece_en_v2(client: TestClient) -> None:
    manuscript = _create_manuscript(client, "Comentarios", "Hola mundo.\nSegunda línea.")
    v1 = _versions(client, manuscript["id"])[0]
    v2 = client.post(
        f"/manuscripts/{manuscript['id']}/versions", json={"content": "Otra cosa."}
    ).json()

    response = client.post(
        f"/versions/{v1['id']}/reviews",
        json={
            "reviewer": "Editora",
            "items": [
                {
                    "kind": "observacion",
                    "quote": "mundo",
                    "start_offset": 5,
                    "end_offset": 10,
                    "comment": "Vocativo demasiado genérico.",
                    "suggestion": "Valorar otra imagen. No se aplica automáticamente.",
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    review = response.json()
    assert review["items"][0]["line_number"] == 1
    assert review["items"][0]["intent_status"] == "no_declarada"

    assert len(client.get(f"/versions/{v1['id']}/reviews").json()) == 1
    assert client.get(f"/versions/{v2['id']}/reviews").json() == []
    assert client.get(f"/versions/{v1['id']}").json()["review_count"] == 1


def test_cita_incorrecta_responde_422(client: TestClient) -> None:
    manuscript = _create_manuscript(client, "Error", "Texto breve.")
    v1 = _versions(client, manuscript["id"])[0]
    response = client.post(
        f"/versions/{v1['id']}/reviews",
        json={
            "reviewer": "Editor",
            "items": [
                {"kind": "observacion", "quote": "nada", "start_offset": 0, "end_offset": 4, "comment": "x"}
            ],
        },
    )
    assert response.status_code == 422
    assert "no coincide" in response.json()["detail"]


def test_inferencia_sin_cadena_responde_422(client: TestClient) -> None:
    manuscript = _create_manuscript(client, "Inferencia", "Texto breve.")
    v1 = _versions(client, manuscript["id"])[0]
    response = client.post(
        f"/versions/{v1['id']}/reviews",
        json={
            "reviewer": "Editor",
            "items": [
                {"kind": "inferencia", "quote": "Texto", "start_offset": 0, "end_offset": 5, "comment": "x"}
            ],
        },
    )
    assert response.status_code == 422


def test_campos_desconocidos_se_rechazan(client: TestClient) -> None:
    manuscript = _create_manuscript(client, "Campos", "Texto.")
    v1 = _versions(client, manuscript["id"])[0]
    response = client.post(
        f"/versions/{v1['id']}/reviews",
        json={
            "reviewer": "Editor",
            "items": [
                {
                    "kind": "observacion",
                    "quote": "Texto",
                    "start_offset": 0,
                    "end_offset": 5,
                    "comment": "x",
                    "intent_status": "declarada_por_autor",
                }
            ],
        },
    )
    assert response.status_code == 422


def test_version_de_otro_manuscrito_responde_422(client: TestClient) -> None:
    first = _create_manuscript(client, "Uno", "Texto A.")
    second = _create_manuscript(client, "Dos", "Texto B.")
    foreign = _versions(client, second["id"])[0]
    response = client.post(
        f"/manuscripts/{first['id']}/versions",
        json={"content": "Intento.", "based_on_version_id": foreign["id"]},
    )
    assert response.status_code == 422


def test_recursos_inexistentes_responden_404(client: TestClient) -> None:
    assert client.get("/manuscripts/999999").status_code == 404
    assert client.get("/versions/999999").status_code == 404
    assert client.get("/versions/999999/reviews").status_code == 404


def test_titulo_vacio_responde_422(client: TestClient) -> None:
    assert client.post("/manuscripts", json={"title": "   ", "content": "x"}).status_code == 422


def test_contenido_demasiado_grande_responde_413(settings: Settings) -> None:
    small = Settings(database_url=settings.database_url, max_version_chars=20)
    with TestClient(create_app(small)) as limited:
        response = limited.post("/manuscripts", json={"title": "Grande", "content": "x" * 21})
        assert response.status_code == 413
        assert "límite es 20" in response.json()["detail"]


def test_cors_permite_el_frontend_en_local(client: TestClient) -> None:
    response = client.options(
        "/manuscripts",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_health_sigue_respondiendo(client: TestClient) -> None:
    assert client.get("/health").json()["status"] == "ok"
