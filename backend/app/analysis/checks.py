"""Verificaciones deterministas: los únicos problemas verificables.

Cada regla es mecánica y se puede comprobar a mano. Son problemas de
corrección tipográfica o gramatical, no juicios literarios. Las reglas
deliberadamente no miran la longitud de las frases, la ambigüedad ni la
ausencia de explicaciones: esos rasgos no son errores.
"""

from __future__ import annotations

import re

from app.analysis.provider import ProviderFinding

# Palabras funcionales que, repetidas de forma inmediata, casi nunca son intencionadas
# en prosa (con excepciones como diálogos marcados con puntuación, que la regla no toca).
FUNCTION_WORDS = ("de", "la", "el", "que", "y", "a", "en", "los", "las", "un", "una", "se", "por", "con", "para")

_REPEATED_FUNCTION_WORD = re.compile(
    r"(?<!\w)(" + "|".join(FUNCTION_WORDS) + r")[ \t]+\1(?!\w)",
    re.IGNORECASE,
)
_DOUBLE_SPACE = re.compile(r"(?<=\S)[ \t]{2,}(?=\S)")


def _unmatched_guillemets(fragment: str) -> list[tuple[int, str]]:
    """Posiciones de « o » sin pareja, en orden de aparición."""
    unmatched: list[tuple[int, str]] = []
    open_positions: list[int] = []
    for index, char in enumerate(fragment):
        if char == "«":
            open_positions.append(index)
        elif char == "»":
            if open_positions:
                open_positions.pop()
            else:
                unmatched.append((index, "»"))
    unmatched.extend((position, "«") for position in open_positions)
    return sorted(unmatched)


def run_deterministic_checks(fragment: str) -> list[ProviderFinding]:
    """Aplica las reglas al fragmento y devuelve los problemas encontrados."""
    findings: list[ProviderFinding] = []

    for match in _REPEATED_FUNCTION_WORD.finditer(fragment):
        findings.append(
            ProviderFinding(
                category="problema_verificable",
                quote=match.group(0),
                quote_offset=match.start(),
                explanation=(
                    f"La palabra «{match.group(1)}» aparece dos veces seguidas sin signo de puntuación "
                    "entre ambas. Es una comprobación de corrección, no un juicio sobre el estilo."
                ),
                effect=None,
                certainty="verificable",
            )
        )

    for match in _DOUBLE_SPACE.finditer(fragment):
        findings.append(
            ProviderFinding(
                category="problema_verificable",
                quote=match.group(0),
                quote_offset=match.start(),
                explanation=(
                    f"Hay {len(match.group(0))} espacios seguidos entre dos palabras. "
                    "Es una comprobación tipográfica."
                ),
                effect=None,
                certainty="verificable",
            )
        )

    for position, char in _unmatched_guillemets(fragment):
        missing = "de cierre »" if char == "«" else "de apertura «"
        findings.append(
            ProviderFinding(
                category="problema_verificable",
                quote=char,
                quote_offset=position,
                explanation=f"Este guion de diálogo o comilla «{char}» no tiene su pareja {missing}. "
                "Es una comprobación tipográfica.",
                effect=None,
                certainty="verificable",
            )
        )

    return sorted(findings, key=lambda item: item.quote_offset)
