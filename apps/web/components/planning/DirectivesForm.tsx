"use client";

import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError, type NarrativeDirectives } from "@/lib/api";
import { useDirty } from "./UnsavedChanges";

type Props = { projectId: number };

const SIN_DECIDIR = "";

const OPCIONES = {
  persona: [
    ["primera", "Primera persona"],
    ["segunda", "Segunda persona"],
    ["tercera", "Tercera persona"],
  ],
  tiempo_verbal: [
    ["presente", "Presente"],
    ["pasado", "Pasado"],
    ["futuro", "Futuro"],
    ["mixto", "Mixto"],
  ],
  tipo_narrador: [
    ["narrador_personaje", "Narrador-personaje"],
    ["narrador_externo", "Narrador externo"],
  ],
  punto_de_vista: [
    ["un_personaje", "Un personaje"],
    ["varios_personajes", "Varios personajes"],
    ["omnisciente", "Omnisciente"],
  ],
  focalizacion: [
    ["interna_fija", "Interna fija"],
    ["interna_variable", "Interna variable"],
    ["externa", "Externa"],
    ["omnisciente", "Omnisciente"],
  ],
} as const;

type Textos = "voz" | "estilo" | "intencion" | "limites" | "instrucciones";
type Valores = "persona" | "tiempo_verbal" | "tipo_narrador" | "punto_de_vista" | "focalizacion";

type Values = Record<Textos, string> & Record<Valores, string>;

function valuesOf(data: NarrativeDirectives | null): Values {
  return {
    voz: data?.voz ?? "",
    estilo: data?.estilo ?? "",
    intencion: data?.intencion ?? "",
    limites: data?.limites ?? "",
    instrucciones: data?.instrucciones ?? "",
    persona: data?.persona ?? SIN_DECIDIR,
    tiempo_verbal: data?.tiempo_verbal ?? SIN_DECIDIR,
    tipo_narrador: data?.tipo_narrador ?? SIN_DECIDIR,
    punto_de_vista: data?.punto_de_vista ?? SIN_DECIDIR,
    focalizacion: data?.focalizacion ?? SIN_DECIDIR,
  };
}

/**
 * Directrices narrativas: decisiones del autor, independientes entre sí. Ninguna viene marcada: «Sin decidir» significa
 * que el autor no ha elegido, no un valor por defecto. El tono y el género no se repiten aquí.
 */
export function DirectivesForm({ projectId }: Props) {
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
        setBaseline(valuesOf(data.directives));
        setValues(valuesOf(data.directives));
      })
      .catch((reason: unknown) => {
        if (active) setLoadError(reason instanceof ApiError ? reason.message : "No se pudieron cargar las directrices.");
      });
    return () => {
      active = false;
    };
  }, [projectId]);

  const dirty = values !== null && baseline !== null && JSON.stringify(values) !== JSON.stringify(baseline);
  useDirty(`directrices:${projectId}`, dirty);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!values || !dirty) return;
    setBusy(true);
    setSaveError(null);
    setNotice(null);
    const nulo = (valor: string) => (valor.trim() === "" ? null : valor.trim());
    try {
      const saved = await api.putDirectives(projectId, {
        voz: nulo(values.voz),
        estilo: nulo(values.estilo),
        intencion: nulo(values.intencion),
        limites: nulo(values.limites),
        instrucciones: nulo(values.instrucciones),
        persona: (values.persona || null) as NarrativeDirectives["persona"],
        tiempo_verbal: (values.tiempo_verbal || null) as NarrativeDirectives["tiempo_verbal"],
        tipo_narrador: (values.tipo_narrador || null) as NarrativeDirectives["tipo_narrador"],
        punto_de_vista: (values.punto_de_vista || null) as NarrativeDirectives["punto_de_vista"],
        focalizacion: (values.focalizacion || null) as NarrativeDirectives["focalizacion"],
      });
      setBaseline(valuesOf(saved));
      setValues(valuesOf(saved));
      setNotice("Directrices guardadas.");
    } catch (reason) {
      setSaveError(reason instanceof ApiError ? reason.message : "No se pudieron guardar. Tus cambios siguen aquí.");
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
  if (!values) return <p className="ne-meta">Cargando directrices…</p>;

  const select = (name: Valores, label: string, options: readonly (readonly [string, string])[]) => (
    <div className="flex flex-col gap-1">
      <label htmlFor={`directriz-${name}`} className="ne-label">
        {label}
      </label>
      <select
        id={`directriz-${name}`}
        value={values[name]}
        disabled={busy}
        onChange={(event) => setValues({ ...values, [name]: event.target.value })}
      >
        <option value={SIN_DECIDIR}>Sin decidir</option>
        {options.map(([valor, texto]) => (
          <option key={valor} value={valor}>
            {texto}
          </option>
        ))}
      </select>
    </div>
  );

  const texto = (name: Textos, label: string, multiline: boolean, hint?: string) => (
    <div className="flex flex-col gap-1">
      <label htmlFor={`directriz-${name}`} className="ne-label">
        {label}
      </label>
      {multiline ? (
        <textarea
          id={`directriz-${name}`}
          rows={3}
          value={values[name]}
          disabled={busy}
          onChange={(event) => setValues({ ...values, [name]: event.target.value })}
        />
      ) : (
        <input
          id={`directriz-${name}`}
          value={values[name]}
          disabled={busy}
          onChange={(event) => setValues({ ...values, [name]: event.target.value })}
        />
      )}
      {hint ? <span className="ne-hint">{hint}</span> : null}
    </div>
  );

  return (
    <form onSubmit={save} aria-label="Directrices narrativas" className="flex flex-col gap-5">
      <p className="ne-hint">
        Son decisiones del autor. Cada una es independiente de las demás; «Sin decidir» significa que todavía no has elegido.
        El tono se edita en la visión general.
      </p>
      {texto("voz", "Voz narrativa", false)}
      {select("persona", "Persona gramatical", OPCIONES.persona)}
      {select("tiempo_verbal", "Tiempo verbal", OPCIONES.tiempo_verbal)}
      {select("tipo_narrador", "Tipo de narrador", OPCIONES.tipo_narrador)}
      {select("punto_de_vista", "Punto de vista", OPCIONES.punto_de_vista)}
      {select("focalizacion", "Focalización", OPCIONES.focalizacion)}
      {texto("estilo", "Estilo y preferencias literarias", true)}
      {texto("intencion", "Intención de la novela", true)}
      {texto("limites", "Límites y preferencias estilísticas", true, "Lo que la escritura asistida no debe hacer.")}
      {texto("instrucciones", "Instrucciones adicionales", true)}

      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={!dirty || busy} className="ne-button ne-button--primary">
          {busy ? "Guardando…" : "Guardar directrices"}
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
