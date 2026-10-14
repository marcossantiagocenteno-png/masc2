"""Adaptador de Anthropic, probado con dobles del SDK: sin red, sin saldo, sin reintentos."""

from __future__ import annotations

import logging
from typing import Any

import pytest

import app.analysis.anthropic_provider as module
from app.analysis.anthropic_provider import (
    CLAUDE_CATEGORIES,
    TOOL_NAME,
    AnthropicAnalyzer,
    build_user_message,
    locate_occurrence,
)
from app.analysis.errors import ProviderFailed, ProviderOutputInvalid
from tests.anthropic_fakes import API_KEY, MODEL, FakeClaude, FakeMessage, FakeBlock, tool_response, valid_finding

FRAGMENT = "La lluvia caía. Después, la lluvia cesó sobre el tejado."
TITLE = "Título privado del manuscrito"
OTHER_VERSION = "Texto de otra versión que no debe enviarse."


def _analyzer(fake: FakeClaude, timeout: float = 30.0, max_tokens: int = 1500) -> AnthropicAnalyzer:
    return AnthropicAnalyzer(
        api_key=API_KEY,
        model=MODEL,
        timeout_seconds=timeout,
        max_output_tokens=max_tokens,
        client_factory=fake.factory,
    )


def test_identidad_del_proveedor_es_real_y_externa() -> None:
    analyzer = _analyzer(FakeClaude())
    assert analyzer.name == "anthropic"
    assert analyzer.is_external is True
    assert analyzer.is_simulated is False
    assert MODEL in analyzer.label
    assert "PROVEEDOR REAL" in analyzer.label
    assert "se envía a Anthropic" in analyzer.label


def test_una_sola_llamada_con_parametros_fijos_y_herramienta_forzada() -> None:
    fake = FakeClaude()
    _analyzer(fake, timeout=12.5, max_tokens=1234).analyze(FRAGMENT)
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["model"] == MODEL
    assert call["max_tokens"] == 1234
    assert call["tool_choice"] == {"type": "tool", "name": TOOL_NAME}
    assert [tool["name"] for tool in call["tools"]] == [TOOL_NAME]
    assert fake.constructed == [(API_KEY, 12.5)]


def test_solo_se_envia_el_fragmento_y_nada_mas() -> None:
    """Ni el título, ni otras versiones, ni comentarios, ni texto fuera del fragmento."""
    fake = FakeClaude()
    _analyzer(fake).analyze(FRAGMENT)
    payload = str(fake.calls[0]["messages"]) + str(fake.calls[0]["system"])
    assert FRAGMENT in fake.calls[0]["messages"][0]["content"]
    assert TITLE not in payload
    assert OTHER_VERSION not in payload
    assert "<fragmento>" in build_user_message(FRAGMENT)


def test_el_sistema_prohibe_atribuir_intenciones_y_penalizar_la_contencion() -> None:
    fake = FakeClaude()
    _analyzer(fake).analyze(FRAGMENT)
    system = fake.calls[0]["system"]
    assert "No atribuyas intenciones" in system
    assert "contención emocional" in system
    assert "frases breves" in system
    assert "no puntúas la calidad" in system


def test_la_salida_no_admite_problemas_verificables() -> None:
    assert "problema_verificable" not in CLAUDE_CATEGORIES


def test_posiciones_calculadas_por_el_backend_sobre_la_aparicion_indicada() -> None:
    # "lluvia" aparece dos veces en el fragmento; la segunda aparición es la que se pide.
    fake = FakeClaude(response=tool_response([valid_finding(quote="lluvia", occurrence=2)]))
    (finding,) = _analyzer(fake).analyze(FRAGMENT)
    first = FRAGMENT.index("lluvia")
    assert finding.quote_offset == FRAGMENT.index("lluvia", first + 1)
    assert FRAGMENT[finding.quote_offset : finding.quote_offset + len(finding.quote)] == finding.quote


def test_lista_vacia_es_una_respuesta_valida() -> None:
    assert _analyzer(FakeClaude(response=tool_response([]))).analyze(FRAGMENT) == []


def test_locate_occurrence_cuenta_apariciones_solapadas() -> None:
    assert locate_occurrence("aaa", "aa", 2) == 1


@pytest.mark.parametrize(
    "finding,reason",
    [
        (valid_finding(quote="esta cita no existe"), "no aparece literalmente"),
        (valid_finding(quote="la lluvia", occurrence=3), "aparición 3"),
        (valid_finding(quote="LA LLUVIA"), "no aparece literalmente"),
    ],
)
def test_citas_inventadas_o_posiciones_incorrectas_se_rechazan(finding: dict[str, Any], reason: str) -> None:
    with pytest.raises(ProviderOutputInvalid, match=reason):
        _analyzer(FakeClaude(response=tool_response([finding]))).analyze(FRAGMENT)


@pytest.mark.parametrize(
    "response",
    [
        FakeMessage(content=[FakeBlock(type="text")], stop_reason="end_turn"),
        FakeMessage(content=[FakeBlock(type="tool_use", name="otra_herramienta", input={})]),
        FakeMessage(content=[FakeBlock(type="tool_use", name=TOOL_NAME, input={"findings": "no es lista"})]),
        FakeMessage(content=[FakeBlock(type="tool_use", name=TOOL_NAME, input={"findings": [], "extra": 1})]),
        FakeMessage(content=[FakeBlock(type="tool_use", name=TOOL_NAME, input=None)]),
    ],
)
def test_respuestas_malformadas_se_rechazan(response: FakeMessage) -> None:
    with pytest.raises(ProviderOutputInvalid):
        _analyzer(FakeClaude(response=response)).analyze(FRAGMENT)


@pytest.mark.parametrize(
    "finding",
    [
        valid_finding(category="problema_verificable"),
        valid_finding(category="categoria_inventada"),
        valid_finding(certainty="absoluta"),
        valid_finding(justification=""),
        valid_finding(occurrence=0),
        valid_finding(unexpected_field="x"),
        valid_finding(observation=""),
    ],
)
def test_hallazgos_fuera_de_esquema_se_rechazan(finding: dict[str, Any]) -> None:
    with pytest.raises(ProviderOutputInvalid, match="esquema"):
        _analyzer(FakeClaude(response=tool_response([finding]))).analyze(FRAGMENT)


def test_mas_hallazgos_que_el_maximo_se_rechazan() -> None:
    findings = [valid_finding() for _ in range(13)]
    with pytest.raises(ProviderOutputInvalid, match="esquema"):
        _analyzer(FakeClaude(response=tool_response(findings))).analyze(FRAGMENT)


def test_respuesta_cortada_por_limite_de_tokens_se_rechaza() -> None:
    with pytest.raises(ProviderOutputInvalid, match="límite de tokens"):
        _analyzer(FakeClaude(response=tool_response([valid_finding()], stop_reason="max_tokens"))).analyze(FRAGMENT)


def test_error_del_sdk_no_expone_su_mensaje_ni_la_clave() -> None:
    leaked = RuntimeError(f"fallo con la clave {API_KEY} y el texto {FRAGMENT}")
    with pytest.raises(ProviderFailed) as info:
        _analyzer(FakeClaude(error=leaked)).analyze(FRAGMENT)
    message = str(info.value)
    assert API_KEY not in message
    assert FRAGMENT not in message
    assert "RuntimeError" in message
    assert info.value.__cause__ is None  # suprimido con "from None"


def test_el_cliente_real_se_crea_sin_reintentos(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un reintento automático del SDK duplicaría llamadas y costes."""
    recorded: dict[str, Any] = {}

    class RecordingSDK:
        def __init__(self, **kwargs: Any) -> None:
            recorded.update(kwargs)

    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", RecordingSDK)
    module.default_client_factory(API_KEY, 7.0)
    assert recorded == {"api_key": API_KEY, "timeout": 7.0, "max_retries": 0}


def test_los_logs_solo_contienen_metadatos(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="novel_engine.analysis")
    _analyzer(FakeClaude()).analyze(FRAGMENT)
    text = caplog.text
    assert MODEL in text
    assert str(len(FRAGMENT)) in text
    assert API_KEY not in text
    assert FRAGMENT not in text


def test_los_errores_no_registran_ni_la_clave_ni_el_texto(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="novel_engine.analysis")
    with pytest.raises(ProviderFailed):
        _analyzer(FakeClaude(error=RuntimeError(f"{API_KEY} {FRAGMENT}"))).analyze(FRAGMENT)
    assert API_KEY not in caplog.text
    assert FRAGMENT not in caplog.text
    assert "error_type=RuntimeError" in caplog.text


def test_la_clave_no_aparece_al_imprimir_la_configuracion() -> None:
    from app.config import Settings

    settings = Settings(anthropic_api_key=API_KEY, anthropic_model=MODEL)
    assert API_KEY not in repr(settings)
    assert settings.anthropic_api_key == API_KEY
