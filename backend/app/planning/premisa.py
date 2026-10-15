"""Evaluación determinista de la premisa (F2, corrección).

No interpreta el sentido de la premisa. Busca pistas léxicas visibles y separa tres cosas:

- ``hechos``: lo que el autor escribió y decidió (el texto, sus frases, sus géneros y sus directrices).
- ``inferencias``: pistas léxicas que sugieren un elemento dramático. Cada una muestra la palabra y la frase que la
  originaron, con confianza baja. Son hipótesis para revisar, nunca canon: ``canon`` es siempre falso.
- ``preguntas``: elementos que la premisa no muestra y que el autor debe decidir.

Un léxico simple falla con ironía, negación y sentido figurado. Por eso cada pista es visible y el autor puede
contradecirla. Las palabras se comparan sin acentos y en minúsculas.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Final

# Categorías de pistas. Cada una corresponde a un criterio «favorece» de algún modelo (ver recomendaciones.py).
PISTAS: Final[dict[str, tuple[str, ...]]] = {
    "objetivo": ("busca", "buscar", "quiere", "querer", "intenta", "intentar", "necesita", "necesitar", "pretende", "aspira", "decide", "decidir"),
    "obstaculo": ("amenaza", "amenazar", "impide", "impedir", "enfrenta", "enfrentar", "oculta", "ocultar", "traicion", "persigue", "perseguir", "peligro", "miente", "mentira", "engana", "enganar", "sabotea", "alterad"),
    "pregunta": ("descubre", "descubrir", "investiga", "investigar", "misterio", "desaparec", "secreto", "quien", "por que"),
    "tension": ("plazo", "antes de", "hasta que", "quedan", "horas", "dias", "semanas", "ultimo", "ultima", "cuenta atras"),
    "cambio": ("cambia", "cambiar", "transforma", "transformar", "aprende", "aprender", "pierde", "perder", "renuncia", "renunciar", "acepta", "aceptar", "ya no"),
}

CATEGORIAS: Final = tuple(PISTAS)

# Rótulos para mostrar al autor, con cada pista declarada como posible elemento y no como hecho.
ROTULO: Final[dict[str, str]] = {
    "objetivo": "Posible objetivo del protagonista",
    "obstaculo": "Posible obstáculo o conflicto",
    "pregunta": "Posible pregunta dramática o misterio",
    "tension": "Posible presión de tiempo o plazo",
    "cambio": "Posible cambio del protagonista",
}

# Pregunta que se hace al autor cuando la premisa no muestra la categoría.
PREGUNTA_SI_FALTA: Final[dict[str, str]] = {
    "objetivo": "¿Qué quiere conseguir el protagonista?",
    "obstaculo": "¿Qué le impide conseguirlo, y quién o qué lo impide?",
    "pregunta": "¿Qué pregunta debe responder la historia para el lector?",
    "tension": "¿Hay un plazo o una presión que empuje la historia?",
    "cambio": "¿Cómo cambia el protagonista, y lo ve venir el lector?",
}

_NO_LETRAS: Final = re.compile(r"[^a-z0-9?¿ ]+")


def _normalizar(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto.lower())
    sin_acentos = "".join(caracter for caracter in descompuesto if unicodedata.category(caracter) != "Mn")
    return re.sub(r"\s+", " ", _NO_LETRAS.sub(" ", sin_acentos)).strip()


def _frases(texto: str) -> list[str]:
    return [frase.strip() for frase in re.split(r"(?<=[.!?;])\s+|\n+", texto) if frase.strip()]


@dataclass(frozen=True)
class Pista:
    categoria: str
    palabra: str
    frase: str


def _buscar(premisa: str) -> list[Pista]:
    """Pistas en orden de aparición. Cada pista es una raíz o una palabra: coincide al principio de palabra, así que «alterad» cubre «alterados»."""
    pistas: list[Pista] = []
    for frase in _frases(premisa):
        normalizada = _normalizar(frase)
        for categoria, palabras in PISTAS.items():
            for palabra in palabras:
                if re.search(rf"\b{re.escape(palabra)}", normalizada):
                    pistas.append(Pista(categoria, palabra, frase))
                    break
        if "?" in frase or "¿" in frase:
            pistas.append(Pista("pregunta", "?", frase))
    return pistas


def pistas_de(premisa: str | None) -> list[Pista]:
    return _buscar(premisa) if premisa else []


def evaluar(premisa: str | None, hechos_del_autor: list[str]) -> dict[str, Any]:
    """Evaluación completa. ``hechos_del_autor`` son frases ya decididas por el autor (géneros, directrices)."""
    pistas = pistas_de(premisa)
    cubiertas = {categoria for categoria in CATEGORIAS if any(p.categoria == categoria for p in pistas)}
    hechos: list[dict[str, str]] = []
    if premisa:
        hechos.append({"tipo": "confirmado", "texto": f"La premisa tiene {len(_frases(premisa))} frase(s)."})
    hechos.extend({"tipo": "confirmado", "texto": texto} for texto in hechos_del_autor)

    inferencias: list[dict[str, Any]] = []
    vistos: set[tuple[str, str]] = set()
    for pista in pistas:
        clave = (pista.categoria, pista.frase)
        if clave in vistos:
            continue
        vistos.add(clave)
        palabra = "un signo de pregunta" if pista.palabra == "?" else f"«{pista.palabra}»"
        inferencias.append(
            {
                "tipo": "inferencia",
                "categoria": pista.categoria,
                "texto": f"{ROTULO[pista.categoria]}: la premisa usa {palabra} en «{pista.frase}».",
                "fragmento": pista.frase,
                "confianza": "baja",
                "canon": False,
            }
        )

    preguntas = [PREGUNTA_SI_FALTA[c] for c in CATEGORIAS if c not in cubiertas and premisa]
    if not premisa:
        preguntas.insert(0, "Escribe la premisa para que pueda evaluarla.")

    return {
        "hechos": hechos,
        "inferencias": inferencias,
        "preguntas": preguntas,
        "presente": bool(premisa),
        "cubiertas": sorted(cubiertas, key=CATEGORIAS.index),
        "suficiencia": _suficiencia(premisa, cubiertas),
    }


def _suficiencia(premisa: str | None, cubiertas: set[str]) -> str:
    if not premisa or not cubiertas:
        return "insuficiente"
    if len(cubiertas) >= 2:
        return "parcial" if not {"objetivo", "obstaculo"} <= cubiertas else "suficiente"
    return "insuficiente"


def fragmento_para(premisa: str | None, categoria: str) -> str | None:
    """Primera frase de la premisa que contiene una pista de la categoría, o ``None``."""
    for pista in pistas_de(premisa):
        if pista.categoria == categoria:
            return pista.frase
    return None
