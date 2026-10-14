"""Recuperación por copia de la base de datos (única vía de respaldo disponible hoy).

Procedimiento documentado: detener la aplicación, copiar el archivo SQLite,
y para restaurar, sustituir el archivo por la copia con la aplicación detenida.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def _url_for(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def test_restaurar_una_copia_devuelve_el_estado_anterior(tmp_path: Path, database_url: str) -> None:
    live = Path(database_url.removeprefix("sqlite:///"))
    backup = tmp_path / "copia.sqlite"

    # 1) Estado inicial y copia de seguridad (con la aplicación detenida: sin conexiones abiertas).
    with TestClient(create_app(Settings(database_url=database_url))) as client:
        manuscript = client.post("/manuscripts", json={"title": "Antes", "content": "Texto original."}).json()
    shutil.copyfile(live, backup)

    # 2) Cambios posteriores.
    with TestClient(create_app(Settings(database_url=database_url))) as client:
        client.post(f"/manuscripts/{manuscript['id']}/versions", json={"content": "Cambio posterior."})
        assert len(client.get(f"/manuscripts/{manuscript['id']}/versions").json()) == 2

    # 3) Restauración: sustituir el archivo por la copia.
    shutil.copyfile(backup, live)

    with TestClient(create_app(Settings(database_url=database_url))) as client:
        versions = client.get(f"/manuscripts/{manuscript['id']}/versions").json()
        assert [v["number"] for v in versions] == [1]
        assert client.get(f"/versions/{versions[0]['id']}").json()["content"] == "Texto original."


def test_la_copia_mantiene_la_inmutabilidad(tmp_path: Path, database_url: str) -> None:
    """Una base restaurada conserva los triggers: la protección no depende de la aplicación."""
    import sqlite3
    from contextlib import closing

    live = Path(database_url.removeprefix("sqlite:///"))
    backup = tmp_path / "copia.sqlite"
    shutil.copyfile(live, backup)
    shutil.copyfile(backup, tmp_path / "restaurada.sqlite")
    with closing(sqlite3.connect(tmp_path / "restaurada.sqlite")) as connection:
        names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
    assert "trg_manuscript_versions_no_update" in names
