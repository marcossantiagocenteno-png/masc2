"""Evaluación de la premisa y recomendación provisional (F2, corrección).

Demuestra que la premisa cambia la explicación y el ranking cuando corresponde, que la confianza nunca es «alta» y que
las inferencias no se guardan como canon. Las pruebas unitarias no usan base de datos; las de API comparan el canon
antes y después de cada operación.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.planning import premisa as PRE
from app.planning import recomendaciones as RC

OBJETIVO = "Un capitán busca al hijo que lo abandonó hace años."
ESCALADA = "Una ciudad sitiada tiene quince días antes de que el agua se agote, y un traidor oculta las reservas."
CAMBIO = "Una hija vuelve al pueblo, ya no es la misma persona que se fue y aprende a perdonar."
SIN_PISTAS = "Hay una casa vieja en el campo y un jardín."


def _analisis(premisa: str | None, generos: tuple[str, ...] = (), **directrices: str) -> dict:
    return RC.analizar(RC.Entradas(premisa, generos, directrices))


# ---------------------------------------------------------------------------------------------
# Evaluación léxica: hechos, inferencias y preguntas
# ---------------------------------------------------------------------------------------------


def test_las_inferencias_muestran_la_palabra_y_la_frase_que_las_originan() -> None:
    evaluacion = PRE.evaluar(OBJETIVO, [])
    inferencia = next(i for i in evaluacion["inferencias"] if i["categoria"] == "objetivo")
    assert "«busca»" in inferencia["texto"]
    assert inferencia["fragmento"] == OBJETIVO
    assert inferencia["tipo"] == "inferencia"
    assert inferencia["confianza"] == "baja"


def test_ninguna_inferencia_se_marca_como_canon() -> None:
    for premisa in (OBJETIVO, ESCALADA, CAMBIO, SIN_PISTAS):
        evaluacion = PRE.evaluar(premisa, ["Género elegido: Misterio."])
        assert all(inferencia["canon"] is False for inferencia in evaluacion["inferencias"])


def test_los_hechos_son_lo_que_el_autor_escribio_y_decidio() -> None:
    evaluacion = PRE.evaluar(OBJETIVO, ["Género elegido: Misterio."])
    assert all(hecho["tipo"] == "confirmado" for hecho in evaluacion["hechos"])
    textos = [hecho["texto"] for hecho in evaluacion["hechos"]]
    assert any("1 frase" in texto for texto in textos)
    assert "Género elegido: Misterio." in textos


def test_las_formas_flexionadas_cuentan_como_la_misma_pista() -> None:
    # «alterados» debe contar como la raíz «alterad», igual que «desaparecido» cuenta como «desaparec».
    evaluacion = PRE.evaluar("Los registros fueron alterados y el hombre desapareció.", [])
    assert {"obstaculo", "pregunta"} <= set(evaluacion["cubiertas"])


def test_una_premisa_sin_pistas_queda_insuficiente_y_pregunta_por_lo_que_falta() -> None:
    evaluacion = PRE.evaluar(SIN_PISTAS, [])
    assert evaluacion["suficiencia"] == "insuficiente"
    assert evaluacion["inferencias"] == []
    assert len(evaluacion["preguntas"]) == len(PRE.CATEGORIAS)


def test_sin_premisa_se_pide_escribirla() -> None:
    evaluacion = PRE.evaluar(None, [])
    assert evaluacion["presente"] is False
    assert evaluacion["preguntas"][0].startswith("Escribe la premisa")


# ---------------------------------------------------------------------------------------------
# Cambiar la premisa cambia el ranking y la explicación
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("premisa", "primero", "motivo"),
    [
        (OBJETIVO, "siete_puntos", "premisa_objetivo"),
        (ESCALADA, "freytag", "premisa_escalada"),
        (CAMBIO, "save_the_cat", "premisa_cambio"),
    ],
)
def test_cada_premisa_lleva_a_un_modelo_distinto_y_lo_explica_con_su_criterio(premisa: str, primero: str, motivo: str) -> None:
    analisis = _analisis(premisa)
    assert analisis["ranking"][0]["clave"] == primero
    razones = analisis["ranking"][0]["razones"]
    assert any(razon["regla"] == motivo and razon["tipo"] == "inferencia" for razon in razones)


def test_cambiar_la_premisa_cambia_el_orden_del_ranking() -> None:
    antes = [item["clave"] for item in _analisis(OBJETIVO)["ranking"]]
    despues = [item["clave"] for item in _analisis(ESCALADA)["ranking"]]
    assert antes[0] != despues[0]


def test_la_limitacion_de_un_modelo_depende_de_lo_que_la_premisa_no_muestra() -> None:
    limites = {item["clave"]: item["limites_de_la_premisa"] for item in _analisis(OBJETIVO)["ranking"]}
    # La premisa de objetivo no muestra ni conflicto que escalar ni cambio del protagonista.
    assert any("escalar" in texto for texto in limites["freytag"])
    assert any("qué cambia" in texto for texto in limites["save_the_cat"])
    # No limita a Siete puntos: sí tiene objetivo.
    assert limites["siete_puntos"] == []


def test_sin_pistas_la_limitacion_dice_que_no_hay_base_y_no_inventa_motivo() -> None:
    analisis = _analisis(SIN_PISTAS)
    for item in analisis["ranking"]:
        assert item["limites_de_la_premisa"] == ["La premisa no ofrece pistas para este modelo: no hay base para evaluarlo."]
        assert all(razon["regla"] != "premisa_objetivo" for razon in item["razones"])


def test_sin_premisa_la_limitacion_no_pretende_haberla_leido() -> None:
    analisis = _analisis(None)
    assert analisis["ranking"][0]["limites_de_la_premisa"] == ["Sin premisa no hay pistas que evaluar para este modelo."]


# ---------------------------------------------------------------------------------------------
# Confianza: nunca alta, provisional cuando no hay base suficiente
# ---------------------------------------------------------------------------------------------


def test_sin_datos_la_confianza_es_insuficiente_y_la_recomendacion_es_provisional() -> None:
    analisis = _analisis(None)
    assert analisis["confianza"] == "insuficiente"
    assert analisis["recomendacion_provisional"] is True


def test_una_sola_pista_da_confianza_baja_y_provisional() -> None:
    analisis = _analisis(OBJETIVO)
    assert analisis["confianza"] == "baja"
    assert analisis["recomendacion_provisional"] is True


def test_la_confianza_moderada_exige_margen_y_al_menos_dos_categorias() -> None:
    # Un personaje (+2 a Siete puntos, +1 a Save the Cat!) y una premisa con objetivo (+1 a Siete puntos).
    # Siete puntos queda con 3 y Save the Cat! con 1: margen 2, pero la premisa solo cubre una categoría.
    una_categoria = _analisis(OBJETIVO, punto_de_vista="un_personaje")
    assert una_categoria["confianza"] == "baja"
    # Objetivo y obstáculo: dos categorías, y Save the Cat! no recibe nada de la premisa. Margen 2 → moderada.
    dos_categorias = _analisis(
        "Un capitán busca al hijo, pero una tormenta le impide cruzar el mar.", punto_de_vista="un_personaje"
    )
    assert dos_categorias["evaluacion_premisa"]["cubiertas"] == ["objetivo", "obstaculo"]
    assert dos_categorias["confianza"] == "moderada"
    assert dos_categorias["recomendacion_provisional"] is False


def test_un_margen_de_uno_con_dos_categorias_sigue_siendo_baja() -> None:
    # «aprende a perdonar» suma +1 a Save the Cat!: el margen de Siete puntos baja a 1 y la confianza no sube.
    analisis = _analisis("Un capitán busca al hijo, y aprende a perdonar.", punto_de_vista="un_personaje")
    assert analisis["evaluacion_premisa"]["cubiertas"] == ["objetivo", "cambio"]
    assert analisis["confianza"] == "baja"


def test_la_confianza_nunca_es_alta() -> None:
    casos = [
        _analisis(None),
        _analisis(OBJETIVO),
        _analisis(ESCALADA, punto_de_vista="varios_personajes", generos=()),
        _analisis("Un capitán busca al hijo, aprende a perdonar y el tiempo se agota en quince días.", punto_de_vista="un_personaje"),
    ]
    assert {caso["confianza"] for caso in casos} <= {"insuficiente", "baja", "moderada"}


def test_con_margen_de_uno_la_confianza_no_sube_a_moderada() -> None:
    ranking = [{"puntaje": 2}, {"puntaje": 1}, {"puntaje": 0}]
    evaluacion = {"cubiertas": ["objetivo", "cambio"]}
    assert RC.confianza(ranking, evaluacion) == "baja"


# ---------------------------------------------------------------------------------------------
# Etapas: anclajes a la premisa sin acontecimientos inventados
# ---------------------------------------------------------------------------------------------


def test_una_etapa_cita_la_frase_de_la_premisa_que_la_engancha() -> None:
    etapa = next(e for e in RC.etapas_de("freytag") if e.nombre == "Clímax")
    pregunta = RC.pregunta_anclada("freytag", etapa, ESCALADA)
    assert f"«{ESCALADA}»" in pregunta
    assert pregunta.startswith(etapa.pregunta)


def test_una_etapa_sin_pista_en_la_premisa_queda_como_decision_del_autor() -> None:
    etapa = next(e for e in RC.etapas_de("freytag") if e.nombre == "Clímax")
    pregunta = RC.pregunta_anclada("freytag", etapa, OBJETIVO)
    assert pregunta.endswith("La premisa no lo muestra: decídelo tú.")


def test_sin_premisa_la_pregunta_de_la_etapa_es_la_generica() -> None:
    for modelo in RC.MODELOS:
        for etapa in modelo.etapas:
            assert RC.pregunta_anclada(modelo.clave, etapa, None) == etapa.pregunta


def test_las_funciones_de_etapa_no_cambian_con_la_premisa() -> None:
    # Una función describe el papel de la etapa; lo que ocurre lo decide el autor. Por eso no depende del texto.
    for modelo in RC.MODELOS:
        for etapa in modelo.etapas:
            assert RC.pregunta_anclada(modelo.clave, etapa, ESCALADA).startswith(etapa.pregunta)
            assert etapa.funcion in [e.funcion for e in RC.etapas_de(modelo.clave)]


def test_todo_enganche_apunta_a_una_etapa_real_del_catalogo() -> None:
    nombres = {(modelo.clave, etapa.nombre) for modelo in RC.MODELOS for etapa in modelo.etapas}
    assert set(RC.ENGANCHE) <= nombres
    categorias = set(PRE.CATEGORIAS)
    for valores in RC.ENGANCHE.values():
        assert set(valores) <= categorias


# ---------------------------------------------------------------------------------------------
# API: nada de la evaluación se guarda como canon
# ---------------------------------------------------------------------------------------------


@pytest.fixture
def api(client: TestClient) -> TestClient:
    return client


def _url(project_id: int, path: str = "") -> str:
    return f"/projects/{project_id}/planificacion{path}"


def _project(api: TestClient) -> int:
    response = api.post("/projects", json={"name": "Premisa"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _canon(api: TestClient, project_id: int) -> dict:
    base = _url(project_id)
    return {
        "narrativa": api.get(f"{base}/narrativa").json(),
        "directrices": api.get(f"{base}/directrices").json(),
        "personajes": api.get(f"{base}/personajes").json(),
        "lugares": api.get(f"{base}/lugares").json(),
        "elementos": api.get(f"{base}/elementos-trama").json(),
        "acontecimientos": api.get(f"{base}/acontecimientos").json(),
        "estructura": api.get(f"{base}/estructura").json(),
        "vinculos": api.get(f"{base}/vinculos").json(),
        "manuscritos": api.get(f"/projects/{project_id}/manuscripts").json(),
    }


def test_leer_la_evaluacion_no_cambia_el_canon(api: TestClient) -> None:
    project_id = _project(api)
    api.patch(_url(project_id, "/narrativa"), json={"premise": ESCALADA})
    antes = _canon(api, project_id)
    api.get(_url(project_id, "/estructura-recomendada"))
    assert _canon(api, project_id) == antes


def test_proponer_etapas_y_aceptar_una_no_convierte_las_inferencias_en_canon(api: TestClient) -> None:
    project_id = _project(api)
    api.patch(_url(project_id, "/narrativa"), json={"premise": ESCALADA})
    api.put(_url(project_id, "/estructura-recomendada/modelo"), json={"model_key": "freytag"})
    antes = _canon(api, project_id)

    propuestas = api.post(_url(project_id, "/estructura-recomendada/propuestas"), json={})
    assert propuestas.status_code == 201, propuestas.text
    # La propuesta guarda la evaluación usada, pero es solo un registro de entradas.
    evaluacion = propuestas.json()[0]["entradas"]
    assert evaluacion["modelo"] == "freytag"
    assert "premisa_escalada" in evaluacion["reglas"]
    assert _canon(api, project_id)["personajes"] == antes["personajes"]
    assert _canon(api, project_id)["estructura"] == antes["estructura"]

    primera = propuestas.json()[0]["id"]
    aceptada = api.post(_url(project_id, f"/estructura-recomendada/propuestas/{primera}/aceptar"))
    assert aceptada.status_code == 200, aceptada.text
    nodo = aceptada.json()
    assert nodo["estado"] == "provisional"
    assert nodo["origen"] == "ia"
    assert nodo["approved_decision_id"] is None

    despues = _canon(api, project_id)
    assert despues["narrativa"] == antes["narrativa"]
    assert despues["personajes"] == antes["personajes"]
    assert despues["lugares"] == antes["lugares"]
    assert despues["elementos"] == antes["elementos"]
    assert despues["acontecimientos"] == antes["acontecimientos"]
    assert despues["vinculos"] == antes["vinculos"]
    assert despues["manuscritos"] == antes["manuscritos"]
    decisiones = api.get(_url(project_id, f"/estructura/{nodo['id']}/decisiones")).json()
    assert not any(decision["accion"] == "aprobar_canon" for decision in decisiones)


def test_la_pregunta_de_una_etapa_cita_la_premisa_y_no_inventa_acontecimientos(api: TestClient) -> None:
    project_id = _project(api)
    api.patch(_url(project_id, "/narrativa"), json={"premise": ESCALADA})
    api.put(_url(project_id, "/estructura-recomendada/modelo"), json={"model_key": "freytag"})
    propuestas = api.post(_url(project_id, "/estructura-recomendada/propuestas"), json={}).json()
    climax = next(p for p in propuestas if p["title"] == "Clímax")
    assert f"«{ESCALADA}»" in climax["pregunta"]
    # El texto añadido es solo la premisa citada y la pregunta: nada más se asigna.
    assert climax["summary"] is None
    assert climax["funcion"] == next(e.funcion for e in RC.etapas_de("freytag") if e.nombre == "Clímax")


def test_cambiar_la_premisa_despues_no_altera_las_propuestas_ya_generadas(api: TestClient) -> None:
    project_id = _project(api)
    api.patch(_url(project_id, "/narrativa"), json={"premise": ESCALADA})
    api.put(_url(project_id, "/estructura-recomendada/modelo"), json={"model_key": "freytag"})
    antes = api.post(_url(project_id, "/estructura-recomendada/propuestas"), json={}).json()
    api.patch(_url(project_id, "/narrativa"), json={"premise": OBJETIVO})
    despues = api.get(_url(project_id, "/estructura-recomendada")).json()["propuestas"]
    assert despues[0]["pregunta"] == antes[0]["pregunta"]
    assert despues[0]["entradas"] == antes[0]["entradas"]


def test_la_respuesta_incluye_evaluacion_confianza_y_aviso_provisional(api: TestClient) -> None:
    project_id = _project(api)
    data = api.get(_url(project_id, "/estructura-recomendada")).json()
    assert set(data["evaluacion_premisa"]) >= {"hechos", "inferencias", "preguntas", "cubiertas", "suficiencia", "presente"}
    assert data["confianza"] == "insuficiente"
    assert data["recomendacion_provisional"] is True
    assert all(inferencia["canon"] is False for inferencia in data["evaluacion_premisa"]["inferencias"])


def test_el_documento_de_fuentes_existe_y_nombra_las_versiones_del_metodo() -> None:
    documento = Path(__file__).resolve().parents[2] / "docs" / "estructura-narrativa-fuentes.md"
    texto = documento.read_text(encoding="utf-8")
    assert "Writing Excuses" in texto
    assert "Save the Cat! Writes a Novel" in texto
    assert "No es el método original" in texto
