"use client";

import { useEffect, useState } from "react";
import {
  api,
  ApiError,
  formatDate,
  type AnalysisCategory,
  type AnalysisFinding,
  type AnalysisRun,
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
  readSelection: () => ContentSelection | null;
};

/**
 * Análisis editorial de un fragmento. El análisis no modifica la versión:
 * solo muestra y guarda diagnósticos vinculados a ella.
 */
export function AnalysisPanel({ versionId, readSelection }: Props) {
  const [runs, setRuns] = useState<AnalysisRun[] | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    api
      .listAnalyses(versionId)
      .then((list) => {
        if (!active) return;
        setRuns(list);
        setSelectedId(list.length > 0 ? list[list.length - 1].id : null);
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : "Error desconocido.");
      });
    return () => {
      active = false;
    };
  }, [versionId]);

  async function handleAnalyze() {
    setError(null);
    const selection = readSelection();
    if (!selection) {
      setError("Selecciona un fragmento en el contenido de la versión antes de analizarlo.");
      return;
    }
    setBusy(true);
    try {
      const run = await api.analyzeFragment(versionId, {
        start_offset: selection.start,
        end_offset: selection.end,
      });
      const list = await api.listAnalyses(versionId);
      setRuns(list);
      setSelectedId(run.id);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "No se pudo completar el análisis.");
    } finally {
      setBusy(false);
    }
  }

  const selected = runs?.find((run) => run.id === selectedId) ?? null;

  return (
    <section aria-labelledby="analisis-titulo" className="flex flex-col gap-5">
      <h2 id="analisis-titulo" className="text-xl font-medium">
        Análisis editorial de un fragmento
      </h2>
      <p className="text-sm text-[var(--color-muted)]">
        El análisis examina el fragmento seleccionado y no modifica el texto. Sus resultados quedan guardados con esta versión.
      </p>

      <div className="flex flex-col gap-2">
        <button
          type="button"
          onClick={handleAnalyze}
          disabled={busy}
          className="self-start rounded bg-[var(--color-ink)] px-4 py-2 text-[var(--color-paper)] disabled:opacity-50"
        >
          {busy ? "Analizando…" : "Analizar la selección del contenido"}
        </button>
        {error ? (
          <p role="alert" className="text-sm text-red-700">
            {error}
          </p>
        ) : null}
      </div>

      {runs === null ? <p className="text-[var(--color-muted)]">Cargando análisis…</p> : null}
      {runs?.length === 0 ? (
        <p className="text-[var(--color-muted)]">Esta versión todavía no tiene análisis.</p>
      ) : null}

      {runs && runs.length > 0 ? (
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium">Análisis guardado</span>
          <select
            value={selectedId ?? ""}
            onChange={(event) => setSelectedId(Number(event.target.value))}
            className="rounded border border-[var(--color-muted)] bg-transparent px-3 py-2"
          >
            {runs.map((run) => (
              <option key={run.id} value={run.id}>
                Análisis {run.id} · {formatDate(run.created_at)} · caracteres {run.fragment_start}–{run.fragment_end}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {selected ? <RunView run={selected} /> : null}
    </section>
  );
}

function RunView({ run }: { run: AnalysisRun }) {
  return (
    <div className="flex flex-col gap-6">
      <div
        role="note"
        className={
          run.provider_simulated
            ? "rounded border-2 border-amber-700 bg-amber-50 p-3 text-sm font-medium text-amber-900"
            : "rounded border border-[var(--color-muted)] p-3 text-sm"
        }
      >
        {run.provider_simulated ? "⚠ " : ""}
        {run.provider_label}
        <span className="block font-normal">Proveedor: {run.provider_name}</span>
      </div>

      <div className="flex flex-col gap-1">
        <p className="text-sm font-medium">Fragmento analizado (caracteres {run.fragment_start}–{run.fragment_end})</p>
        <blockquote className="whitespace-pre-wrap border-l-4 border-[var(--color-muted)]/60 pl-3 font-serif italic">
          {run.fragment_text}
        </blockquote>
      </div>

      {SECTIONS.map((section) => {
        const items = run.findings.filter((finding) => finding.category === section.category);
        return (
          <section key={section.category} aria-labelledby={`seccion-${run.id}-${section.category}`} className="flex flex-col gap-3">
            <h3 id={`seccion-${run.id}-${section.category}`} className="text-lg font-medium">
              {section.title} <span className="text-sm font-normal text-[var(--color-muted)]">({items.length})</span>
            </h3>
            <p className="text-sm text-[var(--color-muted)]">{section.note}</p>
            {items.length === 0 ? <p className="text-sm text-[var(--color-muted)]">Ninguno en este fragmento.</p> : null}
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
    <article className="flex flex-col gap-2 border-l-2 border-[var(--color-muted)]/50 pl-4">
      <p className="flex flex-wrap gap-2 text-sm text-[var(--color-muted)]">
        <span>Línea {finding.line_number}</span>
        <span>· posiciones {finding.start_offset}–{finding.end_offset}</span>
        <span>· {CERTAINTY_LABEL[finding.certainty]}</span>
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
    </article>
  );
}
