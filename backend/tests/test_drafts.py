"""Borradores persistentes, escritura condicional, puntos de recuperación y restauración.

Todas las pruebas son deterministas: el tiempo se controla con ``FakeClock`` y las
concurrencias se reproducen con dos sesiones en orden fijo. No hay esperas.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.drafts.errors import DraftConflict
from app.drafts.service import DraftService
from app.main import create_app
from app.projects.service import ProjectService
from app.texts.service import TextService


class FakeClock:
    """Reloj controlable. Sustituye a ``app.state.clock``."""

    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, 12, 0, 0)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def api(client: TestClient, clock: FakeClock) -> TestClient:
    client.app.state.clock = clock
    return client


def _save(api: TestClient, manuscript_id: int, content: str, base_revision: int):
    return api.put(
        f"/manuscripts/{manuscript_id}/draft",
        json={"content": content, "base_revision": base_revision},
    )


def _draft_rows(settings: Settings, manuscript_id: int) -> int:
    db_path = Path(settings.database_url.removeprefix("sqlite:///"))
    with closing(sqlite3.connect(db_path)) as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM manuscript_drafts WHERE manuscript_id = ?", (manuscript_id,)
        ).fetchone()
    return row[0]


def _points(api: TestClient, manuscript_id: int) -> list[dict]:
    response = api.get(f"/manuscripts/{manuscript_id}/recovery-points")
    assert response.status_code == 200
    return response.json()


# 1. Autoguardado persistido -------------------------------------------------


def test_autoguardado_queda_persistido(api: TestClient, service: TextService, settings: Settings) -> None:
    manuscript = service.create_manuscript("Novela", "Texto inicial.", None)
    init = api.post(f"/manuscripts/{manuscript.id}/draft")
    assert init.status_code == 200
    assert init.json()["created"] is True
    assert init.json()["draft"]["revision"] == 1

    saved = _save(api, manuscript.id, "Texto escrito después.", 1)
    assert saved.status_code == 200
    assert saved.json()["revision"] == 2

    with TestClient(create_app(settings)) as otro:
        assert otro.get(f"/manuscripts/{manuscript.id}/draft").json()["content"] == "Texto escrito después."


# 2. Recarga recupera el último borrador -------------------------------------


def test_recargar_recupera_el_ultimo_borrador(api: TestClient, service: TextService, settings: Settings) -> None:
    manuscript = service.create_manuscript("Novela", "Uno.", None)
    api.post(f"/manuscripts/{manuscript.id}/draft")
    _save(api, manuscript.id, "Dos.", 1)
    _save(api, manuscript.id, "Tres.", 2)

    with TestClient(create_app(settings)) as recargada:
        draft = recargada.get(f"/manuscripts/{manuscript.id}/draft").json()
    assert draft["content"] == "Tres."
    assert draft["revision"] == 3


# 3. Guardado antiguo no sobrescribe ----------------------------------------


def test_guardado_con_revision_antigua_no_sobrescribe(api: TestClient, service: TextService) -> None:
    manuscript = service.create_manuscript("Novela", "Base.", None)
    api.post(f"/manuscripts/{manuscript.id}/draft")
    assert _save(api, manuscript.id, "Versión B, la más reciente.", 1).status_code == 200

    rechazado = _save(api, manuscript.id, "Versión A, enviada tarde.", 1)
    assert rechazado.status_code == 409
    body = rechazado.json()
    assert body["code"] == "draft_conflict"
    assert body["current_revision"] == 2
    assert body["current_content"] == "Versión B, la más reciente."
    assert body["preserved_point_id"] is not None

    draft = api.get(f"/manuscripts/{manuscript.id}/draft").json()
    assert draft["content"] == "Versión B, la más reciente."
    assert draft["revision"] == 2

    preserved = api.get(f"/manuscripts/{manuscript.id}/recovery-points/{body['preserved_point_id']}").json()
    assert preserved["reason"] == "conflicto"
    assert preserved["content"] == "Versión A, enviada tarde."


def test_escritura_obsoleta_pierde_aunque_supere_la_comprobacion_previa(
    session_factory: sessionmaker[Session], service: TextService, settings: Settings, clock: FakeClock
) -> None:
    """La protección real es la escritura condicional, no la lectura previa.

    Se simula una lectura obsoleta: el servicio cree que su revisión es la 1, pero la
    base ya está en la 2. La sentencia ``UPDATE ... WHERE revision = 1`` no debe aplicarse.
    """
    manuscript = service.create_manuscript("Novela", "Base.", None)
    with session_factory() as sesion_a, session_factory() as sesion_b:
        servicio_a = DraftService(sesion_a, settings.max_version_chars, clock)
        servicio_b = DraftService(sesion_b, settings.max_version_chars, clock)
        draft, _ = servicio_a.init_draft(manuscript.id)
        obsoleto = SimpleNamespace(id=draft.id, revision=1)

        servicio_a.save(manuscript.id, "Escrito por A.", 1)

        lecturas = {"primera": True}
        cargar_real = servicio_b._load_draft

        def primera_lectura_obsoleta(manuscript_id: int):
            if lecturas["primera"]:
                lecturas["primera"] = False
                return obsoleto
            return cargar_real(manuscript_id)

        servicio_b._load_draft = primera_lectura_obsoleta  # type: ignore[method-assign]
        with pytest.raises(DraftConflict) as error:
            servicio_b.save(manuscript.id, "Escrito por B, tarde.", 1)

    assert error.value.payload["current_revision"] == 2
    with session_factory() as control:
        actual = DraftService(control, settings.max_version_chars, clock).get_draft(manuscript.id)
        assert actual.content == "Escrito por A."
        assert actual.revision == 2


# 4. Error de servidor: texto y revisión intactos, sin falso éxito ------------


def test_rechazo_no_cambia_el_borrador_ni_su_revision(
    api: TestClient, service: TextService, settings: Settings
) -> None:
    manuscript = service.create_manuscript("Novela", "Texto conservado.", None)
    api.post(f"/manuscripts/{manuscript.id}/draft")

    demasiado_largo = "x" * (settings.max_version_chars + 1)
    rechazo = _save(api, manuscript.id, demasiado_largo, 1)
    assert rechazo.status_code == 413

    draft = api.get(f"/manuscripts/{manuscript.id}/draft").json()
    assert draft["content"] == "Texto conservado."
    assert draft["revision"] == 1
    assert _points(api, manuscript.id) == []


def test_guardar_sin_borrador_o_en_manuscrito_inexistente_falla(api: TestClient, service: TextService) -> None:
    manuscript = service.create_manuscript("Novela", "Texto.", None)
    assert _save(api, manuscript.id, "Nada.", 1).status_code == 404
    assert _save(api, 999_999, "Nada.", 1).status_code == 404


# 5. Borradores aislados por manuscrito --------------------------------------


def test_borradores_aislados_por_manuscrito(api: TestClient, service: TextService) -> None:
    primero = service.create_manuscript("Primera novela", "Uno.", None)
    segundo = service.create_manuscript("Segunda novela", "Dos.", None)
    api.post(f"/manuscripts/{primero.id}/draft")
    api.post(f"/manuscripts/{segundo.id}/draft")

    _save(api, primero.id, "Uno, editado.", 1)
    assert _save(api, primero.id, "Uno, otra vez.", 2).status_code == 200

    assert api.get(f"/manuscripts/{segundo.id}/draft").json()["content"] == "Dos."
    assert api.get(f"/manuscripts/{segundo.id}/draft").json()["revision"] == 1
    assert api.get(f"/manuscripts/{primero.id}/draft").json()["content"] == "Uno, otra vez."


# 6. Inicializar no destruye el borrador existente ----------------------------


def test_inicializar_no_destruye_ni_duplica_el_borrador(
    api: TestClient, service: TextService, settings: Settings
) -> None:
    manuscript = service.create_manuscript("Novela", "Origen.", None)
    api.post(f"/manuscripts/{manuscript.id}/draft")
    _save(api, manuscript.id, "Trabajo en curso.", 1)

    repetida = api.post(f"/manuscripts/{manuscript.id}/draft").json()
    assert repetida["created"] is False
    assert repetida["draft"]["content"] == "Trabajo en curso."
    assert repetida["draft"]["revision"] == 2
    assert _draft_rows(settings, manuscript.id) == 1


def test_get_sin_borrador_devuelve_404_y_no_lo_crea(api: TestClient, service: TextService, settings: Settings) -> None:
    manuscript = service.create_manuscript("Novela", "Origen.", None)
    assert api.get(f"/manuscripts/{manuscript.id}/draft").status_code == 404
    assert _draft_rows(settings, manuscript.id) == 0


# 7. Restaurar conserva el estado previo y las versiones formales -------------


def test_restaurar_conserva_el_estado_previo_y_las_versiones(
    api: TestClient, service: TextService
) -> None:
    manuscript = service.create_manuscript("Novela", "Versión formal.", None)
    service.add_version(manuscript.id, "Segunda versión formal.", None, based_on_version_id=None)
    versiones_antes = api.get(f"/manuscripts/{manuscript.id}/versions").json()

    api.post(f"/manuscripts/{manuscript.id}/draft")
    _save(api, manuscript.id, "Borrador dos.", 1)
    _save(api, manuscript.id, "Borrador tres.", 2)

    punto = next(p for p in _points(api, manuscript.id) if p["draft_revision"] == 2)
    restaurado = api.post(
        f"/manuscripts/{manuscript.id}/recovery-points/{punto['id']}/restore",
        json={"base_revision": 3},
    )
    assert restaurado.status_code == 200
    assert restaurado.json()["content"] == "Borrador dos."
    assert restaurado.json()["revision"] == 4

    motivos = [p["reason"] for p in _points(api, manuscript.id)]
    assert "antes_de_restaurar" in motivos
    previo = next(p for p in _points(api, manuscript.id) if p["reason"] == "antes_de_restaurar")
    assert api.get(f"/manuscripts/{manuscript.id}/recovery-points/{previo['id']}").json()["content"] == "Borrador tres."

    assert api.get(f"/manuscripts/{manuscript.id}/versions").json() == versiones_antes


def test_restaurar_con_revision_antigua_no_cambia_nada(api: TestClient, service: TextService) -> None:
    manuscript = service.create_manuscript("Novela", "Base.", None)
    api.post(f"/manuscripts/{manuscript.id}/draft")
    _save(api, manuscript.id, "Primero.", 1)
    _save(api, manuscript.id, "Segundo.", 2)
    punto = _points(api, manuscript.id)[0]

    rechazo = api.post(
        f"/manuscripts/{manuscript.id}/recovery-points/{punto['id']}/restore",
        json={"base_revision": 2},
    )
    assert rechazo.status_code == 409
    assert api.get(f"/manuscripts/{manuscript.id}/draft").json()["content"] == "Segundo."


def test_punto_de_otro_manuscrito_no_se_puede_restaurar(api: TestClient, service: TextService) -> None:
    primero = service.create_manuscript("Primera", "Uno.", None)
    segundo = service.create_manuscript("Segunda", "Dos.", None)
    for manuscript in (primero, segundo):
        api.post(f"/manuscripts/{manuscript.id}/draft")
    _save(api, primero.id, "Uno editado.", 1)
    punto_ajeno = _points(api, primero.id)[0]

    respuesta = api.post(
        f"/manuscripts/{segundo.id}/recovery-points/{punto_ajeno['id']}/restore",
        json={"base_revision": 1},
    )
    assert respuesta.status_code == 404
    assert api.get(f"/manuscripts/{segundo.id}/draft").json()["content"] == "Dos."


# 8. Cambiar de manuscrito con escrituras pendientes no pierde nada ----------


def test_escrituras_intercaladas_entre_manuscritos_no_se_pierden(api: TestClient, service: TextService) -> None:
    """Simula el cambio de manuscrito: escrituras de A, de B y de A otra vez, en ese orden."""
    a = service.create_manuscript("A", "A0.", None)
    b = service.create_manuscript("B", "B0.", None)
    for manuscript in (a, b):
        api.post(f"/manuscripts/{manuscript.id}/draft")

    assert _save(api, a.id, "A1, pendiente.", 1).status_code == 200
    assert _save(api, b.id, "B1.", 1).status_code == 200
    assert _save(api, a.id, "A2, pendiente.", 2).status_code == 200

    assert api.get(f"/manuscripts/{a.id}/draft").json()["content"] == "A2, pendiente."
    assert api.get(f"/manuscripts/{b.id}/draft").json()["content"] == "B1."


# 9. Migraciones: ver tests/test_migraciones_borradores.py ------------------


# 10. Proyecto archivado conserva el comportamiento actual -------------------


def test_proyecto_archivado_conserva_su_borrador_y_su_comportamiento(
    api: TestClient, session: Session, service: TextService, settings: Settings
) -> None:
    proyectos = ProjectService(session, service)
    proyecto = proyectos.create_project("Proyecto con borrador")
    manuscript = service.create_manuscript("En proyecto", "Texto.", None, project_id=proyecto.id)
    api.post(f"/manuscripts/{manuscript.id}/draft")
    _save(api, manuscript.id, "Texto editado.", 1)

    proyectos.archive_project(proyecto.id)
    assert api.get(f"/manuscripts/{manuscript.id}/draft").json()["content"] == "Texto editado."
    assert _save(api, manuscript.id, "Texto editado en archivo.", 2).status_code == 200

    proyectos.restore_project(proyecto.id)
    assert api.get(f"/manuscripts/{manuscript.id}/draft").json()["revision"] == 3


# 11. Sin exceso de puntos durante la escritura normal -----------------------


def test_escritura_normal_no_genera_puntos_duplicados(api: TestClient, service: TextService, clock: FakeClock) -> None:
    manuscript = service.create_manuscript("Novela", "", None)
    api.post(f"/manuscripts/{manuscript.id}/draft")

    texto = ""
    revision = 1
    for _ in range(60):
        clock.advance(1)
        texto += "a"
        assert _save(api, manuscript.id, texto, revision).status_code == 200
        revision += 1
    assert len(_points(api, manuscript.id)) == 1  # solo el primer guardado

    clock.advance(300)
    texto += "b"
    assert _save(api, manuscript.id, texto, revision).status_code == 200
    revision += 1
    assert len(_points(api, manuscript.id)) == 2  # periódico tras cinco minutos

    clock.advance(60)
    texto += "c" * 600
    assert _save(api, manuscript.id, texto, revision).status_code == 200
    motivos = [p["reason"] for p in reversed(_points(api, manuscript.id))]
    assert motivos == ["periodico", "periodico", "significativo"]


def test_cambio_grande_antes_de_un_minuto_no_crea_punto_significativo(
    api: TestClient, service: TextService, clock: FakeClock
) -> None:
    manuscript = service.create_manuscript("Novela", "", None)
    api.post(f"/manuscripts/{manuscript.id}/draft")
    _save(api, manuscript.id, "a", 1)
    clock.advance(30)
    _save(api, manuscript.id, "a" * 600, 2)
    assert len(_points(api, manuscript.id)) == 1


# Concurrencia: pedidos desordenados -----------------------------------------


def test_pedidos_desordenados_no_se_aplican_fuera_de_orden(api: TestClient, service: TextService) -> None:
    """La escritura de la revisión 2 llega antes que la de la 1 (orden de red invertido)."""
    manuscript = service.create_manuscript("Novela", "Inicio.", None)
    api.post(f"/manuscripts/{manuscript.id}/draft")
    assert _save(api, manuscript.id, "Segunda, llega primero.", 2).status_code == 409
    assert _save(api, manuscript.id, "Primera, llega después.", 1).status_code == 200
    draft = api.get(f"/manuscripts/{manuscript.id}/draft").json()
    assert draft["revision"] == 2
    assert draft["content"] == "Primera, llega después."


# Mantener el texto propio tras un conflicto no pierde el guardado anterior ---


def test_mantener_mi_texto_conserva_el_guardado_anterior(api: TestClient, service: TextService) -> None:
    manuscript = service.create_manuscript("Novela", "Origen.", None)
    api.post(f"/manuscripts/{manuscript.id}/draft")
    _save(api, manuscript.id, "Guardado por otra ventana.", 1)

    rechazo = _save(api, manuscript.id, "Mi texto.", 1)
    actual = rechazo.json()["current_revision"]
    assert rechazo.status_code == 409

    respuesta = api.put(
        f"/manuscripts/{manuscript.id}/draft",
        json={"content": "Mi texto.", "base_revision": actual, "keep_previous": True},
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["content"] == "Mi texto."
    previos = [p for p in _points(api, manuscript.id) if p["reason"] == "antes_de_sobrescribir"]
    assert len(previos) == 1
    detalle = api.get(f"/manuscripts/{manuscript.id}/recovery-points/{previos[0]['id']}").json()
    assert detalle["content"] == "Guardado por otra ventana."
