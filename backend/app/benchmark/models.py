"""Modelos Pydantic del benchmark literario.

Validan forma, rangos y valores permitidos. No calculan ni sugieren
puntuaciones de calidad: ese juicio corresponde a una evaluación real.

Escala de puntuación: enteros de 1 a 5 (ambos incluidos). Se usa
``StrictInt``, así que cadenas como ``"3"`` y decimales como ``3.0``
se rechazan.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StringConstraints,
    model_validator,
)

CASE_ID_PATTERN = r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$"
SCHEMA_VERSION = 1
MIN_SCORE = 1
MAX_SCORE = 5

Text = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4000),
]
ShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]
Score = Annotated[StrictInt, Field(ge=MIN_SCORE, le=MAX_SCORE)]
CaseId = Annotated[str, StringConstraints(pattern=CASE_ID_PATTERN)]


class Dimension(StrEnum):
    """Dimensiones de la rúbrica literaria inicial."""

    PROSE_VOICE = "prosa_y_voz"
    DRAMATURGY = "dramaturgia"
    CHARACTERS_DIALOGUE = "personajes_y_dialogo"
    FOCALIZATION = "focalizacion"
    CONTINUITY = "continuidad"


class EvaluationCriterion(BaseModel):
    """Criterio explícito para una dimensión.

    ``critical_defect_if`` describe qué convierte el problema en defecto
    crítico. ``preference_only_if`` describe cuándo el juicio es solo gusto
    y no debe penalizarse.
    """

    model_config = ConfigDict(extra="forbid")

    dimension: Dimension
    question: Text
    critical_defect_if: list[Text] = Field(default_factory=list)
    preference_only_if: list[Text] = Field(default_factory=list)


class BenchmarkCase(BaseModel):
    """Caso de prueba del benchmark.

    ``provenance`` es siempre ``ejemplo_ficticio``. El modelo no tiene
    campo para versiones de referencia: no se inventan textos aprobados.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    id: CaseId
    title: ShortText
    provenance: Literal["ejemplo_ficticio"]
    language: Literal["es"]
    assignment: Text
    narrative_context: Text
    constraints: list[Text] = Field(min_length=1, max_length=20)
    expected_properties: list[Text] = Field(min_length=1, max_length=20)
    dimensions_under_test: list[Dimension] = Field(min_length=1, max_length=5)
    evaluation_criteria: list[EvaluationCriterion] = Field(min_length=1, max_length=25)

    @model_validator(mode="after")
    def _check_dimensions(self) -> BenchmarkCase:
        if len(set(self.dimensions_under_test)) != len(self.dimensions_under_test):
            raise ValueError("dimensions_under_test contiene dimensiones repetidas")
        under_test = set(self.dimensions_under_test)
        criteria_dimensions = {criterion.dimension for criterion in self.evaluation_criteria}
        outside = criteria_dimensions - under_test
        if outside:
            names = ", ".join(sorted(d.value for d in outside))
            raise ValueError(f"hay criterios para dimensiones no evaluadas: {names}")
        missing = under_test - criteria_dimensions
        if missing:
            names = ", ".join(sorted(d.value for d in missing))
            raise ValueError(f"faltan criterios para dimensiones evaluadas: {names}")
        return self


class DimensionScore(BaseModel):
    """Puntuación de una dimensión, con justificación obligatoria.

    Regla: si hay defectos críticos, la puntuación no puede superar 2.
    Las notas estilísticas no afectan a la puntuación y no pueden
    mezclarse con los defectos críticos.
    """

    model_config = ConfigDict(extra="forbid")

    dimension: Dimension
    score: Score
    justification: Text
    critical_defects: list[Text] = Field(default_factory=list, max_length=20)
    stylistic_notes: list[Text] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _critical_defects_cap_score(self) -> DimensionScore:
        if self.critical_defects and self.score > 2:
            raise ValueError(
                "con defectos críticos la puntuación no puede superar 2"
            )
        return self


class LiteraryEvaluation(BaseModel):
    """Evaluación de un caso.

    Estados:
    - ``pendiente``: sin puntuaciones y sin evaluador.
    - ``completada``: con evaluador y una puntuación por dimensión, sin repetir.

    La coincidencia entre dimensiones evaluadas y ``dimensions_under_test``
    se comprueba en el validador, porque necesita el caso.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    case_id: CaseId
    status: Literal["pendiente", "completada"]
    assessor: ShortText | None = None
    scores: list[DimensionScore] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def _check_status(self) -> LiteraryEvaluation:
        dimensions = [score.dimension for score in self.scores]
        if len(set(dimensions)) != len(dimensions):
            raise ValueError("hay dimensiones puntuadas más de una vez")
        if self.status == "pendiente":
            if self.scores or self.assessor is not None:
                raise ValueError("una evaluación pendiente no puede tener puntuaciones ni evaluador")
        else:
            if self.assessor is None:
                raise ValueError("una evaluación completada necesita evaluador")
            if not self.scores:
                raise ValueError("una evaluación completada necesita puntuaciones")
        return self


class RubricLevel(BaseModel):
    """Descriptor de un nivel de la escala."""

    model_config = ConfigDict(extra="forbid")

    level: Score
    descriptor: Text


class RubricDimension(BaseModel):
    """Definición de una dimensión dentro de la rúbrica."""

    model_config = ConfigDict(extra="forbid")

    dimension: Dimension
    label: ShortText
    purpose: Text
    levels: list[RubricLevel] = Field(min_length=5, max_length=5)
    critical_defects: list[Text] = Field(min_length=1, max_length=20)
    stylistic_preferences: list[Text] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _check_levels(self) -> RubricDimension:
        levels = [entry.level for entry in self.levels]
        if levels != [MIN_SCORE, 2, 3, 4, MAX_SCORE]:
            raise ValueError("los niveles deben aparecer en orden del 1 al 5, sin repetir")
        return self


class Rubric(BaseModel):
    """Rúbrica completa. Debe definir exactamente las cinco dimensiones."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    name: ShortText
    scale: Literal["1-5"]
    dimensions: list[RubricDimension] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def _check_all_dimensions(self) -> Rubric:
        defined = [entry.dimension for entry in self.dimensions]
        if set(defined) != set(Dimension) or len(defined) != len(Dimension):
            raise ValueError("la rúbrica debe definir cada dimensión exactamente una vez")
        return self
