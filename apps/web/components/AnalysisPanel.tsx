"use client";

import { useEffect, useState } from "react";
import {
  api,
  ApiError,
  formatDate,
  type AnalysisCategory,
  type AnalysisFinding,
  type AnalysisProviderStatus,
  type AnalysisRun,
  type ExternalAuthorization,
  type VersionOps,
} from "@/lib/api";

/** Selección del contenido de la versión, en posiciones de caracteres. */
export type ContentSelection = { start: number; end: number; quote: string };

/** Orden y títulos de las categorías. Cada una se muestra por separado. */
const SECTIONS: { category: AnalysisCategory; title: string; note: string }[] = [
  {
    category: "problema_verificable",
    title: "Problemas verificables",
    note: "Comprobaciones mecánicas de corrección tipográfica o gramatical. No son juicios literarios.",
  },
  {
    category: "observacion_literaria",
    title: "Observaciones literarias",
    note: "Lecturas argumentadas, con su efecto y su grado de certeza.",
  },
  {
    category: "inferencia_incierta",
    title: "Inferencias inciertas",
    note: "Conclusiones que el texto no fija del todo.",
  },
  {
    category: "preferencia_de_gusto",
    title: "Preferencias de gusto (no son errores)",
    note: "Preferencias personales. No deben corregirse como fallos del texto.",
  },
  {
    category: "elemento_a_preservar",
    title: "Elementos que funcionan y conviene preservar",
    note: "Rasgos que el análisis considera eficaces en este fragmento.",
  },
];

const CERTAINTY_LABEL: Record<AnalysisFinding["certainty"], string> = {
  verificable: "Verificable",
  alta: "Certeza alta",
  media: "Certeza media",
  baja: "Certeza baja",
  no_aplica: "No aplica (gusto)",
};

type Props = {
  versionId: number;
  /** Número de la versión, para identificarla en el resultado. */
  versionNumber?: number;
  /** Operaciones de la versión con su ámbito de proyecto (ver ``versionOps``). */
  ops: VersionOps;
  readSelection: () => ContentSelection | null;
};

/**
 * Análisis editorial de un fragmento. El análisis no modifica la versión:
 * solo muestra y guarda diagnósticos vinculados a ella.
 */
export function AnalysisPanel({ versionId, versionNumber, ops, readSelection }: Props) {
  const [runs, setRuns] = useState<AnalysisRun[] | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [provider, setProvider] = useState<AnalysisProviderStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Fragmento pendiente de confirmación de envío externo. Nunca se guarda entre análisis.
  const [pendingExternal, setPendingExternal] = useState<ContentSelection | null>(null);
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.all([ops.listAnalyses(), api.getAnalysisProvider()])
      .then(([list, status]) => {
        if (!active) return;
        setRuns(list);
        setProvider(status);
        setSelectedId(list.length > 0 ? list[list.length - 1].id : null);
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : "Error desconocido.");
      });
    return () => {
      active = false;
    };
  }, [versionId]);

  function resetExternalStep() {
    setPendingExternal(null);
    setAuthorized(false);
  }

  async function runAnalysis(selection: ContentSelection, authorization?: ExternalAuthorization) {
    setError(null);
    setBusy(true);
    try {
      const run = await ops.analyzeFragment({
        start_offset: selection.start,
        end_offset: selection.end,
        ...(authorization ? { external_authorization: authorization } : {}),
      });
      const list = await ops.listAnalyses();
      setRuns(list);
      setSelectedId(run.id);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "No se pudo completar el análisis.");
    } finally {
      setBusy(false);
      resetExternalStep();
    }
  }

  /** Lee la selección. Con proveedor simulado analiza directamente; con uno externo, pide confirmación. */
  function handleAnalyzeClick() {
    setError(null);
    const selection = readSelection();
    if (!selection) {
      setError("Selecciona un fragmento en el contenido de la versión antes de analizarlo.");
      return;
    }
    if (provider?.is_external) {
      setPendingExternal(selection);
      setAuthorized(false);
      return;
    }
    void runAnalysis(selection);
  }

  function handleConfirmExternal() {
    if (!pendingExternal || !provider?.name || !authorized) return;
    void runAnalysis(pendingExternal, {
      provider: provider.name,
      scope: "fragmento_seleccionado",
      acknowledged: true,
    });
  }

  const selected = runs?.find((run) => run.id === selectedId) ?? null;
  const unavailable = provider !== null && !provider.configured;

  return (
    <section aria-labelledby="analisis-titulo" className="flex flex-col gap-5">
      <h2 id="analisis-titulo" className="ne-section-title">
        Análisis editorial de un fragmento
      </h2>
      <p className="ne-meta">
        El análisis examina el fragmento seleccionado y no modifica el texto. Sus resultados quedan guardados con esta versión.
      </p>

      <ProviderNotice provider={provider} />

      {unavailable ? null : (
        <div className="flex flex-col gap-2">
          <button
            type="button"
            onClick={handleAnalyzeClick}
            disabled={busy || provider === null || pendingExternal !== null}
            className="self-start ne-button ne-button--primary"
          >
            {busy
              ? "Analizando…"
              : provider?.is_external
                ? "Revisar envío a Anthropic del fragmento seleccionado"
                : "Analizar la selección del contenido"}
          </button>
        </div>
      )}

      {pendingExternal && provider ? (
        <ExternalConfirmation
          selection={pendingExternal}
          model={provider.model_name}
          authorized={authorized}
          busy={busy}
          onAuthorizedChange={setAuthorized}
          onConfirm={handleConfirmExternal}
          onCancel={resetExternalStep}
        />
      ) : null}

      {error ? (
        <p role="alert" className="ne-notice ne-notice--danger">
          {error}
        </p>
      ) : null}

      {runs === null ? <p className="ne-meta">Cargando análisis…</p> : null}
      {runs?.length === 0 ? <p className="ne-empty">Esta versión todavía no tiene análisis.</p> : null}

      {runs && runs.length > 0 ? (
        <label className="flex flex-col gap-1">
          <span className="ne-label">Análisis guardado</span>
          <select
            value={selectedId ?? ""}
            onChange={(event) => setSelectedId(Number(event.target.value))}
            
          >
            {runs.map((run) => (
              <option key={run.id} value={run.id}>
                Análisis {run.id} · {run.sent_external ? "proveedor real" : "simulado"} · {formatDate(run.created_at)} · caracteres {run.fragment_start}–{run.fragment_end}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {selected ? <RunView run={selected} versionNumber={versionNumber} /> : null}
    </section>
  );
}

/** Estado del proveedor: visible antes de cualquier análisis. */
function ProviderNotice({ provider }: { provider: AnalysisProviderStatus | null }) {
  if (provider === null) return null;
  if (!provider.configured) {
    return (
      <div role="note" className="ne-notice ne-notice--danger">
        <span className="font-medium">Proveedor de análisis no disponible.</span> {provider.reason}
      </div>
    );
  }
  if (provider.is_external) {
    return (
      <div role="note" className="ne-notice ne-notice--info">
        <span className="font-medium">Proveedor externo configurado: Anthropic.</span> Cada análisis envía solo el
        fragmento que selecciones y exige tu confirmación. Modelo: {provider.model_name}.
      </div>
    );
  }
  return (
    <div role="note" className="ne-notice ne-notice--warn">
      Proveedor activo: analizador simulado. No envía nada fuera de este equipo y no es una IA.
    </div>
  );
}

/** Paso de confirmación: muestra el fragmento exacto que se enviará, antes de enviarlo. */
function ExternalConfirmation({
  selection,
  model,
  authorized,
  busy,
  onAuthorizedChange,
  onConfirm,
  onCancel,
}: {
  selection: ContentSelection;
  model: string | null;
  authorized: boolean;
  busy: boolean;
  onAuthorizedChange: (value: boolean) => void;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div role="dialog" aria-modal="false" aria-labelledby="confirmar-envio" className="ne-panel flex flex-col gap-3 border-[var(--color-accent)]">
      <h3 id="confirmar-envio" className="ne-subtitle">
        Confirmar envío a Anthropic
      </h3>
      <p className="text-sm">
        El texto seleccionado se enviará a Anthropic{model ? ` (modelo ${model})` : ""} para su procesamiento. Se envía
        únicamente este fragmento ({selection.end - selection.start} caracteres, posiciones {selection.start}–
        {selection.end}). No se envían el manuscrito completo, otras versiones ni los comentarios.
      </p>
      <blockquote className="whitespace-pre-wrap border-l-2 border-[var(--color-accent)] pl-4 font-serif italic">
        {selection.quote}
      </blockquote>
      <label className="flex items-start gap-2 text-sm">
        <input
          type="checkbox"
          checked={authorized}
          onChange={(event) => onAuthorizedChange(event.target.checked)}
          className="mt-1"
        />
        <span>Autorizo el envío de este fragmento a Anthropic. Esta autorización vale solo para este análisis.</span>
      </label>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onConfirm}
          disabled={!authorized || busy}
          className="ne-button ne-button--primary"
        >
          {busy ? "Enviando…" : "Enviar a Anthropic y analizar"}
        </button>
        <button type="button" onClick={onCancel} disabled={busy} className="ne-button">
          Cancelar
        </button>
      </div>
    </div>
  );
}

function RunView({ run, versionNumber }: { run: AnalysisRun; versionNumber?: number }) {
  return (
    <div className="flex flex-col gap-8">
      <div role="note" className={run.sent_external ? "ne-notice ne-notice--info" : "ne-notice ne-notice--warn"}>
        {run.sent_external
          ? "ANÁLISIS CON PROVEEDOR REAL: el fragmento se envió a Anthropic."
          : "ANALIZADOR SIMULADO: no es una evaluación literaria de ninguna IA."}
        <span className="block font-normal">
          Proveedor: {run.provider_name}
          {run.model_name ? ` · modelo: ${run.model_name}` : ""}
        </span>
      </div>

      <div className="flex flex-col gap-2">
        <p className="ne-label">Fragmento analizado (caracteres {run.fragment_start}–{run.fragment_end})</p>
        <p className="ne-meta">
          {versionNumber !== undefined ? `Versión ${versionNumber} · ` : ""}Análisis {run.id} · {formatDate(run.created_at)}
        </p>
        <blockquote className="whitespace-pre-wrap border-l-2 border-[var(--color-accent)] pl-4 font-serif text-[1.0625rem] leading-relaxed">
          {run.fragment_text}
        </blockquote>
      </div>

      {SECTIONS.map((section) => {
        const items = run.findings.filter((finding) => finding.category === section.category);
        return (
          <section key={section.category} aria-labelledby={`seccion-${run.id}-${section.category}`} className="flex flex-col gap-3 border-t border-[var(--color-line)] pt-8">
            <h3 id={`seccion-${run.id}-${section.category}`} className="ne-subtitle">
              {section.title} <span className="ne-meta">({items.length})</span>
            </h3>
            <p className="ne-meta">{section.note}</p>
            {items.length === 0 ? <p className="ne-meta">Ninguno en este fragmento.</p> : null}
            {items.map((finding) => (
              <FindingView key={finding.id} finding={finding} />
            ))}
          </section>
        );
      })}
    </div>
  );
}

function FindingView({ finding }: { finding: AnalysisFinding }) {
  const origin =
    finding.provenance === "determinista"
      ? "Verificación determinista"
      : `Proveedor «${finding.source_name}»${finding.source_name === "simulado" ? " (SIMULADO)" : ""}`;
  return (
    <article className="flex flex-col gap-2 border-l-2 border-[var(--color-line)] pl-4">
      <p className="ne-meta flex flex-wrap items-center gap-x-3 gap-y-2">
        <span>Línea {finding.line_number}</span>
        <span>· posiciones {finding.start_offset}–{finding.end_offset}</span>
        <span className="ne-badge">{CERTAINTY_LABEL[finding.certainty]}</span>
        <span>· {origin}</span>
      </p>
      <blockquote className="whitespace-pre-wrap font-serif italic">«{finding.quote}»</blockquote>
      <p className="whitespace-pre-wrap">{finding.explanation}</p>
      {finding.effect ? (
        <p className="whitespace-pre-wrap text-sm">
          <span className="font-medium">Efecto: </span>
          {finding.effect}
        </p>
      ) : null}
      {finding.justification ? (
        <p className="whitespace-pre-wrap text-sm">
          <span className="font-medium">Justificación: </span>
          {finding.justification}
        </p>
      ) : null}
    </article>
  );
}
