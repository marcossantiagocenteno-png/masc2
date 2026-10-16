"""Asistente: chat por novela, propuestas con aprobación explícita, aislamiento y autorización externa.

Ninguna prueba llama a un servicio real: el proveedor externo es un cliente falso.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

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


def test_dos_envios_simultaneos_con_el_mismo_client_id_no_fallan_ni_duplican(
    session_factory: sessionmaker[Session], settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reproduce la carrera: las dos peticiones comprueban que el client_id no existe antes de que ninguna inserte."""
    with TestClient(create_app(settings)) as cliente:
        proyecto = _proyecto(cliente, "Carrera client_id")
    with session_factory() as preparacion:
        AssistantService(preparacion, settings).conversacion(proyecto)

    barrera = threading.Barrier(2, timeout=10)
    original = AssistantService._mensaje_existente

    def esperar_antes_de_insertar(self: AssistantService, conversacion_id: int, client_id: str) -> AssistantMessage | None:
        resultado = original(self, conversacion_id, client_id)
        if resultado is None:
            barrera.wait()
        return resultado

    monkeypatch.setattr(AssistantService, "_mensaje_existente", esperar_antes_de_insertar)
    resultados: list[dict] = []
    errores: list[BaseException] = []

    def enviar() -> None:
        try:
            with session_factory() as sesion:
                resultados.append(AssistantService(sesion, settings).enviar(proyecto, "cliente-carrera-01", "resumen"))
        except BaseException as error:  # noqa: BLE001 — la prueba debe ver cualquier fallo de hilo
            errores.append(error)

    hilos = [threading.Thread(target=enviar) for _ in range(2)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=30)

    assert errores == []
    assert len(resultados) == 2
    assert [m.id for m in resultados[0]["mensajes"]] == [m.id for m in resultados[1]["mensajes"]]
    with session_factory() as verificacion:
        usuarios = verificacion.scalars(
            select(AssistantMessage).where(
                AssistantMessage.project_id == proyecto, AssistantMessage.client_id == "cliente-carrera-01"
            )
        ).all()
    assert len(usuarios) == 1


def test_si_la_colision_llega_y_el_ganador_ya_existe_se_devuelve_sin_500(
    session_factory: sessionmaker[Session], settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(create_app(settings)) as cliente:
        proyecto = _proyecto(cliente, "Colision determinista")
        primero = _chat(cliente, proyecto, "resumen", client_id="cliente-colision-1")
    assert primero.status_code == 200
    original = AssistantService._mensaje_existente
    llamadas = {"n": 0}

    def primera_vez_no_ve_nada(self: AssistantService, conversacion_id: int, client_id: str) -> AssistantMessage | None:
        llamadas["n"] += 1
        return None if llamadas["n"] == 1 else original(self, conversacion_id, client_id)

    monkeypatch.setattr(AssistantService, "_mensaje_existente", primera_vez_no_ve_nada)
    with TestClient(create_app(settings)) as cliente:
        segundo = _chat(cliente, proyecto, "resumen", client_id="cliente-colision-1")
    assert segundo.status_code == 200
    assert [m["id"] for m in segundo.json()["mensajes"]] == [m["id"] for m in primero.json()["mensajes"]]


def _completar(cliente: TestClient, proyecto: int, instruccion, autorizacion: str | None = None):
    cuerpo = {"entidad": "premisa", "campo": "premise", "actual": "", "instruccion": instruccion}
    if autorizacion is not None:
        cuerpo["autorizacion_hash"] = autorizacion
    return cliente.post(f"/projects/{proyecto}/asistente/autocompletar", json=cuerpo)


@pytest.mark.parametrize("vacia", [None, "", "   \n  "])
def test_instruccion_vacia_equivale_a_no_dar_ninguna(api: TestClient, vacia) -> None:
    proyecto = _proyecto(api, "Instruccion vacia")
    sin = _completar(api, proyecto, None).json()
    con = _completar(api, proyecto, vacia).json()
    assert con["texto"] == sin["texto"]
    assert "Instrucción recibida" not in con["texto"]
    previa_sin = api.post(f"/projects/{proyecto}/asistente/autocompletar/vista-previa", json={"entidad": "premisa", "campo": "premise", "actual": ""}).json()
    previa_con = api.post(f"/projects/{proyecto}/asistente/autocompletar/vista-previa", json={"entidad": "premisa", "campo": "premise", "actual": "", "instruccion": vacia}).json()
    assert previa_con["huella"] == previa_sin["huella"]


def test_instruccion_valida_llega_al_proveedor_y_cambia_la_vista_previa(api: TestClient) -> None:
    proyecto = _proyecto(api, "Instruccion valida")
    respuesta = _completar(api, proyecto, "Hazla más breve y misteriosa")
    assert respuesta.status_code == 200
    assert "Instrucción recibida: Hazla más breve y misteriosa" in respuesta.json()["texto"]
    previa = api.post(f"/projects/{proyecto}/asistente/autocompletar/vista-previa", json={"entidad": "premisa", "campo": "premise", "actual": "", "instruccion": "Hazla más breve y misteriosa"}).json()
    assert "Hazla más breve y misteriosa" in previa["contenido"]


def test_instruccion_demasiado_larga_responde_422(api: TestClient) -> None:
    proyecto = _proyecto(api, "Instruccion larga")
    assert _completar(api, proyecto, "x" * 501).status_code == 422


def test_error_del_proveedor_en_autocompletado_no_cambia_nada(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.assistant.providers import SimulatedAssistant

    def fallar(self, *args, **kwargs):
        raise RuntimeError("fallo interno del proveedor")

    monkeypatch.setattr(SimulatedAssistant, "completar", fallar)
    proyecto = _proyecto(api, "Error proveedor")
    respuesta = _completar(api, proyecto, "Amplía")
    assert respuesta.status_code == 502
    assert "fallo interno" not in respuesta.text
    assert api.get(f"/projects/{proyecto}/asistente/propuestas").json() == []


def test_autorizacion_de_una_instruccion_no_sirve_para_otra(settings: Settings) -> None:
    texto_fake = FakeMessage(content=[FakeBlock(type="text", name=None, input=None)])
    texto_fake.content[0].text = "Sugerencia de prueba"  # type: ignore[attr-defined]
    fake = FakeClaude(response=texto_fake)
    with TestClient(_app_externa(settings, fake)) as cliente:
        proyecto = _proyecto(cliente, "Externo instruccion")
        previa = cliente.post(
            f"/projects/{proyecto}/asistente/autocompletar/vista-previa",
            json={"entidad": "premisa", "campo": "premise", "actual": "", "instruccion": "Versión A"},
        ).json()
        assert previa["externo"] is True
        cambiada = _completar(cliente, proyecto, "Versión B", autorizacion=previa["huella"])
        sin_autorizar = _completar(cliente, proyecto, "Versión A")
        autorizada = _completar(cliente, proyecto, "Versión A", autorizacion=previa["huella"])
    assert cambiada.status_code == 409
    assert sin_autorizar.status_code == 403
    assert autorizada.status_code == 200
    assert len(fake.calls) == 1
