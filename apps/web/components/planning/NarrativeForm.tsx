"use client";

import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError, DEVELOPMENT_STATUS_LABELS, type DevelopmentStatus, type NarrativeData } from "@/lib/api";
import { toNullable } from "@/lib/planning";
import { useDirty } from "./UnsavedChanges";

type Values = { premise: string; synopsis: string; genre: string; theme: string; tone: string; development_status: string };

function valuesOf(data: NarrativeData): Values {
  return {
    premise: data.premise ?? "",
    synopsis: data.synopsis ?? "",
    genre: data.genre ?? "",
    theme: data.theme ?? "",
    tone: data.tone ?? "",
    development_status: data.development_status ?? "",
  };
}

/**
 * Datos generales de la novela. Todos los campos son opcionales. Ver la advertencia de la sección:
 * estos campos no tienen estado de canon ni historial de decisiones.
 */
export function NarrativeForm({ projectId }: { projectId: number }) {
  const [baseline, setBaseline] = useState<Values | null>(null);
  const [values, setValues] = useState<Values | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    api
      .getNarrative(projectId)
      .then((data) => {
        if (!active) return;
        setBaseline(valuesOf(data));
        setValues(valuesOf(data));
      })
      .catch((reason: unknown) => {
        if (active) setLoadError(reason instanceof ApiError ? reason.message : "No se pudo cargar la visión general.");
      });
    return () => {
      active = false;
    };
  }, [projectId]);

  const dirty = values !== null && baseline !== null && JSON.stringify(values) !== JSON.stringify(baseline);
  useDirty(`narrativa:${projectId}`, dirty);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!values || !dirty) return;
    setBusy(true);
    setSaveError(null);
    setNotice(null);
    try {
      const saved = await api.updateNarrative(projectId, {
        premise: toNullable(values.premise),
        synopsis: toNullable(values.synopsis),
        genre: toNullable(values.genre),
        theme: toNullable(values.theme),
        tone: toNullable(values.tone),
        development_status: (values.development_status || null) as DevelopmentStatus | null,
      });
      setBaseline(valuesOf(saved));
      setValues(valuesOf(saved));
      setNotice("Visión general guardada.");
    } catch (reason) {
      // El formulario conserva lo escrito para corregirlo y volver a guardar.
      setSaveError(reason instanceof ApiError ? reason.message : "No se pudo guardar. Tus cambios siguen aquí.");
    } finally {
      setBusy(false);
    }
  }

  if (loadError) {
    return (
      <p role="alert" className="text-red-700">
        {loadError}
      </p>
    );
  }
  if (!values) return <p className="text-[var(--color-muted)]">Cargando visión general…</p>;

  const field = (name: keyof Values, label: string, multiline = false, hint?: string) => (
    <div className="flex flex-col gap-1">
      <label htmlFor={`narrativa-${name}`} className="text-sm font-medium">
        {label}
      </label>
      {multiline ? (
        <textarea
          id={`narrativa-${name}`}
          rows={3}
          value={values[name]}
          disabled={busy}
          onChange={(event) => setValues({ ...values, [name]: event.target.value })}
          className="rounded border border-[var(--color-muted)] bg-transparent px-3 py-2"
        />
      ) : (
        <input
          id={`narrativa-${name}`}
          value={values[name]}
          disabled={busy}
          onChange={(event) => setValues({ ...values, [name]: event.target.value })}
          className="rounded border border-[var(--color-muted)] bg-transparent px-3 py-2"
        />
      )}
      {hint ? <span className="text-xs text-[var(--color-muted)]">{hint}</span> : null}
    </div>
  );

  return (
    <form onSubmit={save} aria-label="Visión general de la novela" className="flex flex-col gap-5">
      <p className="rounded border border-[var(--color-muted)]/60 p-3 text-sm text-[var(--color-muted)]">
        Estos datos se pueden cambiar en cualquier momento, sin confirmación. Todavía no tienen las protecciones de canon
        ni el historial de decisiones que tienen personajes, lugares, trama, cronología y estructura.
      </p>
      {field("premise", "Premisa", true, "La idea central en pocas frases. Puede ser incompleta.")}
      {field("synopsis", "Sinopsis de trabajo", true, "Puede cambiar a medida que avanzas.")}
      {field("genre", "Género")}
      {field("theme", "Tema", true)}
      {field("tone", "Tono")}
      <div className="flex flex-col gap-1">
        <label htmlFor="narrativa-development_status" className="text-sm font-medium">
          Estado de desarrollo
        </label>
        <select
          id="narrativa-development_status"
          value={values.development_status}
          disabled={busy}
          onChange={(event) => setValues({ ...values, development_status: event.target.value })}
          className="rounded border border-[var(--color-muted)] bg-transparent px-3 py-2"
        >
          <option value="">Sin definir</option>
          {(Object.keys(DEVELOPMENT_STATUS_LABELS) as DevelopmentStatus[]).map((status) => (
            <option key={status} value={status}>
              {DEVELOPMENT_STATUS_LABELS[status]}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={!dirty || busy} className="rounded bg-[var(--color-ink)] px-4 py-2 text-[var(--color-paper)] disabled:opacity-50">
          {busy ? "Guardando…" : "Guardar visión general"}
        </button>
        {dirty ? <span className="text-sm text-[var(--color-muted)]">Hay cambios sin guardar.</span> : null}
      </div>
      {saveError ? (
        <p role="alert" className="text-sm text-red-700">
          {saveError}
        </p>
      ) : null}
      {notice ? (
        <p role="status" className="text-sm text-green-800">
          {notice}
        </p>
      ) : null}
    </form>
  );
}
