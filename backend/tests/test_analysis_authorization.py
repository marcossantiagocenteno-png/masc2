"""Autorización de envío externo, de extremo a extremo: API, servicio y persistencia.

Todas las llamadas al proveedor real van a un doble del SDK. Ningún test
necesita una clave real ni consume saldo.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import app.analysis.anthropic_provider as module
from app.analysis.anthropic_provider import AnthropicAnalyzer
from app.analysis.errors import AuthorizationRequired
from app.analysis.service import AnalysisService
from app.config import Settings
from app.db.models import AnalysisFinding, AnalysisRun
from app.main import create_app
from app.texts.service import TextService
from tests.anthropic_fakes import API_KEY, MODEL, FakeClaude, FakeMessage, tool_response, valid_finding

TITLE = "Título privado del manuscrito"
FIRST_SENTENCE = "La lluvia caía sobre el tejado."
OUTSIDE = "Otro párrafo ajeno que no debe enviarse."
CONTENT = f"{FIRST_SENTENCE} Después, nadie habló.\n\n{OUTSIDE}"
COMMENT = "Comentario privado editorial que no debe enviarse."
AUTHORIZATION = {"provider": "anthropic", "scope": "fragmento_seleccionado", "acknowledged": True}


@pytest.fixture
def claude(database_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, FakeClaude]]:
    """Cliente con el proveedor Anthropic configurado y un doble del SDK."""
    fake = FakeClaude()
    monkeypatch.setattr(module, "default_client_factory", fake.factory)
    configured = Settings(
        database_url=database_url,
        analysis_provider="anthropic",
        anthropic_api_key=API_KEY,
        anthropic_model=MODEL,
    )
    with TestClient(create_app(configured)) as client:
        yield client, fake


@pytest.fixture
def version_with_context(claude: tuple[TestClient, FakeClaude]) -> dict[str, Any]:
    """Manuscrito con título, otra versión y un comentario: nada de esto debe salir."""
    client, _ = claude
    manuscript = client.post("/manuscripts", json={"title": TITLE, "content": CONTENT}).json()
    version = client.get(f"/manuscripts/{manuscript['id']}/versions").json()[0]
    other = client.post(
        f"/manuscripts/{manuscript['id']}/versions",
        json={"content": "Texto de otra versión que no debe enviarse."},
    ).json()
    client.post(
        f"/versions/{version['id']}/reviews",
        json={
            "reviewer": "Editora",
            "items": [
                {
                    "kind": "observacion",
                    "quote": "lluvia",
                    "start_offset": CONTENT.index("lluvia"),
                    "end_offset": CONTENT.index("lluvia") + len("lluvia"),
                    "comment": COMMENT,
                }
            ],
        },
    )
    return {"version_id": version["id"], "other_id": other["id"], "manuscript_id": manuscript["id"]}


def _analyze(client: TestClient, version_id: int, authorization: dict[str, Any] | None = None) -> Any:
    body: dict[str, Any] = {"start_offset": 0, "end_offset": len(FIRST_SENTENCE)}
    if authorization is not None:
        body["external_authorization"] = authorization
    return client.post(f"/versions/{version_id}/analyses", json=body)


def _runs_stored(session: Session) -> int:
    return int(session.scalar(select(func.count()).select_from(AnalysisRun)) or 0)


def _findings_stored(session: Session) -> int:
    return int(session.scalar(select(func.count()).select_from(AnalysisFinding)) or 0)


# ---------------------------------------------------------------------------
# Autorización explícita por petición
# ---------------------------------------------------------------------------


def test_sin_autorizacion_no_hay_ninguna_llamada_externa(
    claude: tuple[TestClient, FakeClaude], version_with_context: dict[str, Any], session: Session
) -> None:
    client, fake = claude
    response = _analyze(client, version_with_context["version_id"])
    assert response.status_code == 403
    assert "external_authorization" in response.json()["detail"]
    assert fake.constructed == []
    assert fake.calls == []
    assert _runs_stored(session) == 0


def test_autorizacion_de_otro_proveedor_se_rechaza_sin_llamar(
    claude: tuple[TestClient, FakeClaude], version_with_context: dict[str, Any]
) -> None:
    client, fake = claude
    response = _analyze(client, version_with_context["version_id"], {**AUTHORIZATION, "provider": "openai"})
    assert response.status_code == 403
    assert fake.calls == []


def test_con_autorizacion_se_analiza_y_se_registra_el_proveedor_real(
    claude: tuple[TestClient, FakeClaude], version_with_context: dict[str, Any], session: Session
) -> None:
    client, fake = claude
    response = _analyze(client, version_with_context["version_id"], AUTHORIZATION)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["provider_name"] == "anthropic"
    assert body["provider_simulated"] is False
    assert body["sent_external"] is True
    assert body["model_name"] == MODEL
    assert "PROVEEDOR REAL" in body["provider_label"]
    assert len(fake.calls) == 1
    provider_findings = [f for f in body["findings"] if f["provenance"] == "proveedor"]
    assert len(provider_findings) == 1
    (finding,) = provider_findings
    assert finding["quote"] == "La lluvia caía"
    assert finding["source_name"] == "anthropic"
    assert finding["justification"] == valid_finding()["justification"]
    assert finding["category"] == "observacion_literaria"
    assert _runs_stored(session) == 1


def test_la_autorizacion_se_exige_en_cada_peticion(
    claude: tuple[TestClient, FakeClaude], version_with_context: dict[str, Any]
) -> None:
    client, fake = claude
    version_id = version_with_context["version_id"]
    assert _analyze(client, version_id, AUTHORIZATION).status_code == 201
    assert len(fake.calls) == 1

    # Sin autorización en la siguiente petición: no se reutiliza la anterior.
    assert _analyze(client, version_id).status_code == 403
    assert len(fake.calls) == 1

    assert _analyze(client, version_id, AUTHORIZATION).status_code == 201
    assert len(fake.calls) == 2


def test_la_autorizacion_no_puede_ser_falsa(claude: tuple[TestClient, FakeClaude], version_with_context: dict[str, Any]) -> None:
    client, fake = claude
    for invalid in ({**AUTHORIZATION, "acknowledged": False}, {**AUTHORIZATION, "scope": "manuscrito_completo"}):
        response = _analyze(client, version_with_context["version_id"], invalid)
        assert response.status_code == 422
    assert fake.calls == []


def test_el_servicio_tambien_se_niega_sin_autorizacion(session: Session, settings: Settings) -> None:
    """Defensa en profundidad: aunque la ruta falle, el servicio no llama al proveedor externo."""
    fake = FakeClaude()
    provider = AnthropicAnalyzer(
        api_key=API_KEY, model=MODEL, timeout_seconds=5, max_output_tokens=100, client_factory=fake.factory
    )
    texts = TextService(session, max_version_chars=settings.max_version_chars)
    version = texts.list_versions(texts.create_manuscript("Servicio", CONTENT, None).id)[0]
    service = AnalysisService(session, texts, max_analysis_chars=500)
    with pytest.raises(AuthorizationRequired):
        service.analyze(version.id, 0, len(FIRST_SENTENCE), provider, external_authorized=False)
    assert fake.calls == []
    assert _runs_stored(session) == 0


# ---------------------------------------------------------------------------
# Solo el fragmento autorizado sale del equipo
# ---------------------------------------------------------------------------


def test_solo_se_envia_el_fragmento_seleccionado(
    claude: tuple[TestClient, FakeClaude], version_with_context: dict[str, Any]
) -> None:
    client, fake = claude
    assert _analyze(client, version_with_context["version_id"], AUTHORIZATION).status_code == 201
    sent = str(fake.calls[0]["messages"]) + str(fake.calls[0]["system"])
    assert FIRST_SENTENCE in sent
    for private in (TITLE, OUTSIDE, COMMENT, "Texto de otra versión", "Después, nadie habló"):
        assert private not in sent, f"se envió contenido no autorizado: {private!r}"


# ---------------------------------------------------------------------------
# Modo simulado y configuración incompleta: nunca hay llamada externa
# ---------------------------------------------------------------------------


def test_el_modo_simulado_nunca_contacta_anthropic(
    database_url: str, monkeypatch: pytest.MonkeyPatch, version_with_context: dict[str, Any], session: Session
) -> None:
    import anthropic

    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("el modo simulado intentó crear un cliente de Anthropic")

    monkeypatch.setattr(anthropic, "Anthropic", forbidden)
    with TestClient(create_app(Settings(database_url=database_url))) as client:
        response = _analyze(client, version_with_context["version_id"])
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["provider_name"] == "simulado"
    assert body["provider_simulated"] is True
    assert body["sent_external"] is False
    assert body["model_name"] is None
    assert "SIMULADO" in body["provider_label"]


def test_sin_clave_no_hay_llamada_ni_respaldo_simulado(
    database_url: str, monkeypatch: pytest.MonkeyPatch, version_with_context: dict[str, Any], session: Session
) -> None:
    fake = FakeClaude()
    monkeypatch.setattr(module, "default_client_factory", fake.factory)
    configured = Settings(database_url=database_url, analysis_provider="anthropic", anthropic_model=MODEL)
    with TestClient(create_app(configured)) as client:
        response = _analyze(client, version_with_context["version_id"], AUTHORIZATION)
    assert response.status_code == 503
    assert "falta ANTHROPIC_API_KEY" in response.json()["detail"]
    assert fake.constructed == [] and fake.calls == []
    assert _runs_stored(session) == 0  # no se guarda un análisis simulado en su lugar


def test_sin_modelo_no_hay_llamada(
    database_url: str, monkeypatch: pytest.MonkeyPatch, version_with_context: dict[str, Any]
) -> None:
    fake = FakeClaude()
    monkeypatch.setattr(module, "default_client_factory", fake.factory)
    configured = Settings(database_url=database_url, analysis_provider="anthropic", anthropic_api_key=API_KEY)
    with TestClient(create_app(configured)) as client:
        response = _analyze(client, version_with_context["version_id"], AUTHORIZATION)
    assert response.status_code == 503
    assert "NOVEL_ENGINE_ANTHROPIC_MODEL" in response.json()["detail"]
    assert fake.calls == []


# ---------------------------------------------------------------------------
# Fallos, respuestas inválidas y atomicidad
# ---------------------------------------------------------------------------


def test_fallo_del_proveedor_no_altera_el_manuscrito_ni_deja_parciales(
    claude: tuple[TestClient, FakeClaude], version_with_context: dict[str, Any], session: Session
) -> None:
    client, fake = claude
    version_id = version_with_context["version_id"]
    before = client.get(f"/versions/{version_id}").json()
    fake.error = RuntimeError(f"caída simulada con {API_KEY}")

    response = _analyze(client, version_id, AUTHORIZATION)
    assert response.status_code == 502
    assert API_KEY not in response.text
    assert "RuntimeError" in response.json()["detail"]

    after = client.get(f"/versions/{version_id}").json()
    assert after["content"] == before["content"] == CONTENT
    assert after["sha256"] == before["sha256"]
    assert client.get(f"/versions/{version_id}/analyses").json() == []
    assert _findings_stored(session) == 0


@pytest.mark.parametrize(
    "label,response",
    [
        ("cita inventada", tool_response([valid_finding(quote="Esta cita no existe en el texto.")])),
        ("aparición inexistente", tool_response([valid_finding(quote="lluvia", occurrence=2)])),
        ("sin herramienta", FakeMessage(content=[], stop_reason="end_turn")),
        ("sin justificación", tool_response([valid_finding(justification="")])),
        ("categoría de verificación", tool_response([valid_finding(category="problema_verificable")])),
        ("lote mixto", tool_response([valid_finding(), valid_finding(quote="inventada")])),
        ("cortada por tokens", tool_response([valid_finding()], stop_reason="max_tokens")),
    ],
)
def test_respuestas_invalidas_se_rechazan_sin_guardar_nada(
    claude: tuple[TestClient, FakeClaude],
    version_with_context: dict[str, Any],
    session: Session,
    label: str,
    response: FakeMessage,
) -> None:
    client, fake = claude
    fake.response = response
    version_id = version_with_context["version_id"]
    result = _analyze(client, version_id, AUTHORIZATION)
    assert result.status_code == 502, label
    assert API_KEY not in result.text
    assert _runs_stored(session) == 0, label
    assert _findings_stored(session) == 0, label
    assert client.get(f"/versions/{version_id}").json()["content"] == CONTENT


# ---------------------------------------------------------------------------
# Estado del proveedor y ausencia de secretos en respuestas y logs
# ---------------------------------------------------------------------------


def test_estado_del_proveedor_no_llama_y_no_muestra_la_clave(
    claude: tuple[TestClient, FakeClaude],
) -> None:
    client, fake = claude
    body = client.get("/analysis/provider").json()
    assert body["configured"] is True
    assert body["name"] == "anthropic"
    assert body["is_external"] is True
    assert body["is_simulated"] is False
    assert body["model_name"] == MODEL
    assert API_KEY not in str(body)
    assert fake.constructed == [] and fake.calls == []


def test_estado_sin_clave_indica_la_causa_sin_revelar_nada(database_url: str) -> None:
    with TestClient(create_app(Settings(database_url=database_url, analysis_provider="anthropic"))) as client:
        body = client.get("/analysis/provider").json()
    assert body["configured"] is False
    assert "ANTHROPIC_API_KEY" in body["reason"]


def test_estado_del_simulado_por_defecto(database_url: str) -> None:
    with TestClient(create_app(Settings(database_url=database_url))) as client:
        body = client.get("/analysis/provider").json()
    assert body == {
        "configured": True,
        "name": "simulado",
        "label": body["label"],
        "is_simulated": True,
        "is_external": False,
        "model_name": None,
        "reason": None,
    }
    assert "SIMULADO" in body["label"]


def test_la_clave_no_aparece_en_las_respuestas_de_un_flujo_completo(
    claude: tuple[TestClient, FakeClaude], version_with_context: dict[str, Any]
) -> None:
    client, _ = claude
    version_id = version_with_context["version_id"]
    texts = [
        _analyze(client, version_id, AUTHORIZATION).text,
        _analyze(client, version_id).text,
        client.get(f"/versions/{version_id}/analyses").text,
        client.get("/analysis/provider").text,
    ]
    for text in texts:
        assert API_KEY not in text


def test_los_logs_del_flujo_no_contienen_clave_ni_fragmento_ni_comentarios(
    claude: tuple[TestClient, FakeClaude],
    version_with_context: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, fake = claude
    caplog.set_level(logging.DEBUG)
    _analyze(client, version_with_context["version_id"], AUTHORIZATION)
    fake.error = RuntimeError(f"{API_KEY} {FIRST_SENTENCE}")
    _analyze(client, version_with_context["version_id"], AUTHORIZATION)
    for private in (API_KEY, FIRST_SENTENCE, COMMENT, TITLE):
        assert private not in caplog.text


def test_fragmento_demasiado_grande_no_llama_al_proveedor(database_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClaude()
    monkeypatch.setattr(module, "default_client_factory", fake.factory)
    configured = Settings(
        database_url=database_url,
        analysis_provider="anthropic",
        anthropic_api_key=API_KEY,
        anthropic_model=MODEL,
        max_analysis_chars=10,
    )
    with TestClient(create_app(configured)) as client:
        manuscript = client.post("/manuscripts", json={"title": "Grande", "content": "a" * 50}).json()
        version = client.get(f"/manuscripts/{manuscript['id']}/versions").json()[0]
        response = client.post(
            f"/versions/{version['id']}/analyses",
            json={"start_offset": 0, "end_offset": 20, "external_authorization": AUTHORIZATION},
        )
    assert response.status_code == 413
    assert fake.calls == []
