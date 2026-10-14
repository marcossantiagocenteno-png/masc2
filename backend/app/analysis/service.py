"""Servicio de análisis editorial de fragmentos.

Flujo de ``analyze``:

1. Se carga la versión y se comprueba su hash. El texto original no se toca.
2. Se valida el rango del fragmento y su tamaño.
3. Se ejecutan las verificaciones deterministas y el proveedor.
4. Cada hallazgo se valida. Si uno falla, no se guarda nada.
5. Se guarda el análisis y sus hallazgos en una sola transacción.

Los hallazgos guardan posiciones absolutas dentro de la versión, pero la
validación se hace contra el fragmento que recibió el proveedor.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.checks import run_deterministic_checks
from app.analysis.categories import PROVENANCE_DETERMINISTIC, PROVENANCE_PROVIDER
from app.analysis.errors import AuthorizationRequired, FindingsRejected, ProviderFailed
from app.analysis.provider import AnalysisProvider, ProviderFinding
from app.analysis.validation import validate_finding
from app.db.models import AnalysisFinding, AnalysisRun, ManuscriptVersion
from app.texts.errors import ContentTooLarge, IntegrityFailure, NotFoundError, TextError, ValidationFailed
from app.texts.service import TextService

DETERMINISTIC_SOURCE = "verificacion_determinista"


class AnalysisService:
    """Ejecuta análisis y consulta los ya guardados. No modifica versiones."""

    def __init__(self, session: Session, text_service: TextService, max_analysis_chars: int) -> None:
        self._session = session
        self._texts = text_service
        self._max_chars = max_analysis_chars

    def analyze(
        self,
        version_id: int,
        start: int,
        end: int,
        provider: AnalysisProvider,
        *,
        external_authorized: bool = False,
    ) -> AnalysisRun:
        """Analiza el fragmento ``[start, end)`` de la versión y guarda el resultado.

        Un proveedor externo solo se llama si ``external_authorized`` es verdadero.
        La comprobación ocurre antes de cualquier llamada. No hay autorización
        persistente: cada análisis exige la suya.
        """
        version: ManuscriptVersion = self._texts.get_version(version_id)
        content = version.content

        if not 0 <= start < end <= len(content):
            raise ValidationFailed(
                f"rango de fragmento no válido: [{start}, {end}) en una versión de {len(content)} caracteres"
            )
        if end - start > self._max_chars:
            raise ContentTooLarge(
                f"el fragmento tiene {end - start} caracteres; el máximo es {self._max_chars}"
            )

        if provider.is_external and not external_authorized:
            raise AuthorizationRequired(
                f"el proveedor '{provider.name}' envía el fragmento fuera de este equipo: "
                "hace falta una autorización explícita en esta petición"
            )

        fragment = content[start:end]

        try:
            provider_findings = provider.analyze(fragment)
        except TextError:
            # Errores de dominio del proveedor (malformado, cita inválida...): se devuelven tal cual.
            raise
        except Exception as error:  # noqa: BLE001 - el mensaje no se expone: podría contener datos
            raise ProviderFailed(
                f"el proveedor '{provider.name}' falló ({type(error).__name__}). No se guardó nada."
            ) from None

        candidates: list[tuple[ProviderFinding, str, str]] = [
            (finding, PROVENANCE_DETERMINISTIC, DETERMINISTIC_SOURCE)
            for finding in run_deterministic_checks(fragment)
        ]
        candidates.extend(
            (finding, PROVENANCE_PROVIDER, provider.name) for finding in provider_findings
        )

        rows: list[AnalysisFinding] = []
        for index, (finding, provenance, source_name) in enumerate(candidates):
            reason = validate_finding(finding, fragment, provenance)
            if reason is not None:
                raise FindingsRejected(f"hallazgo {index} rechazado: {reason}")

            absolute_start = start + finding.quote_offset
            absolute_end = absolute_start + len(finding.quote)
            if content[absolute_start:absolute_end] != finding.quote:
                # Imposible si la validación anterior pasó; se comprueba igualmente.
                raise IntegrityFailure("la cita no coincide con la versión original")

            rows.append(
                AnalysisFinding(
                    category=finding.category,
                    provenance=provenance,
                    source_name=source_name,
                    quote=finding.quote,
                    start_offset=absolute_start,
                    end_offset=absolute_end,
                    line_number=content.count("\n", 0, absolute_start) + 1,
                    explanation=finding.explanation.strip(),
                    effect=(finding.effect or "").strip() or None,
                    certainty=finding.certainty,
                    justification=(finding.justification or "").strip() or None,
                )
            )

        run = AnalysisRun(
            version_id=version.id,
            fragment_start=start,
            fragment_end=end,
            fragment_text=fragment,
            provider_name=provider.name,
            provider_label=provider.label,
            provider_simulated=provider.is_simulated,
            model_name=getattr(provider, "model", None),
            sent_external=provider.is_external,
        )
        run.findings = rows
        self._session.add(run)
        self._session.commit()
        return run

    def list_runs(self, version_id: int) -> Sequence[AnalysisRun]:
        """Análisis de una versión, del más antiguo al más reciente, comprobados contra el texto."""
        version = self._texts.get_version(version_id)
        runs = list(
            self._session.scalars(
                select(AnalysisRun)
                .where(AnalysisRun.version_id == version.id)
                .order_by(AnalysisRun.id)
            ).all()
        )
        for run in runs:
            self._verify_run(run, version.content)
        return runs

    @staticmethod
    def _verify_run(run: AnalysisRun, content: str) -> None:
        """El fragmento guardado debe coincidir con la versión original."""
        if content[run.fragment_start : run.fragment_end] != run.fragment_text:
            raise IntegrityFailure(
                f"el análisis {run.id} no coincide con el texto de su versión"
            )
