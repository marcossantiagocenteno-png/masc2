"""Auditoría E4 del backend: aislamiento entre proyectos, ids no válidos, mapeo de errores,
atomicidad de las escrituras fallidas, duplicados y persistencia.

Usa la base temporal migrada (fixtures ``settings``, ``client``, ``session``). Las pruebas que buscan
errores 500 usan un cliente que no relanza excepciones, para ver el código HTTP real que recibiría un
navegador y no un error lanzado dentro del cliente de pruebas.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db.models import (
    AssistantProposal,
    Character,
    DraftRecoveryPoint,
    EditorialReview,
    Manuscript,
    ManuscriptDraft,
    ManuscriptVersion,
    NarrativeDecision,
    NarrativeLink,
    Project,
    ProjectGenre,
    ReviewItem,
    StructureNode,
    StructureProposal,
)
from app.main import create_app

TEXTO = "Lucía abre la puerta. Nadie responde en la casa vacía."
CITA_OK = {"kind": "observacion", "quote": "Lucía abre la puerta.", "start_offset": 0, "end_offset": 21, "comment": "Buen inicio."}
CITA_MALA = {"kind": "observacion", "quote": "Esto no está", "start_offset": 0, "end_offset": 12, "comment": "Cita falsa."}
MAL_IDS = ["0", "-1", "999999", str(2**63), "99999999999999999999", "abc", "1.5"]


@pytest.fixture
def api_seguro(settings: Settings) -> Iterator[TestClient]:
    """Cliente que devuelve el 500 real en vez de relanzar la excepción."""
    with TestClient(create_app(settings), raise_server_exceptions=False) as test_client:
        yield test_client


@dataclass
class Mundo:
    a: int
    b: int
    m: int
    v: int
    punto: int
    personaje: int
    acto: int
    escena: int
    vinculo: int
    prop_est: int
    prop_asis: int
    analisis: int
    revision: int


@pytest.fixture
def mundo(client: TestClient) -> Mundo:
    """Dos novelas. Todo lo creado aquí pertenece a la novela A; la B está vacía."""
    a = client.post("/projects", json={"name": "Novela A"}).json()["id"]
    b = client.post("/projects", json={"name": "Novela B"}).json()["id"]
    m = client.post(f"/projects/{a}/manuscripts", json={"title": "Cap A", "content": TEXTO}).json()["id"]
    v = client.get(f"/projects/{a}/manuscripts/{m}/versions").json()[0]["id"]
    assert client.post(f"/projects/{a}/manuscripts/{m}/draft").json()["created"] is True
    assert client.put(f"/projects/{a}/manuscripts/{m}/draft", json={"content": TEXTO + " Fin.", "base_revision": 1}).status_code == 200
    punto = client.get(f"/projects/{a}/manuscripts/{m}/recovery-points").json()[0]["id"]
    revision = client.post(
        f"/projects/{a}/manuscripts/{m}/versions/{v}/reviews", json={"reviewer": "Ana", "items": [CITA_OK]}
    ).json()["id"]
    analisis = client.post(
        f"/projects/{a}/manuscripts/{m}/versions/{v}/analyses", json={"start_offset": 0, "end_offset": 21}
    ).json()["id"]
    personaje = client.post(f"/projects/{a}/planificacion/personajes", json={"name": "Lucía"}).json()["id"]
    acto = client.post(f"/projects/{a}/planificacion/estructura", json={"kind": "acto", "title": "Acto I"}).json()["id"]
    escena = client.post(
        f"/projects/{a}/planificacion/estructura", json={"kind": "escena", "parent_id": acto, "title": "Escena 1"}
    ).json()["id"]
    assert client.post(f"/projects/{a}/planificacion/estructura/{escena}/escritura").status_code == 201
    vinculo = client.post(
        f"/projects/{a}/planificacion/vinculos",
        json={"origen": {"tipo": "personaje", "id": personaje}, "destino": {"tipo": "escena", "id": escena}, "relacion": "participa_en"},
    ).json()["id"]
    assert client.put(f"/projects/{a}/planificacion/estructura-recomendada/modelo", json={"model_key": "freytag"}).status_code == 200
    prop_est = client.post(f"/projects/{a}/planificacion/estructura-recomendada/propuestas", json={}).json()[0]["id"]
    prop_asis = client.post(
        f"/projects/{a}/asistente/mensajes", json={"client_id": "cliente-a-0001", "texto": "crea un personaje llamado Mara"}
    ).json()["propuestas"][0]["id"]
    return Mundo(a, b, m, v, punto, personaje, acto, escena, vinculo, prop_est, prop_asis, analisis, revision)


# Rutas con identificadores de la novela A. Cada una debe responder 404 cuando se llama con la novela B.
ISOLATION_CASES: list[tuple[str, str, Any]] = [
    ("GET", "/projects/{p}/manuscripts/{m}", None),
    ("GET", "/projects/{p}/manuscripts/{m}/versions", None),
    ("GET", "/projects/{p}/manuscripts/{m}/versions/{v}", None),
    ("POST", "/projects/{p}/manuscripts/{m}/versions", {"content": "Intruso."}),
    ("GET", "/projects/{p}/manuscripts/{m}/draft", None),
    ("POST", "/projects/{p}/manuscripts/{m}/draft", None),
    ("PUT", "/projects/{p}/manuscripts/{m}/draft", {"content": "Intruso.", "base_revision": 2}),
    ("GET", "/projects/{p}/manuscripts/{m}/recovery-points", None),
    ("GET", "/projects/{p}/manuscripts/{m}/recovery-points/{punto}", None),
    ("POST", "/projects/{p}/manuscripts/{m}/recovery-points/{punto}/restore", {"base_revision": 2}),
    ("POST", "/projects/{p}/manuscripts/{m}/versions/{v}/analyses", {"start_offset": 0, "end_offset": 5}),
    ("GET", "/projects/{p}/manuscripts/{m}/versions/{v}/analyses", None),
    ("POST", "/projects/{p}/manuscripts/{m}/versions/{v}/reviews", {"reviewer": "Intruso", "items": [CITA_OK]}),
    ("GET", "/projects/{p}/manuscripts/{m}/versions/{v}/reviews", None),
    ("GET", "/projects/{p}/planificacion/personajes/{personaje}", None),
    ("PATCH", "/projects/{p}/planificacion/personajes/{personaje}", {"name": "Intruso"}),
    ("POST", "/projects/{p}/planificacion/personajes/{personaje}/archivar", None),
    ("POST", "/projects/{p}/planificacion/personajes/{personaje}/aprobar", {"confirmar": True}),
    ("POST", "/projects/{p}/planificacion/personajes/{personaje}/aceptar-propuesta", None),
    ("GET", "/projects/{p}/planificacion/personajes/{personaje}/decisiones", None),
    ("GET", "/projects/{p}/planificacion/personajes/{personaje}/vinculos", None),
    ("GET", "/projects/{p}/planificacion/estructura/{acto}", None),
    ("PATCH", "/projects/{p}/planificacion/estructura/{acto}", {"title": "Intruso"}),
    ("POST", "/projects/{p}/planificacion/estructura/{acto}/archivar", None),
    ("POST", "/projects/{p}/planificacion/estructura/{acto}/aprobar", {"confirmar": True}),
    ("POST", "/projects/{p}/planificacion/estructura/{acto}/mover", {"parent_id": None}),
    ("GET", "/projects/{p}/planificacion/estructura/{acto}/decisiones", None),
    ("GET", "/projects/{p}/planificacion/estructura/{acto}/vinculos", None),
    ("POST", "/projects/{p}/planificacion/estructura", {"kind": "escena", "parent_id": "{acto}", "title": "Intrusa"}),
    ("GET", "/projects/{p}/planificacion/estructura/{escena}/escritura", None),
    ("POST", "/projects/{p}/planificacion/estructura/{escena}/escritura", None),
    ("PUT", "/projects/{p}/planificacion/estructura/{escena}/escritura/borrador", {"content": "Intruso.", "base_revision": 1}),
    ("GET", "/projects/{p}/planificacion/vinculos/{vinculo}", None),
    ("POST", "/projects/{p}/planificacion/vinculos/{vinculo}/archivar", None),
    ("POST", "/projects/{p}/planificacion/vinculos/{vinculo}/aprobar", {"confirmar": True}),
    ("POST", "/projects/{p}/planificacion/vinculos", {
        "origen": {"tipo": "personaje", "id": "{personaje}"}, "destino": {"tipo": "escena", "id": "{escena}"}, "relacion": "participa_en"}),
    ("PATCH", "/projects/{p}/planificacion/estructura-recomendada/propuestas/{prop_est}", {"title": "Intruso"}),
    ("POST", "/projects/{p}/planificacion/estructura-recomendada/propuestas/{prop_est}/aceptar", None),
    ("POST", "/projects/{p}/planificacion/estructura-recomendada/propuestas/{prop_est}/rechazar", None),
    ("POST", "/projects/{p}/asistente/propuestas/{prop_asis}/aprobar", None),
    ("POST", "/projects/{p}/asistente/propuestas/{prop_asis}/rechazar", None),
    ("POST", "/projects/{p}/asistente/autocompletar/vista-previa",
        {"entidad": "personaje", "campo": "description", "entidad_id": "{personaje}", "actual": "", "instruccion": None}),
]


def _ruta(plantilla: str, valores: dict[str, Any]) -> str:
    return plantilla.format(**{k: str(v) for k, v in valores.items()})


def _cuerpo(cuerpo: Any, valores: dict[str, Any]) -> Any:
    """Sustituye los marcadores ``"{clave}"`` del cuerpo por ids numéricos (o por el texto dado)."""
    if isinstance(cuerpo, dict):
        return {k: _cuerpo(v, valores) for k, v in cuerpo.items()}
    if isinstance(cuerpo, list):
        return [_cuerpo(v, valores) for v in cuerpo]
    if isinstance(cuerpo, str) and cuerpo.startswith("{") and cuerpo.endswith("}"):
        return valores[cuerpo[1:-1]]
    return cuerpo


def _valores(mundo: Mundo, proyecto: int) -> dict[str, Any]:
    return {
        "p": proyecto, "m": mundo.m, "v": mundo.v, "punto": mundo.punto, "personaje": mundo.personaje,
        "acto": mundo.acto, "escena": mundo.escena, "vinculo": mundo.vinculo,
        "prop_est": mundo.prop_est, "prop_asis": mundo.prop_asis,
    }


def _llamar(client: TestClient, metodo: str, ruta: str, cuerpo: Any) -> Any:
    if cuerpo is None:
        return client.request(metodo, ruta)
    return client.request(metodo, ruta, json=cuerpo)


# ---------------------------------------------------------------------------
# 1. Aislamiento entre proyectos
# ---------------------------------------------------------------------------


def test_ids_de_la_novela_a_bajo_la_novela_b_dan_404_y_no_cambian_nada(
    client: TestClient, session_factory: sessionmaker[Session], mundo: Mundo
) -> None:
    fallos: list[str] = []
    for metodo, plantilla, cuerpo in ISOLATION_CASES:
        ruta = _ruta(plantilla, _valores(mundo, mundo.b))
        respuesta = _llamar(client, metodo, ruta, _cuerpo(cuerpo, _valores(mundo, mundo.b)))
        if respuesta.status_code != 404:
            fallos.append(f"{metodo} {ruta} -> {respuesta.status_code} {respuesta.text[:120]}")
    assert fallos == []

    with session_factory() as nueva:
        assert nueva.get(Manuscript, mundo.m).project_id == mundo.a
        assert nueva.get(ManuscriptDraft, nueva.scalar(select(ManuscriptDraft.id))).revision == 2
        assert nueva.scalar(select(func.count(DraftRecoveryPoint.id))) == 1
        assert nueva.scalar(select(func.count(EditorialReview.id))) == 1
        assert nueva.scalar(select(func.count(ReviewItem.id))) == 1
        assert nueva.scalar(select(func.count(NarrativeDecision.id))) == 0
        assert nueva.scalar(select(func.count(NarrativeLink.id))) == 1
        assert nueva.scalar(select(StructureNode.archived_at).where(StructureNode.id == mundo.acto)) is None
        assert nueva.get(AssistantProposal, mundo.prop_asis).estado == "pendiente"
        assert nueva.get(StructureProposal, mundo.prop_est).estado == "pendiente"
        assert nueva.scalar(select(func.count(StructureNode.id)).where(StructureNode.project_id == mundo.b)) == 0


def test_los_ids_de_otra_novela_no_aparecen_en_los_listados_de_la_novela_b(client: TestClient, mundo: Mundo) -> None:
    assert client.get(f"/projects/{mundo.b}/manuscripts").status_code == 200
    assert client.get(f"/projects/{mundo.b}/manuscripts").json() == []
    assert client.get(f"/projects/{mundo.b}/planificacion/personajes").json() == []
    assert client.get(f"/projects/{mundo.b}/planificacion/estructura").json() == []
    assert client.get(f"/projects/{mundo.b}/planificacion/vinculos").json() == []
    assert client.get(f"/projects/{mundo.b}/planificacion/estructura-recomendada").json()["propuestas"] == []
    assert client.get(f"/projects/{mundo.b}/asistente/propuestas").json() == []
    assert client.get(f"/projects/{mundo.b}/asistente/memoria").json() == []


def test_archivar_o_restaurar_la_novela_b_no_toca_a_la_a(client: TestClient, mundo: Mundo) -> None:
    assert client.post(f"/projects/{mundo.b}/archive").status_code == 200
    assert client.get(f"/projects/{mundo.a}").json()["status"] == "activo"
    assert client.post(f"/projects/{mundo.a}/manuscripts", json={"title": "Nuevo", "content": "x"}).status_code == 201


# ---------------------------------------------------------------------------
# 2. Identificadores no válidos: nunca 500
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("valor", MAL_IDS)
def test_ids_no_validos_en_todas_las_rutas_dan_404_o_422(api_seguro: TestClient, mundo: Mundo, valor: str) -> None:
    valores = {k: valor for k in _valores(mundo, 0)}
    fallos: list[str] = []
    for metodo, plantilla, cuerpo in ISOLATION_CASES:
        ruta = _ruta(plantilla, valores)
        respuesta = _llamar(api_seguro, metodo, ruta, _cuerpo(cuerpo, valores) if cuerpo else None)
        if respuesta.status_code not in (404, 422):
            fallos.append(f"{metodo} {ruta} -> {respuesta.status_code}")
    assert fallos == []


@pytest.mark.parametrize(
    "metodo, ruta, cuerpo",
    [
        ("GET", "/projects/{p}", None),
        ("PATCH", "/projects/{p}", {"name": "X"}),
        ("POST", "/projects/{p}/archive", None),
        ("POST", "/projects/{p}/restore", None),
        ("GET", "/projects/{p}/manuscripts", None),
        ("POST", "/projects/{p}/manuscripts", {"title": "X", "content": "x"}),
        ("GET", "/projects/{p}/planificacion/narrativa", None),
        ("PATCH", "/projects/{p}/planificacion/narrativa", {"premise": "x"}),
        ("PUT", "/projects/{p}/planificacion/generos", {"generos": []}),
        ("GET", "/projects/{p}/planificacion/estructura-recomendada", None),
        ("PUT", "/projects/{p}/planificacion/estructura-recomendada/modelo", {"model_key": "freytag"}),
        ("POST", "/projects/{p}/planificacion/estructura-recomendada/propuestas", {}),
        ("POST", "/projects/{p}/planificacion/estructura/reordenar", {"parent_id": None, "orden": []}),
        ("POST", "/projects/{p}/planificacion/estructura", {"kind": "acto"}),
        ("GET", "/projects/{p}/asistente", None),
        ("GET", "/projects/{p}/asistente/propuestas", None),
        ("GET", "/projects/{p}/asistente/memoria", None),
        ("POST", "/projects/{p}/asistente/mensajes", {"client_id": "cliente-x-0001", "texto": "hola"}),
    ],
)
@pytest.mark.parametrize("valor", MAL_IDS)
def test_ids_no_validos_en_rutas_de_proyecto_y_planificacion(
    api_seguro: TestClient, metodo: str, ruta: str, cuerpo: Any, valor: str
) -> None:
    respuesta = _llamar(api_seguro, metodo, ruta.format(p=valor), cuerpo)
    assert respuesta.status_code in (404, 422), f"{metodo} {ruta} con {valor!r}: {respuesta.status_code}"


@pytest.mark.parametrize("valor", ["99999999999999999999", str(2**63)])
def test_id_enorme_en_cuerpo_no_provoca_500(api_seguro: TestClient, mundo: Mundo, valor: str) -> None:
    """Un id mayor que el entero de 64 bits no debe llegar a la base de datos sin validar."""
    casos = [
        (f"/projects/{mundo.a}/manuscripts/{mundo.m}/versions", {"content": "x", "based_on_version_id": int(valor)}),
        (f"/projects/{mundo.a}/planificacion/vinculos", {
            "origen": {"tipo": "personaje", "id": int(valor)},
            "destino": {"tipo": "escena", "id": mundo.escena}, "relacion": "participa_en"}),
        (f"/projects/{mundo.a}/planificacion/estructura/{mundo.escena}/mover", {"parent_id": int(valor)}),
    ]
    for ruta, cuerpo in casos:
        respuesta = api_seguro.post(ruta, json=cuerpo)
        assert respuesta.status_code in (404, 422), f"{ruta}: {respuesta.status_code}"


def test_proyecto_inexistente_en_escrituras_de_estructura_responde_404(api_seguro: TestClient) -> None:
    """``_structure_version`` lee la revisión antes de comprobar el proyecto: sin esto, un 500."""
    assert api_seguro.post("/projects/987654/planificacion/estructura", json={"kind": "acto"}).status_code == 404
    assert api_seguro.post("/projects/987654/planificacion/estructura/reordenar", json={"orden": []}).status_code == 404
    assert api_seguro.post("/projects/987654/planificacion/estructura/1/mover", json={}).status_code == 404
    assert api_seguro.post(
        "/projects/987654/planificacion/estructura-recomendada/propuestas/1/aceptar"
    ).status_code == 404


# ---------------------------------------------------------------------------
# 3. Mapeo de errores
# ---------------------------------------------------------------------------


def test_excepcion_inesperada_no_expone_su_mensaje_ni_traceback(
    api_seguro: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.projects.service import ProjectService

    def roto(self: ProjectService, status: str | None = None) -> None:
        raise RuntimeError("secreto interno: ruta /home/usuario/base.sqlite")

    monkeypatch.setattr(ProjectService, "list_projects", roto)
    respuesta = api_seguro.get("/projects")
    assert respuesta.status_code == 500
    cuerpo = respuesta.text
    assert "secreto" not in cuerpo and "Traceback" not in cuerpo and "/home/usuario" not in cuerpo
    assert respuesta.json()["detail"].startswith("Error interno")


@pytest.mark.parametrize(
    "metodo, ruta, cuerpo, estado",
    [
        ("GET", "/projects/999/manuscripts/1", None, 404),
        ("POST", "/projects/{p}/planificacion/estructura", {"kind": "acto", "parent_id": "{escena}"}, 422),
        ("PATCH", "/projects/{p}/planificacion/personajes/{personaje}", {"campo_inventado": 1}, 422),
        ("PUT", "/projects/{p}/manuscripts/{m}/draft", {"content": "x", "base_revision": 99}, 409),
        ("POST", "/projects/{p}/manuscripts/{m}/versions/{v}/analyses", {"start_offset": 5, "end_offset": 3}, 422),
        ("POST", "/projects/{p}/manuscripts/{m}/versions/{v}/reviews", {"reviewer": "Ana", "items": [CITA_MALA]}, 422),
    ],
)
def test_errores_de_dominio_tienen_su_codigo_http(
    client: TestClient, mundo: Mundo, metodo: str, ruta: str, cuerpo: Any, estado: int
) -> None:
    valores = _valores(mundo, mundo.a)
    respuesta = _llamar(client, metodo, _ruta(ruta, valores), _cuerpo(cuerpo, valores) if cuerpo else None)
    assert respuesta.status_code == estado, respuesta.text
    assert "detail" in respuesta.json()


def test_contenido_demasiado_grande_responde_413(settings: Settings, database_url: str) -> None:
    pequeno = Settings(database_url=database_url, max_version_chars=10)
    with TestClient(create_app(pequeno)) as api:
        a = api.post("/projects", json={"name": "Límite"}).json()["id"]
        respuesta = api.post(f"/projects/{a}/manuscripts", json={"title": "T", "content": "x" * 50})
        assert respuesta.status_code == 413


# ---------------------------------------------------------------------------
# 4. Escrituras fallidas: no deben dejar nada a medias
# ---------------------------------------------------------------------------


def test_revision_con_una_cita_falsa_no_guarda_ninguna_cita(
    client: TestClient, session_factory: sessionmaker[Session], mundo: Mundo
) -> None:
    respuesta = client.post(
        f"/projects/{mundo.a}/manuscripts/{mundo.m}/versions/{mundo.v}/reviews",
        json={"reviewer": "Ana", "items": [CITA_OK, CITA_MALA]},
    )
    assert respuesta.status_code == 422
    with session_factory() as nueva:
        assert nueva.scalar(select(func.count(EditorialReview.id))) == 1
        assert nueva.scalar(select(func.count(ReviewItem.id))) == 1


def test_guardado_con_revision_vieja_y_keep_previous_no_crea_punto_ni_sobrescribe(
    client: TestClient, session_factory: sessionmaker[Session], mundo: Mundo
) -> None:
    respuesta = client.put(
        f"/projects/{mundo.a}/manuscripts/{mundo.m}/draft",
        json={"content": "Otro texto.", "base_revision": 1, "keep_previous": True},
    )
    assert respuesta.status_code == 409
    with session_factory() as nueva:
        borrador = nueva.scalar(select(ManuscriptDraft).where(ManuscriptDraft.manuscript_id == mundo.m))
        assert borrador.revision == 2 and borrador.content == TEXTO + " Fin."
        razones = nueva.scalars(select(DraftRecoveryPoint.reason).where(DraftRecoveryPoint.manuscript_id == mundo.m)).all()
        assert "antes_de_sobrescribir" not in razones


def test_restaurar_con_revision_vieja_no_crea_punto_ni_cambia_el_borrador(
    client: TestClient, session_factory: sessionmaker[Session], mundo: Mundo
) -> None:
    respuesta = client.post(
        f"/projects/{mundo.a}/manuscripts/{mundo.m}/recovery-points/{mundo.punto}/restore", json={"base_revision": 1}
    )
    assert respuesta.status_code == 409
    with session_factory() as nueva:
        borrador = nueva.scalar(select(ManuscriptDraft).where(ManuscriptDraft.manuscript_id == mundo.m))
        assert borrador.revision == 2 and borrador.content == TEXTO + " Fin."
        razones = nueva.scalars(select(DraftRecoveryPoint.reason).where(DraftRecoveryPoint.manuscript_id == mundo.m)).all()
        assert "antes_de_restaurar" not in razones


def test_estructura_con_padre_incompatible_no_crea_nodo_ni_avanza_la_revision(
    client: TestClient, session_factory: sessionmaker[Session], mundo: Mundo
) -> None:
    from app.db.models import Project as ProjectModel

    with session_factory() as antes:
        version_antes = antes.get(ProjectModel, mundo.a).structure_version
        total_antes = antes.scalar(select(func.count(StructureNode.id)))
    assert client.post(
        f"/projects/{mundo.a}/planificacion/estructura", json={"kind": "acto", "parent_id": mundo.escena}
    ).status_code == 422
    with session_factory() as despues:
        assert despues.get(ProjectModel, mundo.a).structure_version == version_antes
        assert despues.scalar(select(func.count(StructureNode.id))) == total_antes


def test_reordenar_con_lista_incompleta_no_cambia_posiciones(client: TestClient, session_factory: sessionmaker[Session], mundo: Mundo) -> None:
    segundo = client.post(f"/projects/{mundo.a}/planificacion/estructura", json={"kind": "acto", "title": "Acto II"}).json()["id"]
    antes = client.get(f"/projects/{mundo.a}/planificacion/estructura").json()
    assert client.post(f"/projects/{mundo.a}/planificacion/estructura/reordenar", json={"orden": [segundo]}).status_code == 422
    assert client.get(f"/projects/{mundo.a}/planificacion/estructura").json() == antes


def test_mover_escena_bajo_si_misma_no_cambia_nada(client: TestClient, mundo: Mundo) -> None:
    antes = client.get(f"/projects/{mundo.a}/planificacion/estructura").json()
    respuesta = client.post(
        f"/projects/{mundo.a}/planificacion/estructura/{mundo.escena}/mover", json={"parent_id": mundo.escena}
    )
    assert respuesta.status_code == 422
    assert client.get(f"/projects/{mundo.a}/planificacion/estructura").json() == antes


def test_genero_invalido_no_cambia_la_seleccion(client: TestClient, session_factory: sessionmaker[Session], mundo: Mundo) -> None:
    respuesta = client.put(
        f"/projects/{mundo.a}/planificacion/generos",
        json={"generos": [{"key": "misterio"}, {"key": "no_existe"}]},
    )
    assert respuesta.status_code == 422
    with session_factory() as nueva:
        assert nueva.scalar(select(func.count(ProjectGenre.id)).where(ProjectGenre.project_id == mundo.a)) == 0


def test_vinculo_con_relacion_no_permitida_no_crea_nada(client: TestClient, session_factory: sessionmaker[Session], mundo: Mundo) -> None:
    respuesta = client.post(
        f"/projects/{mundo.a}/planificacion/vinculos",
        json={"origen": {"tipo": "personaje", "id": mundo.personaje}, "destino": {"tipo": "escena", "id": mundo.escena}, "relacion": "inventada"},
    )
    assert respuesta.status_code == 422
    with session_factory() as nueva:
        assert nueva.scalar(select(func.count(NarrativeLink.id))) == 1


def test_patch_con_campo_desconocido_no_modifica_el_personaje(client: TestClient, mundo: Mundo) -> None:
    respuesta = client.patch(f"/projects/{mundo.a}/planificacion/personajes/{mundo.personaje}", json={"name": "Otra", "extra": 1})
    assert respuesta.status_code == 422
    assert client.get(f"/projects/{mundo.a}/planificacion/personajes/{mundo.personaje}").json()["name"] == "Lucía"


def test_manuscrito_en_proyecto_archivado_no_se_crea(client: TestClient, session_factory: sessionmaker[Session], mundo: Mundo) -> None:
    assert client.post(f"/projects/{mundo.b}/archive").status_code == 200
    assert client.post(f"/projects/{mundo.b}/manuscripts", json={"title": "T", "content": "x"}).status_code == 422
    with session_factory() as nueva:
        assert nueva.scalar(select(func.count(Manuscript.id)).where(Manuscript.project_id == mundo.b)) == 0


# ---------------------------------------------------------------------------
# 5. Duplicados donde el dominio lo promete
# ---------------------------------------------------------------------------


def test_aceptar_dos_veces_una_propuesta_de_estructura_no_duplica_el_acto(
    client: TestClient, session_factory: sessionmaker[Session], mundo: Mundo
) -> None:
    primera = client.post(f"/projects/{mundo.a}/planificacion/estructura-recomendada/propuestas/{mundo.prop_est}/aceptar")
    segunda = client.post(f"/projects/{mundo.a}/planificacion/estructura-recomendada/propuestas/{mundo.prop_est}/aceptar")
    assert primera.status_code == 200
    assert segunda.status_code == 422
    with session_factory() as nueva:
        actos = nueva.scalar(
            select(func.count(StructureNode.id)).where(
                StructureNode.project_id == mundo.a, StructureNode.title == "Acto I"
            )
        )
        assert actos == 1


def test_aprobar_dos_veces_un_elemento_responde_409_y_registra_una_decision(
    client: TestClient, session_factory: sessionmaker[Session], mundo: Mundo
) -> None:
    url = f"/projects/{mundo.a}/planificacion/personajes/{mundo.personaje}/aprobar"
    assert client.post(url, json={"confirmar": True}).status_code == 200
    assert client.post(url, json={"confirmar": True}).status_code == 409
    with session_factory() as nueva:
        assert nueva.scalar(select(func.count(NarrativeDecision.id)).where(NarrativeDecision.accion == "aprobar_canon")) == 1


def test_iniciar_la_escritura_de_una_escena_dos_veces_no_duplica_el_manuscrito(
    client: TestClient, session_factory: sessionmaker[Session], mundo: Mundo
) -> None:
    url = f"/projects/{mundo.a}/planificacion/estructura/{mundo.escena}/escritura"
    segunda = client.post(url)
    assert segunda.status_code == 200
    with session_factory() as nueva:
        assert nueva.scalar(select(func.count(Manuscript.id)).where(Manuscript.project_id == mundo.a)) == 2


def test_crear_el_borrador_dos_veces_devuelve_el_existente(client: TestClient, mundo: Mundo) -> None:
    respuesta = client.post(f"/projects/{mundo.a}/manuscripts/{mundo.m}/draft")
    assert respuesta.status_code == 200 and respuesta.json()["created"] is False
    assert respuesta.json()["draft"]["revision"] == 2


def test_vinculo_repetido_responde_409(client: TestClient, mundo: Mundo) -> None:
    respuesta = client.post(
        f"/projects/{mundo.a}/planificacion/vinculos",
        json={"origen": {"tipo": "personaje", "id": mundo.personaje}, "destino": {"tipo": "escena", "id": mundo.escena}, "relacion": "participa_en"},
    )
    assert respuesta.status_code == 409


def test_generar_propuestas_con_lote_pendiente_responde_409(client: TestClient, session_factory: sessionmaker[Session], mundo: Mundo) -> None:
    with session_factory() as antes:
        total = antes.scalar(select(func.count(StructureProposal.id)))
    assert client.post(f"/projects/{mundo.a}/planificacion/estructura-recomendada/propuestas", json={}).status_code == 409
    with session_factory() as despues:
        assert despues.scalar(select(func.count(StructureProposal.id))) == total


def test_aprobar_dos_veces_una_propuesta_del_asistente_no_duplica_el_personaje(
    client: TestClient, session_factory: sessionmaker[Session], mundo: Mundo
) -> None:
    url = f"/projects/{mundo.a}/asistente/propuestas/{mundo.prop_asis}/aprobar"
    primera = client.post(url).json()
    segunda = client.post(url).json()
    assert primera["resultado_id"] == segunda["resultado_id"]
    with session_factory() as nueva:
        assert nueva.scalar(select(func.count(Character.id)).where(Character.name == "Mara")) == 1


# ---------------------------------------------------------------------------
# 6. Persistencia: lo confirmado se ve desde una sesión nueva
# ---------------------------------------------------------------------------


def test_las_escrituras_confirmadas_son_visibles_desde_una_sesion_nueva(
    client: TestClient, session_factory: sessionmaker[Session], mundo: Mundo
) -> None:
    assert client.patch(f"/projects/{mundo.a}/planificacion/personajes/{mundo.personaje}", json={"name": "Lucía M."}).status_code == 200
    assert client.put(
        f"/projects/{mundo.a}/manuscripts/{mundo.m}/draft", json={"content": "Texto final.", "base_revision": 2}
    ).status_code == 200
    with session_factory() as nueva:
        assert nueva.get(Character, mundo.personaje).name == "Lucía M."
        borrador = nueva.scalar(select(ManuscriptDraft).where(ManuscriptDraft.manuscript_id == mundo.m))
        assert borrador.content == "Texto final." and borrador.revision == 3
        assert nueva.get(Project, mundo.a).name == "Novela A"


def test_aprobar_una_propuesta_sobre_un_canon_queda_fallida_y_no_cambia_el_elemento(
    client: TestClient, session_factory: sessionmaker[Session], settings: Settings, mundo: Mundo
) -> None:
    """La propuesta se creó sobre un personaje provisional; después el autor lo aprobó como canon.
    Aplicarla debe fallar entera: estado «fallida» y el personaje intacto."""
    from app.assistant.providers import PropuestaBorrador
    from app.assistant.service import AssistantService
    from app.db.models import AssistantMessage

    with session_factory() as sesion:
        servicio = AssistantService(sesion, settings)
        conversacion = servicio.conversacion(mundo.a)
        mensaje = AssistantMessage(project_id=mundo.a, conversation_id=conversacion.id, role="asistente", content="x")
        sesion.add(mensaje)
        sesion.flush()
        datos = servicio._validar_borrador(
            mundo.a, PropuestaBorrador("actualizar", "personaje", mundo.personaje, {"description": "Nueva"}, "Precisar.")
        )
        propuesta = servicio._nueva_propuesta(mundo.a, conversacion.id, mensaje.id, datos)
        sesion.commit()
        propuesta_id = propuesta.id

    assert client.post(f"/projects/{mundo.a}/planificacion/personajes/{mundo.personaje}/aprobar", json={"confirmar": True}).status_code == 200
    respuesta = client.post(f"/projects/{mundo.a}/asistente/propuestas/{propuesta_id}/aprobar")
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "fallida"
    with session_factory() as nueva:
        personaje = nueva.get(Character, mundo.personaje)
        assert personaje.estado == "canonico" and (personaje.description or "") == ""


def test_una_version_no_puede_partir_de_una_version_de_otra_novela(client: TestClient, session_factory: sessionmaker[Session], mundo: Mundo) -> None:
    ajena = client.post(f"/projects/{mundo.b}/manuscripts", json={"title": "Ajeno", "content": "Otro."}).json()
    version_ajena = client.get(f"/projects/{mundo.b}/manuscripts/{ajena['id']}/versions").json()[0]["id"]
    respuesta = client.post(
        f"/projects/{mundo.a}/manuscripts/{mundo.m}/versions",
        json={"content": "Nueva.", "based_on_version_id": version_ajena},
    )
    assert respuesta.status_code == 422
    with session_factory() as nueva:
        assert nueva.scalar(select(func.count(ManuscriptVersion.id)).where(ManuscriptVersion.manuscript_id == mundo.m)) == 1


def test_las_rutas_heredadas_no_atienden_manuscritos_de_proyecto(client: TestClient, session_factory: sessionmaker[Session], mundo: Mundo) -> None:
    assert client.get(f"/manuscripts/{mundo.m}/versions").status_code == 404
    assert client.get(f"/versions/{mundo.v}").status_code == 404
    assert client.get(f"/manuscripts/{mundo.m}/draft").status_code == 404
    assert client.put(f"/manuscripts/{mundo.m}/draft", json={"content": "Intruso.", "base_revision": 2}).status_code == 422
    assert client.post(f"/versions/{mundo.v}/reviews", json={"reviewer": "Intruso", "items": [CITA_OK]}).status_code == 422
    with session_factory() as nueva:
        assert nueva.scalar(select(func.count(EditorialReview.id))) == 1
        assert nueva.get(ManuscriptDraft, nueva.scalar(select(ManuscriptDraft.id))).content == TEXTO + " Fin."


def test_ids_de_otro_manuscrito_de_la_misma_novela_dan_404(client: TestClient, mundo: Mundo) -> None:
    """Dentro de un mismo proyecto, la versión, el punto y la revisión deben pertenecer al manuscrito de la ruta."""
    otro = client.post(f"/projects/{mundo.a}/manuscripts", json={"title": "Cap B", "content": "Otro texto."}).json()["id"]
    casos = [
        ("GET", f"/projects/{mundo.a}/manuscripts/{otro}/versions/{mundo.v}", None),
        ("GET", f"/projects/{mundo.a}/manuscripts/{otro}/versions/{mundo.v}/reviews", None),
        ("GET", f"/projects/{mundo.a}/manuscripts/{otro}/versions/{mundo.v}/analyses", None),
        ("POST", f"/projects/{mundo.a}/manuscripts/{otro}/versions/{mundo.v}/analyses", {"start_offset": 0, "end_offset": 5}),
        ("GET", f"/projects/{mundo.a}/manuscripts/{otro}/recovery-points/{mundo.punto}", None),
        ("POST", f"/projects/{mundo.a}/manuscripts/{otro}/recovery-points/{mundo.punto}/restore", {"base_revision": 1}),
    ]
    codigos = {(m, r): client.request(m, r, json=c).status_code if c is not None else client.request(m, r).status_code for m, r, c in casos}
    assert {k: v for k, v in codigos.items() if v != 404} == {}
