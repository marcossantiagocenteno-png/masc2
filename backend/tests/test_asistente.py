"""Asistente: chat por novela, propuestas con aprobación explícita, aislamiento y autorización externa.

Ninguna prueba llama a un servicio real: el proveedor externo es un cliente falso.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.assistant.contexto import huella
from app.assistant.providers import PropuestaBorrador
from app.assistant.service import AssistantService
from app.config import Settings
from app.db.models import AssistantMessage, Character
from app.main import create_app
from tests.anthropic_fakes import API_KEY, MODEL, FakeBlock, FakeClaude, FakeMessage, tool_response


@pytest.fixture
def api(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def _proyecto(api: TestClient, nombre: str) -> int:
    return api.post("/projects", json={"name": nombre}).json()["id"]


def _chat(api: TestClient, proyecto: int, texto: str, client_id: str = "cliente-0001", autorizacion: str | None = None):
    cuerpo = {"client_id": client_id, "texto": texto}
    if autorizacion is not None:
        cuerpo["autorizacion_hash"] = autorizacion
    return api.post(f"/projects/{proyecto}/asistente/mensajes", json=cuerpo)


def _proponer_personaje(api: TestClient, proyecto: int, nombre: str) -> dict:
    respuesta = _chat(api, proyecto, f"crea un personaje llamado {nombre}", client_id=f"cli-{nombre}-0001")
    assert respuesta.status_code == 200, respuesta.text
    propuestas = respuesta.json()["propuestas"]
    assert len(propuestas) == 1
    return propuestas[0]


def _personajes(session: Session, proyecto: int) -> list[str]:
    return [c.name for c in session.scalars(select(Character).where(Character.project_id == proyecto)).all()]


def test_el_chat_propone_sin_crear_nada_hasta_aprobar(api: TestClient, session: Session) -> None:
    proyecto = _proyecto(api, "Chat sin cambios")
    propuesta = _proponer_personaje(api, proyecto, "Lucía")

    assert propuesta["estado"] == "pendiente"
    assert propuesta["operacion"] == "crear" and propuesta["entidad"] == "personaje"
    assert _personajes(session, proyecto) == []


def test_aprobar_aplica_una_vez_y_repetirlo_no_duplica(api: TestClient, session: Session) -> None:
    proyecto = _proyecto(api, "Aprobación")
    propuesta = _proponer_personaje(api, proyecto, "Lucía")

    primera = api.post(f"/projects/{proyecto}/asistente/propuestas/{propuesta['id']}/aprobar")
    segunda = api.post(f"/projects/{proyecto}/asistente/propuestas/{propuesta['id']}/aprobar")

    assert primera.status_code == 200 and primera.json()["estado"] == "aplicada"
    assert segunda.status_code == 200 and segunda.json()["resultado_id"] == primera.json()["resultado_id"]
    assert _personajes(session, proyecto) == ["Lucía"]


def test_rechazar_no_cambia_ningun_dato(api: TestClient, session: Session) -> None:
    proyecto = _proyecto(api, "Rechazo")
    propuesta = _proponer_personaje(api, proyecto, "Mara")

    respuesta = api.post(f"/projects/{proyecto}/asistente/propuestas/{propuesta['id']}/rechazar")

    assert respuesta.status_code == 200 and respuesta.json()["estado"] == "rechazada"
    assert _personajes(session, proyecto) == []
    memoria = api.get(f"/projects/{proyecto}/asistente/memoria").json()
    assert any(item["kind"] == "rechazada" for item in memoria)


def test_aprobar_una_propuesta_rechazada_responde_409(api: TestClient) -> None:
    proyecto = _proyecto(api, "Rechazada y aprobada")
    propuesta = _proponer_personaje(api, proyecto, "Nora")
    api.post(f"/projects/{proyecto}/asistente/propuestas/{propuesta['id']}/rechazar")

    respuesta = api.post(f"/projects/{proyecto}/asistente/propuestas/{propuesta['id']}/aprobar")

    assert respuesta.status_code == 409


def test_el_mismo_client_id_no_duplica_el_mensaje_ni_llama_otra_vez(api: TestClient, session: Session) -> None:
    proyecto = _proyecto(api, "Idempotencia")
    primero = _chat(api, proyecto, "resumen de la novela", client_id="mismo-cliente-1")
    segundo = _chat(api, proyecto, "resumen de la novela", client_id="mismo-cliente-1")

    assert primero.status_code == segundo.status_code == 200
    assert [m["id"] for m in primero.json()["mensajes"]] == [m["id"] for m in segundo.json()["mensajes"]]
    total = session.scalar(select(func.count()).select_from(AssistantMessage).where(AssistantMessage.project_id == proyecto))
    assert total == 2


def test_un_elemento_que_cambio_deja_la_propuesta_desactualizada_y_no_toca_nada(
    api: TestClient, session: Session, settings: Settings
) -> None:
    proyecto = _proyecto(api, "Desactualizada")
    creado = api.post(f"/projects/{proyecto}/planificacion/personajes", json={"name": "Iris", "description": "Antes"})
    assert creado.status_code == 201, creado.text
    personaje_id = creado.json()["id"]

    servicio = AssistantService(session, settings)
    conversacion = servicio.conversacion(proyecto)
    mensaje = AssistantMessage(project_id=proyecto, conversation_id=conversacion.id, role="asistente", content="x")
    session.add(mensaje)
    session.flush()
    datos = servicio._validar_borrador(
        proyecto, PropuestaBorrador("actualizar", "personaje", personaje_id, {"description": "Propuesta"}, "Precisar la descripción.")
    )
    propuesta = servicio._nueva_propuesta(proyecto, conversacion.id, mensaje.id, datos)
    session.commit()

    api.patch(f"/projects/{proyecto}/planificacion/personajes/{personaje_id}", json={"description": "Cambio del autor"})
    respuesta = api.post(f"/projects/{proyecto}/asistente/propuestas/{propuesta.id}/aprobar")

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "desactualizada"
    fila = session.scalar(select(Character).where(Character.id == personaje_id))
    session.refresh(fila)
    assert fila.description == "Cambio del autor"


def test_no_se_puede_aprobar_una_propuesta_de_otra_novela(api: TestClient) -> None:
    origen = _proyecto(api, "Origen")
    otra = _proyecto(api, "Otra")
    propuesta = _proponer_personaje(api, origen, "Teo")

    respuesta = api.post(f"/projects/{otra}/asistente/propuestas/{propuesta['id']}/aprobar")

    assert respuesta.status_code == 404
    assert api.get(f"/projects/{otra}/asistente/propuestas").json() == []


def test_un_proyecto_archivado_no_admite_envios_ni_aprobaciones(api: TestClient, session: Session) -> None:
    proyecto = _proyecto(api, "Archivado")
    propuesta = _proponer_personaje(api, proyecto, "Ada")
    assert api.post(f"/projects/{proyecto}/archive").status_code == 200

    envio = _chat(api, proyecto, "resumen", client_id="cliente-archivado-1")
    aprobacion = api.post(f"/projects/{proyecto}/asistente/propuestas/{propuesta['id']}/aprobar")

    assert envio.status_code == 422
    assert aprobacion.status_code == 422
    assert _personajes(session, proyecto) == []


def test_la_vista_previa_coincide_con_lo_que_se_envia_y_sin_autorizacion_no_hay_envio(api: TestClient) -> None:
    proyecto = _proyecto(api, "Vista previa")
    preview = api.post(f"/projects/{proyecto}/asistente/vista-previa", json={"texto": "resumen"}).json()

    assert preview["externo"] is False and preview["simulado"] is True
    assert preview["huella"] == huella(preview["contenido"])
    assert "resumen" in preview["contenido"]


def test_autocompletar_simulado_no_guarda_nada_y_lo_marca(api: TestClient) -> None:
    proyecto = _proyecto(api, "Autocompletar")
    respuesta = api.post(
        f"/projects/{proyecto}/asistente/autocompletar",
        json={"entidad": "premisa", "campo": "premise", "actual": "", "instruccion": None},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["simulado"] is True
    assert respuesta.json()["texto"].startswith("[Simulado, sin IA]")


def test_autocompletar_rechaza_campos_fuera_de_la_lista(api: TestClient) -> None:
    proyecto = _proyecto(api, "Campo no permitido")
    respuesta = api.post(
        f"/projects/{proyecto}/asistente/autocompletar",
        json={"entidad": "personaje", "campo": "name", "actual": "", "instruccion": None},
    )

    assert respuesta.status_code == 422


def test_autocompletar_no_accede_a_elementos_de_otra_novela(api: TestClient) -> None:
    origen = _proyecto(api, "Origen completar")
    otra = _proyecto(api, "Otra completar")
    creado = api.post(f"/projects/{origen}/planificacion/lugares", json={"name": "Puerto"})
    lugar_id = creado.json()["id"]

    respuesta = api.post(
        f"/projects/{otra}/asistente/autocompletar",
        json={"entidad": "lugar", "campo": "description", "entidad_id": lugar_id, "actual": "", "instruccion": None},
    )

    assert respuesta.status_code == 404


def _app_anthropic(settings: Settings, fake: FakeClaude) -> Settings:  # el cliente falso se inyecta en app.state
    return Settings(
        database_url=settings.database_url,
        assistant_provider="anthropic",
        anthropic_api_key=API_KEY,
        anthropic_model=MODEL,
    )


def _app_externa(settings: Settings, fake: FakeClaude):
    aplicacion = create_app(_app_anthropic(settings, fake))
    aplicacion.state.assistant_client_factory = fake.factory
    return aplicacion


def test_proveedor_externo_sin_autorizacion_responde_403_y_no_llama(settings: Settings) -> None:
    fake = FakeClaude(response=tool_response([]))
    with TestClient(_app_externa(settings, fake)) as cliente:
        proyecto = _proyecto(cliente, "Externo sin permiso")
        respuesta = _chat(cliente, proyecto, "resumen", client_id="cliente-externo-1")
    assert respuesta.status_code == 403
    assert fake.calls == []


def test_proveedor_externo_con_huella_distinta_responde_409(settings: Settings) -> None:
    fake = FakeClaude(response=tool_response([]))
    with TestClient(_app_externa(settings, fake)) as cliente:
        proyecto = _proyecto(cliente, "Externo huella")
        respuesta = _chat(cliente, proyecto, "resumen", client_id="cliente-externo-2", autorizacion="0" * 64)
    assert respuesta.status_code == 409
    assert fake.calls == []


def test_proveedor_externo_con_la_huella_revisada_envia_y_guarda_la_propuesta(settings: Settings) -> None:
    fake = FakeClaude(
        response=FakeMessage(
            content=[
                FakeBlock(
                    type="tool_use",
                    name="registrar_respuesta",
                    input={
                        "texto": "Propongo un lugar.",
                        "propuestas": [
                            {"operacion": "crear", "entidad": "lugar", "datos": {"name": "Faro"}, "motivo": "Falta un escenario."}
                        ],
                    },
                )
            ]
        )
    )
    with TestClient(_app_externa(settings, fake)) as cliente:
        proyecto = _proyecto(cliente, "Externo autorizado")
        vista = cliente.post(f"/projects/{proyecto}/asistente/vista-previa", json={"texto": "propón un lugar"}).json()
        assert vista["externo"] is True
        respuesta = _chat(cliente, proyecto, "propón un lugar", client_id="cliente-externo-3", autorizacion=vista["huella"])

    assert respuesta.status_code == 200
    assert len(fake.calls) == 1
    assert respuesta.json()["propuestas"][0]["datos"] == {"name": "Faro"}


def test_respuesta_externa_mal_formada_no_crea_propuestas_y_conserva_el_mensaje(settings: Settings) -> None:
    fake = FakeClaude(response=FakeMessage(content=[FakeBlock(type="text", name=None, input=None)]))
    with TestClient(_app_externa(settings, fake)) as cliente:
        proyecto = _proyecto(cliente, "Malformada")
        vista = cliente.post(f"/projects/{proyecto}/asistente/vista-previa", json={"texto": "hola"}).json()
        respuesta = _chat(cliente, proyecto, "hola", client_id="cliente-malo-0001", autorizacion=vista["huella"])
        historial = cliente.get(f"/projects/{proyecto}/asistente").json()["mensajes"]

    assert respuesta.status_code == 200
    assert respuesta.json()["propuestas"] == []
    assert respuesta.json()["error"] is not None
    assert [m["role"] for m in historial] == ["usuario", "sistema"]


def test_proveedor_externo_sin_clave_responde_503_y_no_envia_nada(settings: Settings) -> None:
    sin_clave = Settings(database_url=settings.database_url, assistant_provider="anthropic", anthropic_model=MODEL)
    fake = FakeClaude(response=tool_response([]))
    with TestClient(create_app(sin_clave)) as cliente:
        proyecto = _proyecto(cliente, "Sin clave")
        respuesta = _chat(cliente, proyecto, "resumen", client_id="cliente-sin-clave-1")
    assert respuesta.status_code == 503
    assert "ANTHROPIC_API_KEY" in respuesta.json()["detail"]
    assert fake.calls == []
