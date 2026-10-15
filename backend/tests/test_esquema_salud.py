"""E0: estado del esquema en /health, aviso al arrancar y errores con cabeceras CORS.

Una base sin migrar hacía que el navegador mostrara «No se pudo conectar» porque el 500 no llevaba CORS. Estas
pruebas fijan que el backend lo informa y que el error llega con cabeceras CORS para los orígenes permitidos.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.config import Settings
from app.db.esquema import BACKEND_DIR, estado_del_esquema, revision_esperada
from app.db.session import create_engine_for
from app.main import create_app

REVISION_ANTERIOR = "0009_escritura_escenas"


def _base_en_revision(tmp_path: Path, revision: str) -> str:
    url = f"sqlite:///{(tmp_path / 'base.sqlite').as_posix()}"
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["database_url"] = url
    command.upgrade(config, revision)
    return url


def test_la_revision_esperada_es_la_ultima_migracion() -> None:
    assert revision_esperada() == "0012_asistente"


def test_health_informa_de_una_base_al_dia(client: TestClient) -> None:
    data = client.get("/health").json()
    assert data["status"] == "ok"
    assert data["esquema"] == {
        "disponible": True,
        "revision_actual": revision_esperada(),
        "revision_esperada": revision_esperada(),
        "al_dia": True,
    }


def test_health_informa_de_una_base_atrasada_sin_dejar_de_responder(tmp_path: Path) -> None:
    settings = Settings(database_url=_base_en_revision(tmp_path, REVISION_ANTERIOR))
    with TestClient(create_app(settings)) as client:
        response = client.get("/health")
    assert response.status_code == 200
    esquema = response.json()["esquema"]
    assert esquema["al_dia"] is False
    assert esquema["revision_actual"] == REVISION_ANTERIOR
    assert esquema["revision_esperada"] == revision_esperada()


def test_una_base_vacia_es_accesible_pero_no_esta_migrada(tmp_path: Path) -> None:
    # create_engine_for crea el archivo: una base vacía existe, no tiene revisión y no está al día.
    engine = create_engine_for(f"sqlite:///{(tmp_path / 'vacia.sqlite').as_posix()}")
    estado = estado_del_esquema(engine)
    assert estado == {
        "disponible": True,
        "revision_actual": None,
        "revision_esperada": revision_esperada(),
        "al_dia": False,
    }
    engine.dispose()


def test_una_base_inaccesible_se_informa_como_no_disponible(tmp_path: Path) -> None:
    # Sin creación de directorio, el archivo no se puede abrir: el estado debe decirlo.
    engine = create_engine(f"sqlite:///{(tmp_path / 'no_existe' / 'x.sqlite').as_posix()}")
    estado = estado_del_esquema(engine)
    assert estado["disponible"] is False
    assert estado["revision_actual"] is None
    assert estado["al_dia"] is False
    engine.dispose()


def test_el_arranque_avisa_de_una_base_atrasada(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    settings = Settings(database_url=_base_en_revision(tmp_path, REVISION_ANTERIOR))
    with caplog.at_level(logging.WARNING, logger="app.main"), TestClient(create_app(settings)):
        pass
    avisos = [registro.getMessage() for registro in caplog.records if registro.levelno == logging.WARNING]
    assert any("alembic upgrade head" in aviso for aviso in avisos)


def test_el_arranque_no_avisa_de_una_base_al_dia(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    settings = Settings(database_url=_base_en_revision(tmp_path, revision_esperada()))
    with caplog.at_level(logging.WARNING, logger="app.main"), TestClient(create_app(settings)):
        pass
    assert not [registro for registro in caplog.records if "alembic upgrade head" in registro.getMessage()]


def _app_con_ruta_que_falla(settings: Settings):
    app = create_app(settings)

    @app.get("/__fallo_de_prueba")
    def fallo() -> None:
        raise RuntimeError("fallo deliberado de la prueba")

    return app


def test_un_error_no_controlado_devuelve_500_con_cabeceras_cors_para_el_origen_permitido(settings: Settings) -> None:
    app = _app_con_ruta_que_falla(settings)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/__fallo_de_prueba", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "Revisa el registro" in response.json()["detail"]


def test_un_error_no_controlado_no_da_cors_a_un_origen_ajeno(settings: Settings) -> None:
    app = _app_con_ruta_que_falla(settings)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/__fallo_de_prueba", headers={"Origin": "https://ajeno.example"})
    assert response.status_code == 500
    assert "access-control-allow-origin" not in response.headers
