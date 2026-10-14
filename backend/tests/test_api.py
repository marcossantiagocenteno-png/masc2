"""Pruebas de la API mínima."""

from fastapi.testclient import TestClient

from app import __version__
from app.main import create_app


def test_health_responde_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "novel-engine-backend",
        "version": __version__,
    }


def test_ruta_inexistente_devuelve_404() -> None:
    client = TestClient(create_app())
    assert client.get("/manuscritos").status_code == 404
