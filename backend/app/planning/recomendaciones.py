"""Recomendaciones de estructura narrativa (F2): catálogo de modelos, ranking y funciones de etapa.

Todo es determinista. No se interpreta el texto de la premisa: la premisa se cita como dato del autor y sirve de
base a las preguntas pendientes. Cada motivo del ranking declara su tipo:

- ``confirmado``: un dato que el autor guardó (una directriz, un género, la premisa).
- ``inferencia``: una regla de este módulo que relaciona un dato con un modelo.
- ``convencion``: una convención habitual del género. Es opcional y el autor puede ignorarla.
- ``pregunta_pendiente``: algo que el autor debe decidir antes de que el modelo tenga efecto.

Las etapas describen una función dramática, nunca un acontecimiento. Lo que ocurre en cada etapa lo decide el autor.
Un modelo es un método o una forma de referencia, no una exigencia: el texto de cada uno indica sus límites.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from app.planning import generos as GENEROS
from app.planning import premisa as PRE

TIPO_CONFIRMADO: Final = "confirmado"
TIPO_INFERENCIA: Final = "inferencia"
TIPO_CONVENCION: Final = "convencion"
TIPO_PREGUNTA: Final = "pregunta_pendiente"


@dataclass(frozen=True)
class Etapa:
    nombre: str
    funcion: str
    pregunta: str


@dataclass(frozen=True)
class Modelo:
    clave: str
    nombre: str
    origen: str
    ambito: str
    pertinencia: str
    favorece: str
    limitaciones: str
    etapas: tuple[Etapa, ...]


MODELOS: Final[tuple[Modelo, ...]] = (
    Modelo(
        clave="freytag",
        nombre="Pirámide de Freytag (cinco actos)",
        origen=(
            "Gustav Freytag, «Die Technik des Dramas» (1863): modelo de cinco partes de la acción dramática, derivado "
            "del análisis de obras griegas y shakespearianas. Fuente consultada: estudios secundarios (Utrecht "
            "Dramaturgy Database). El texto original no se ha consultado."
        ),
        ambito="Teatro y narrativa",
        pertinencia=(
            "Describe una acción que sube hacia una crisis y baja hacia el desenlace. Sirve cuando la novela gira en "
            "torno a un conflicto central que se intensifica."
        ),
        favorece=(
            "Conflictos centrales con escalada clara y consecuencias acumuladas, y tramas con varios personajes que "
            "comparten la misma acción."
        ),
        limitaciones=(
            "Describe la forma de la acción, no dice cuándo debe llegar cada giro ni qué personaje lo provoca. Ofrece "
            "poco detalle para tramas episódicas o con varios conflictos paralelos."
        ),
        etapas=(
            Etapa(
                "Exposición",
                "Presentar la situación inicial, a quién afecta y qué equilibrio existe antes del conflicto.",
                "¿Qué situación inicial muestra la premisa y qué la pone en marcha?",
            ),
            Etapa(
                "Acción ascendente",
                "Intensificar el conflicto central con obstáculos que aumentan lo que está en juego.",
                "¿Qué obstáculos del conflicto central se acumulan antes del punto más alto?",
            ),
            Etapa(
                "Clímax",
                "Forzar la decisión o el enfrentamiento que el conflicto venía preparando.",
                "¿Qué decisión o enfrentamiento resuelve el conflicto central?",
            ),
            Etapa(
                "Acción descendente",
                "Mostrar las consecuencias del clímax y la nueva situación de los personajes.",
                "¿Qué consecuencias del clímax deben mostrarse antes del desenlace?",
            ),
            Etapa(
                "Desenlace",
                "Cerrar la pregunta central y mostrar el estado final de los personajes.",
                "¿Qué pregunta de la premisa queda respondida al final y cuál queda abierta a propósito?",
            ),
        ),
    ),
    Modelo(
        clave="siete_puntos",
        nombre="Siete puntos (Dan Wells)",
        origen=(
            "Dan Wells lo presenta en el episodio 21.24 de Writing Excuses («Deconstructing the Seven Point Plot "
            "Structure»). Es una referencia de puntos de giro alrededor del protagonista, no una teoría académica."
        ),
        ambito="Narrativa",
        pertinencia=(
            "Organiza la historia alrededor del protagonista y de sus respuestas a los giros. Sirve cuando el interés "
            "depende de lo que el personaje quiere y de lo que le impide conseguirlo."
        ),
        favorece=(
            "Novelas centradas en un protagonista con un objetivo claro, con investigación o misterio, y con giros que "
            "cambian lo que el personaje cree."
        ),
        limitaciones=(
            "Da puntos de referencia, no contenido: no fija el número de capítulos ni resuelve tramas con varios "
            "protagonistas. Puede forzar una estructura de giros en una historia que avanza por acumulación o episodios."
        ),
        etapas=(
            Etapa(
                "Gancho",
                "Captar la atención con la situación en la que el protagonista empieza a no poder seguir igual.",
                "¿Qué detalle de la premisa engancha al lector desde el principio?",
            ),
            Etapa(
                "Primer punto de giro",
                "Obligar al protagonista a entrar en el conflicto y cambiar de objetivo o de perspectiva.",
                "¿Qué acontecimiento obliga al protagonista a entrar en el conflicto?",
            ),
            Etapa(
                "Primer punto de presión",
                "Mostrar la fuerza del antagonista o del obstáculo principal.",
                "¿Qué obstáculo o adversario se hace visible en este punto?",
            ),
            Etapa(
                "Punto medio",
                "Revelar una verdad o un cambio que altera el plan del protagonista.",
                "¿Qué descubrimiento o cambio invierte el plan inicial?",
            ),
            Etapa(
                "Segundo punto de presión",
                "Empeorar la situación: el protagonista pierde apoyos o ve fallar su plan.",
                "¿Qué pérdida o fracaso empeora la situación?",
            ),
            Etapa(
                "Segundo punto de giro",
                "Dar al protagonista la información o la decisión que le permite actuar en el conflicto final.",
                "¿Qué comprende o decide el protagonista que le permite enfrentarse al conflicto final?",
            ),
            Etapa(
                "Resolución",
                "Mostrar el resultado del enfrentamiento y el estado del protagonista después.",
                "¿Cómo cambia el protagonista y qué queda pendiente?",
            ),
        ),
    ),
    Modelo(
        clave="save_the_cat",
        nombre="Save the Cat! (15 escenas)",
        origen=(
            "Blake Snyder, «Save the Cat!» (2005): método para planificar guiones de cine con 15 beats y páginas "
            "orientativas. Jessica Brody lo adaptó a la novela en «Save the Cat! Writes a Novel», con otros "
            "porcentajes y listas por género. Este catálogo recoge el método original de Snyder."
        ),
        ambito="Guion de cine; adaptado a la novela en versiones posteriores",
        pertinencia=(
            "Sirve para planificar con detalle en qué momento ocurre cada escena clave y para dar un ritmo marcado a "
            "la historia."
        ),
        favorece=(
            "Historias lineales de causa y efecto, con un protagonista que cambia y un ritmo de escenas bien definido."
        ),
        limitaciones=(
            "Está pensado para guion de cine, con páginas orientativas. Sus hojas incluyen listas por género y "
            "proporciones concretas que pueden imponer una forma ajena a la novela. Las versiones para novela cambian "
            "porcentajes y nombres: no son el método original."
        ),
        etapas=(
            Etapa(
                "Imagen de apertura",
                "Mostrar el estado inicial del mundo y del protagonista antes del cambio.",
                "¿Cómo está el protagonista al principio, antes de que empiece la historia?",
            ),
            Etapa(
                "Declaración del tema",
                "Enunciar, por palabras o por una acción, la cuestión que la historia va a examinar.",
                "¿Qué pregunta sobre la vida o la sociedad examina la historia?",
            ),
            Etapa(
                "Planteamiento",
                "Presentar el entorno, los personajes importantes y lo que el protagonista tiene que perder.",
                "¿Qué tiene que perder el protagonista si no actúa?",
            ),
            Etapa(
                "Catalizador",
                "Producir el acontecimiento que rompe el equilibrio inicial.",
                "¿Qué acontecimiento rompe el equilibrio del protagonista?",
            ),
            Etapa(
                "Debate",
                "Mostrar que el protagonista duda antes de comprometerse con el cambio.",
                "¿Qué le impide al protagonista decidirse?",
            ),
            Etapa(
                "Entrada al segundo acto",
                "Comprometer al protagonista con el nuevo camino.",
                "¿Qué decisión compromete al protagonista con el conflicto?",
            ),
            Etapa(
                "Subtrama",
                "Introducir un segundo hilo que aporta otro punto de vista o un tema distinto.",
                "¿Qué otro hilo o personaje aporta un punto de vista distinto?",
            ),
            Etapa(
                "Diversión y juegos",
                "Mostrar la promesa de la premisa: lo que el lector esperaba ver.",
                "¿Qué escena cumple la promesa que hace la premisa?",
            ),
            Etapa(
                "Punto medio",
                "Subir las apuestas con una falsa victoria o una derrota que cambia el objetivo.",
                "¿Qué cambia el objetivo del protagonista a mitad de la historia?",
            ),
            Etapa(
                "Se cierran las fuerzas contrarias",
                "Aumentar la presión del antagonista o de las fuerzas en contra.",
                "¿Qué fuerza se acerca y aumenta la presión?",
            ),
            Etapa(
                "Todo está perdido",
                "Llevar al protagonista a su punto más bajo.",
                "¿Qué pérdida deja al protagonista sin recursos?",
            ),
            Etapa(
                "Noche oscura del alma",
                "Dar al protagonista el tiempo de reflexión sobre lo que ha fallado.",
                "¿Qué comprende el protagonista en su punto más bajo?",
            ),
            Etapa(
                "Entrada al tercer acto",
                "Convertir la comprensión en una decisión de actuar.",
                "¿Qué decisión toma el protagonista para afrontar el final?",
            ),
            Etapa(
                "Final",
                "Resolver el conflicto central con la decisión del protagonista.",
                "¿Cómo se resuelve el conflicto central?",
            ),
            Etapa(
                "Imagen final",
                "Mostrar el mundo después del cambio, en contraste con la imagen de apertura.",
                "¿Qué contraste con el inicio cierra la historia?",
            ),
        ),
    ),
)

MODELOS_POR_CLAVE: Final[dict[str, Modelo]] = {modelo.clave: modelo for modelo in MODELOS}
CLAVES: Final[frozenset[str]] = frozenset(MODELOS_POR_CLAVE)


PUNTOS_DE_VISTA_UN_PERSONAJE: Final = frozenset({"un_personaje"})
FOCALIZACIONES_UN_PERSONAJE: Final = frozenset({"interna_fija"})

# Qué elemento de la premisa engancha con cada etapa. Es una regla de diseño, no una norma literaria:
# una etapa cuyo elemento no aparece en la premisa se presenta como pregunta abierta, sin contenido.
ENGANCHE: Final[dict[tuple[str, str], tuple[str, ...]]] = {
    ("freytag", "Exposición"): ("objetivo",),
    ("freytag", "Acción ascendente"): ("obstaculo", "tension"),
    ("freytag", "Clímax"): ("obstaculo",),
    ("freytag", "Acción descendente"): ("cambio",),
    ("freytag", "Desenlace"): ("pregunta", "cambio"),
    ("siete_puntos", "Gancho"): ("pregunta",),
    ("siete_puntos", "Primer punto de giro"): ("objetivo", "obstaculo"),
    ("siete_puntos", "Primer punto de presión"): ("obstaculo",),
    ("siete_puntos", "Punto medio"): ("cambio", "pregunta"),
    ("siete_puntos", "Segundo punto de presión"): ("tension", "obstaculo"),
    ("siete_puntos", "Segundo punto de giro"): ("cambio",),
    ("siete_puntos", "Resolución"): ("pregunta", "cambio"),
    ("save_the_cat", "Imagen de apertura"): ("cambio",),
    ("save_the_cat", "Declaración del tema"): ("pregunta",),
    ("save_the_cat", "Planteamiento"): ("objetivo",),
    ("save_the_cat", "Catalizador"): ("obstaculo",),
    ("save_the_cat", "Debate"): ("cambio",),
    ("save_the_cat", "Entrada al segundo acto"): ("objetivo",),
    ("save_the_cat", "Punto medio"): ("pregunta",),
    ("save_the_cat", "Se cierran las fuerzas contrarias"): ("obstaculo", "tension"),
    ("save_the_cat", "Todo está perdido"): ("obstaculo",),
    ("save_the_cat", "Noche oscura del alma"): ("cambio",),
    ("save_the_cat", "Entrada al tercer acto"): ("cambio",),
    ("save_the_cat", "Final"): ("pregunta", "obstaculo"),
    ("save_the_cat", "Imagen final"): ("cambio",),
}


@dataclass(frozen=True)
class Entradas:
    """Datos del autor que alimentan una recomendación. Solo lectura: nada de aquí se modifica."""

    premisa: str | None
    generos: tuple[str, ...]  # claves del catálogo, solo las seleccionadas y activas
    directrices: Mapping[str, str | None]  # solo los campos de valor; ``None`` si el autor no ha decidido


def _razon(tipo: str, texto: str, peso: int, regla: str) -> dict[str, Any]:
    return {"tipo": tipo, "texto": texto, "peso": peso, "regla": regla}


def _reglas_de_datos(entradas: Entradas) -> dict[str, list[dict[str, Any]]]:
    """Motivos que vienen de directrices y géneros: datos que el autor decidió."""
    motivos: dict[str, list[dict[str, Any]]] = {modelo.clave: [] for modelo in MODELOS}
    punto = entradas.directrices.get("punto_de_vista")
    foco = entradas.directrices.get("focalizacion")
    generos = set(entradas.generos)

    if punto in PUNTOS_DE_VISTA_UN_PERSONAJE or foco in FOCALIZACIONES_UN_PERSONAJE:
        texto = (
            "Tu punto de vista es un solo personaje: los giros se pueden medir por cómo ese personaje responde a ellos."
        )
        motivos["siete_puntos"].append(_razon(TIPO_INFERENCIA, texto, 2, "un_personaje"))
        motivos["save_the_cat"].append(
            _razon(TIPO_INFERENCIA, "Un protagonista que cambia encaja con la hoja de escenas.", 1, "un_personaje")
        )

    if punto == "varios_personajes" or foco == "interna_variable":
        texto = (
            "Tienes varios puntos de vista: Freytag describe la acción común sin atar los giros a un solo personaje."
        )
        motivos["freytag"].append(_razon(TIPO_INFERENCIA, texto, 2, "varios_personajes"))

    if punto == "omnisciente" or foco == "omnisciente":
        texto = "La narración es omnisciente: la forma de la acción no depende de la mirada de un personaje."
        motivos["freytag"].append(_razon(TIPO_INFERENCIA, texto, 1, "omnisciente"))

    if generos & {"misterio", "thriller"}:
        texto = (
            "Los géneros de misterio y suspense suelen apoyarse en preguntas que se responden por etapas. "
            "Es una convención habitual, no una exigencia: puedes ignorarla."
        )
        motivos["siete_puntos"].append(_razon(TIPO_CONVENCION, texto, 1, "genero_misterio"))

    if "tragedia" in generos:
        texto = (
            "La tragedia es el origen de la pirámide de Freytag. Es una convención histórica, no una exigencia de tu historia."
        )
        motivos["freytag"].append(_razon(TIPO_CONVENCION, texto, 1, "genero_tragedia"))

    return motivos


# Criterio «favorece» de cada modelo, citado tal cual en el motivo. Cada regla de premisa usa uno de ellos.
_CRITERIO_OBJETIVO: Final = "un protagonista con un objetivo claro"
_CRITERIO_ESCALADA: Final = "un conflicto central que se intensifica"
_CRITERIO_CAMBIO: Final = "un protagonista que cambia"


def _reglas_de_premisa(evaluacion: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Motivos que vienen de pistas de la premisa. Siempre son inferencias: ``canon`` nunca se toca."""
    motivos: dict[str, list[dict[str, Any]]] = {modelo.clave: [] for modelo in MODELOS}
    cubiertas = set(evaluacion["cubiertas"])
    fragmento = {
        categoria: next((i["fragmento"] for i in evaluacion["inferencias"] if i["categoria"] == categoria), "")
        for categoria in cubiertas
    }
    if "objetivo" in cubiertas:
        texto = (
            f"La premisa sugiere un objetivo del protagonista («{fragmento['objetivo']}»). "
            f"Siete puntos favorece {_CRITERIO_OBJETIVO}."
        )
        motivos["siete_puntos"].append(_razon(TIPO_INFERENCIA, texto, 1, "premisa_objetivo"))
    if {"obstaculo", "tension"} <= cubiertas:
        texto = (
            f"La premisa sugiere un obstáculo con presión de tiempo («{fragmento['obstaculo']}»). "
            f"Freytag favorece {_CRITERIO_ESCALADA}."
        )
        motivos["freytag"].append(_razon(TIPO_INFERENCIA, texto, 1, "premisa_escalada"))
    if "cambio" in cubiertas:
        texto = (
            f"La premisa sugiere un cambio del protagonista («{fragmento['cambio']}»). "
            f"Save the Cat! favorece {_CRITERIO_CAMBIO}."
        )
        motivos["save_the_cat"].append(_razon(TIPO_INFERENCIA, texto, 1, "premisa_cambio"))
    return motivos


def _limites_de_premisa(evaluacion: Mapping[str, Any]) -> dict[str, list[str]]:
    """Cómo limita la premisa a cada modelo: lo que el modelo necesita y la premisa no muestra."""
    cubiertas = set(evaluacion["cubiertas"])
    if not cubiertas:
        mensaje = (
            "La premisa no ofrece pistas para este modelo: no hay base para evaluarlo."
            if evaluacion["presente"]
            else "Sin premisa no hay pistas que evaluar para este modelo."
        )
        return {modelo.clave: [mensaje] for modelo in MODELOS}
    limites: dict[str, list[str]] = {modelo.clave: [] for modelo in MODELOS}
    if "obstaculo" not in cubiertas:
        limites["freytag"].append(
            "La premisa no muestra un conflicto que escalar: Freytag describe una acción que sube, y la escalada queda por decidir."
        )
    if "objetivo" not in cubiertas:
        limites["siete_puntos"].append(
            "Sin un objetivo visible en la premisa, los giros de Siete puntos no tienen de qué partir."
        )
    if "cambio" not in cubiertas:
        limites["save_the_cat"].append(
            "La premisa no muestra qué cambia en el protagonista: el método de Save the Cat! presupone ese cambio para su imagen final."
        )
    return limites


def _motivo_de_posicion(puntaje: int, posicion: int, empates: int, motivos: list[dict[str, Any]]) -> str:
    if puntaje == 0:
        return (
            "Sin datos que lo distingan: se mantiene el orden de referencia del catálogo."
            if empates > 1
            else "Sin señales a su favor en tus datos."
        )
    if empates > 1:
        return f"Empata con {empates - 1} modelo(s) por el mismo puntaje. Se desempata por el orden de referencia."
    return f"{'Primera' if posicion == 1 else f'Posición {posicion}'} por {len(motivos)} señal(es) de tus datos."


def rankear(entradas: Entradas, evaluacion: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """Ordena los modelos por puntaje. Empates: orden de referencia del catálogo, que es estable."""
    if evaluacion is None:
        evaluacion = PRE.evaluar(entradas.premisa, _hechos_del_autor(entradas))
    datos = _reglas_de_datos(entradas)
    premisa = _reglas_de_premisa(evaluacion)
    limites = _limites_de_premisa(evaluacion)
    motivos = {clave: datos[clave] + premisa[clave] for clave in datos}
    puntajes = {modelo.clave: sum(razon["peso"] for razon in motivos[modelo.clave]) for modelo in MODELOS}
    orden = sorted(range(len(MODELOS)), key=lambda indice: (-puntajes[MODELOS[indice].clave], indice))
    resultado: list[dict[str, Any]] = []
    for posicion, indice in enumerate(orden, start=1):
        modelo = MODELOS[indice]
        puntaje = puntajes[modelo.clave]
        empates = sum(1 for valor in puntajes.values() if valor == puntaje)
        razones = list(motivos[modelo.clave])
        if empates == len(MODELOS):
            razones.append(
                _razon(TIPO_INFERENCIA, "Tus datos no distinguen entre los modelos todavía.", 0, "sin_datos")
            )
        resultado.append(
            {
                "clave": modelo.clave,
                "nombre": modelo.nombre,
                "origen": modelo.origen,
                "ambito": modelo.ambito,
                "pertinencia": modelo.pertinencia,
                "favorece": modelo.favorece,
                "limitaciones": modelo.limitaciones,
                "numero_de_etapas": len(modelo.etapas),
                "posicion": posicion,
                "puntaje": puntaje,
                "motivo_de_posicion": _motivo_de_posicion(puntaje, posicion, empates, razones),
                "razones": razones,
                "limites_de_la_premisa": limites[modelo.clave],
            }
        )
    return resultado


def _hechos_del_autor(entradas: Entradas) -> list[str]:
    hechos = [f"Género elegido: {GENEROS.ETIQUETAS.get(clave, clave)}." for clave in entradas.generos]
    for campo in ("punto_de_vista", "focalizacion"):
        valor = entradas.directrices.get(campo)
        if valor:
            hechos.append(f"{campo.replace('_', ' ').capitalize()} guardado: {valor}.")
    return hechos


def confianza(ranking: Sequence[Mapping[str, Any]], evaluacion: Mapping[str, Any]) -> str:
    """Qué tan firme es el primer puesto. Nunca «alta»: las reglas son una guía, no una prueba.

    ``insuficiente``: ningún dato apunta a ningún modelo. ``baja``: hay datos, pero el primero apenas supera al
    segundo. ``moderada``: el primero supera al segundo por dos o más puntos y la premisa cubre al menos dos pistas.
    """
    if all(item["puntaje"] == 0 for item in ranking):
        return "insuficiente"
    margen = ranking[0]["puntaje"] - ranking[1]["puntaje"]
    if margen >= 2 and len(evaluacion["cubiertas"]) >= 2:
        return "moderada"
    return "baja"


def preguntas_pendientes(entradas: Entradas, evaluacion: Mapping[str, Any] | None = None) -> list[str]:
    """Decisiones que el autor debe tomar antes de que el ranking sea más preciso."""
    preguntas: list[str] = []
    if not entradas.premisa:
        preguntas.append("Escribe la premisa: sin ella, el ranking solo usa directrices y géneros.")
    if not entradas.generos:
        preguntas.append("Elige al menos un género si quieres que el ranking lo tenga en cuenta.")
    if entradas.directrices.get("punto_de_vista") is None and entradas.directrices.get("focalizacion") is None:
        preguntas.append("Decide el punto de vista o la focalización: es el dato que más pesa en el ranking.")
    if evaluacion is not None:
        preguntas.extend(p for p in evaluacion["preguntas"] if p not in preguntas and entradas.premisa)
    return preguntas


def analizar(entradas: Entradas) -> dict[str, Any]:
    """Todo lo que se muestra al autor: evaluación de la premisa, ranking, confianza y preguntas. Solo lectura."""
    evaluacion = PRE.evaluar(entradas.premisa, _hechos_del_autor(entradas))
    ranking = rankear(entradas, evaluacion)
    nivel = confianza(ranking, evaluacion)
    return {
        "evaluacion_premisa": evaluacion,
        "ranking": ranking,
        "confianza": nivel,
        "recomendacion_provisional": nivel != "moderada",
        "preguntas_pendientes": preguntas_pendientes(entradas, evaluacion),
    }


def etapas_de(clave: str) -> tuple[Etapa, ...]:
    return MODELOS_POR_CLAVE[clave].etapas


def pregunta_anclada(clave: str, etapa: Etapa, premisa: str | None) -> str:
    """Pregunta de la etapa, con la frase de la premisa que la engancha. Sin premisa, la pregunta queda genérica."""
    engancha = ENGANCHE.get((clave, etapa.nombre), ())
    for categoria in engancha:
        fragmento = PRE.fragmento_para(premisa, categoria)
        if fragmento:
            return f"{etapa.pregunta} Tu premisa menciona: «{fragmento}»."
    if engancha and premisa:
        return f"{etapa.pregunta} La premisa no lo muestra: decídelo tú."
    return etapa.pregunta


def etiqueta_genero(clave: str, custom_label: str | None) -> str:
    if clave == GENEROS.OTRO and custom_label:
        return custom_label
    return GENEROS.ETIQUETAS.get(clave, clave)
