"use client";

import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError, DEVELOPMENT_STATUS_LABELS, type DevelopmentStatus, type NarrativeData } from "@/lib/api";
import { toNullable } from "@/lib/planning";
import { useDirty } from "./UnsavedChanges";
import { SugerenciaCampo } from "@/components/asistente/SugerenciaCampo";

type Values = {
  premise: string;
  genres: string[];
  otherOn: boolean;
  otherGenre: string;
  tone: string;
  theme: string;
  development_status: string;
};

const OTRO = "otro";

function valuesOf(data: NarrativeData): Values {
  const active = data.genres ?? [];
  return {
    premise: data.premise ?? "",
    genres: active.filter((g) => g.key !== OTRO).map((g) => g.key),
    otherOn: active.some((g) => g.key === OTRO),
    otherGenre: active.find((g) => g.key === OTRO)?.custom_label ?? "",
    tone: data.tone ?? "",
    theme: data.theme ?? "",
    development_status: data.development_status ?? "",
  };
}

/**
 * Visión general: la premisa es el punto de partida de la novela. Los géneros se eligen de un catálogo, con «Otro»
 * para conservar valores propios. La sinopsis de trabajo ya no se muestra; su texto sigue guardado.
 */
export function NarrativeForm({ projectId }: { projectId: number }) {
  const [catalog, setCatalog] = useState<NarrativeData["genre_catalog"]>([]);
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
        setCatalog(data.genre_catalog);
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

  function toggleGenre(key: string) {
    if (!values) return;
    const genres = values.genres.includes(key) ? values.genres.filter((g) => g !== key) : [...values.genres, key];
    setValues({ ...values, genres });
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!values || !dirty) return;
    if (values.otherOn && values.otherGenre.trim() === "") {
      setSaveError("Escribe el nombre del género «Otro», o desmárcalo.");
      return;
    }
    setBusy(true);
    setSaveError(null);
    setNotice(null);
    try {
      await api.updateNarrative(projectId, {
        premise: toNullable(values.premise),
        theme: toNullable(values.theme),
        tone: toNullable(values.tone),
        development_status: (values.development_status || null) as DevelopmentStatus | null,
      });
      const generos = [
        ...values.genres.map((key) => ({ key })),
        ...(values.otherOn ? [{ key: OTRO, custom_label: values.otherGenre.trim() }] : []),
      ];
      await api.putGenres(projectId, generos);
      const refreshed = await api.getNarrative(projectId);
      setBaseline(valuesOf(refreshed));
      setValues(valuesOf(refreshed));
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
      <p role="alert" className="ne-notice ne-notice--danger">
        {loadError}
      </p>
    );
  }
  if (!values) return <p className="ne-meta">Cargando visión general…</p>;

  return (
    <form onSubmit={save} aria-label="Visión general de la novela" className="flex flex-col gap-6">
      <p className="ne-notice ne-notice--info">
        Estos datos se pueden cambiar en cualquier momento, sin confirmación. Todavía no tienen las protecciones de canon
        ni el historial de decisiones que tienen personajes, lugares, trama, cronología y estructura.
      </p>
      <div className="flex flex-col gap-1">
        <label htmlFor="narrativa-premise" className="ne-label">
          Premisa
        </label>
        <textarea
          id="narrativa-premise"
          rows={5}
          value={values.premise}
          disabled={busy}
          onChange={(event) => setValues({ ...values, premise: event.target.value })}
        />
        <span className="ne-hint">
          Punto de partida de la novela: la idea central en pocas frases. Todo lo demás se construye a partir de ella.
        </span>
        <SugerenciaCampo
          projectId={projectId}
          entidad="premisa"
          campo="premise"
          entidadId={null}
          valorActual={values.premise}
          etiqueta="Premisa"
          disabled={busy}
          onAceptar={(texto) => setValues((actual) => (actual ? { ...actual, premise: texto } : actual))}
        />
      </div>

      <fieldset className="flex flex-col gap-2" disabled={busy}>
        <legend className="ne-label">Géneros</legend>
        <span className="ne-hint">Puedes elegir varios. Son una clasificación de la obra, no una estructura.</span>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {catalog
            .filter((genre) => genre.key !== OTRO)
            .map((genre) => (
              <label key={genre.key} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={values.genres.includes(genre.key)}
                  onChange={() => toggleGenre(genre.key)}
                />
                <span>{genre.label}</span>
              </label>
            ))}
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={values.otherOn}
              onChange={(event) => setValues({ ...values, otherOn: event.target.checked })}
            />
            <span>Otro</span>
          </label>
        </div>
        {values.otherOn ? (
          <div className="flex flex-col gap-1">
            <label htmlFor="narrativa-otro-genero" className="ne-label">
              Nombre del género
            </label>
            <input
              id="narrativa-otro-genero"
              value={values.otherGenre}
              maxLength={120}
              onChange={(event) => setValues({ ...values, otherGenre: event.target.value })}
            />
          </div>
        ) : null}
      </fieldset>

      <div className="flex flex-col gap-1">
        <label htmlFor="narrativa-tone" className="ne-label">
          Tono
        </label>
        <input
          id="narrativa-tone"
          value={values.tone}
          disabled={busy}
          onChange={(event) => setValues({ ...values, tone: event.target.value })}
        />
        <span className="ne-hint">Lo decides tú. Las recomendaciones llegarán en una fase posterior, marcadas como propuestas.</span>
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="narrativa-theme" className="ne-label">
          Tema
        </label>
        <textarea
          id="narrativa-theme"
          rows={3}
          value={values.theme}
          disabled={busy}
          onChange={(event) => setValues({ ...values, theme: event.target.value })}
        />
        <SugerenciaCampo
          projectId={projectId}
          entidad="premisa"
          campo="theme"
          entidadId={null}
          valorActual={values.theme}
          etiqueta="Tema"
          disabled={busy}
          onAceptar={(texto) => setValues((actual) => (actual ? { ...actual, theme: texto } : actual))}
        />
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="narrativa-development_status" className="ne-label">
          Estado de desarrollo
        </label>
        <select
          id="narrativa-development_status"
          value={values.development_status}
          disabled={busy}
          onChange={(event) => setValues({ ...values, development_status: event.target.value })}
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
        <button type="submit" disabled={!dirty || busy} className="ne-button ne-button--primary">
          {busy ? "Guardando…" : "Guardar visión general"}
        </button>
        {dirty ? <span className="ne-meta">Hay cambios sin guardar.</span> : null}
      </div>
      {saveError ? (
        <p role="alert" className="ne-notice ne-notice--danger">
          {saveError}
        </p>
      ) : null}
      {notice ? (
        <p role="status" className="ne-notice ne-notice--ok">
          {notice}
        </p>
      ) : null}
    </form>
  );
}
