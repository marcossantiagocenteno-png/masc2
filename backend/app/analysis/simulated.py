"""Analizador simulado: prueba el flujo, no evalúa nada.

Este proveedor no es una IA ni un juicio literario. Produce únicamente datos
estructurales del fragmento (cuántas frases hay y cuál es la más larga). Cada
hallazgo lleva el prefijo «[Simulado]» y la respuesta marca el proveedor como
simulado, para que nadie confunda esto con una evaluación real.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.analysis.provider import ProviderFinding

LABEL = (
    "ANALIZADOR SIMULADO: no es una evaluación literaria de ninguna IA. "
    "Sirve para probar el flujo de análisis."
)

_SENTENCE = re.compile(r"[^.!?…\n]*[.!?…]+|[^.!?…\n]+")


@dataclass(frozen=True)
class _Sentence:
    text: str
    start: int

    @property
    def words(self) -> int:
        return len(self.text.split())


def split_sentences(fragment: str) -> list[_Sentence]:
    """Frases con su posición dentro del fragmento. Ignora trozos sin letras."""
    sentences: list[_Sentence] = []
    for match in _SENTENCE.finditer(fragment):
        raw = match.group(0)
        stripped = raw.strip()
        if not any(char.isalpha() for char in stripped):
            continue
        leading = len(raw) - len(raw.lstrip())
        sentences.append(_Sentence(text=stripped, start=match.start() + leading))
    return sentences


class SimulatedAnalyzer:
    """Proveedor simulado. Determinista: el mismo fragmento produce siempre lo mismo."""

    name = "simulado"
    label = LABEL
    is_simulated = True
    is_external = False

    def analyze(self, fragment: str) -> list[ProviderFinding]:
        sentences = split_sentences(fragment)
        if not sentences:
            return []
        longest = max(sentences, key=lambda sentence: sentence.words)
        return [
            ProviderFinding(
                category="observacion_literaria",
                quote=longest.text,
                quote_offset=longest.start,
                explanation=(
                    f"[Simulado] El fragmento tiene {len(sentences)} frases. "
                    f"La más larga tiene {longest.words} palabras."
                ),
                effect="Es un dato de longitud. Por sí solo no indica calidad.",
                certainty="alta",
                justification="Recuento de frases y palabras sobre el fragmento; no requiere juicio literario.",
            ),
            ProviderFinding(
                category="preferencia_de_gusto",
                quote=longest.text,
                quote_offset=longest.start,
                explanation=(
                    "[Simulado] Si prefiere frases más breves, esta es un candidato. "
                    "Es una preferencia, no un error."
                ),
                effect=None,
                certainty="no_aplica",
                justification="Se deduce solo de la longitud de la frase, sin juicio sobre su calidad.",
            ),
        ]
