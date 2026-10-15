"""Pruebas de la API mínima."""

from fastapi.testclient import TestClient

from app import __version__
from app.main import create_app


def test_health_responde_ok(settings) -> None:
    # Base temporal migrada: /health consulta el esquema y no debe tocar la base de uso normal.
    client = TestClient(create_app(settings))
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "novel-engine-backend"
    assert data["version"] == __version__
    assert data["esquema"]["al_dia"] is True


def test_ruta_inexistente_devuelve_404(settings) -> None:
    client = TestClient(create_app(settings))
    assert client.get("/manuscritos").status_code == 404
