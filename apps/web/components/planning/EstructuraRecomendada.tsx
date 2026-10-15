"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type PropuestaEstructura, type RecomendacionesEstructura, type TipoMotivo } from "@/lib/api";
import { useDirty } from "@/components/planning/UnsavedChanges";

const TIPO_MOTIVO: Record<TipoMotivo, string> = {
  confirmado: "Dato tuyo",
  inferencia: "Inferencia de una regla",
  convencion: "Convención del género (opcional)",
  pregunta_pendiente: "Pregunta pendiente",
};

const VALOR: Record<string, string> = {
  un_personaje: "Un personaje",
  varios_personajes: "Varios personajes",
  omnisciente: "Omnisciente",
  interna_fija: "Interna fija",
  interna_variable: "Interna variable",
  externa: "Externa",
  primera: "Primera persona",
  segunda: "Segunda persona",
  tercera: "Tercera persona",
  narrador_personaje: "Narrador personaje",
  narrador_externo: "Narrador externo",
  presente: "Presente",
  pasado: "Pasado",
  futuro: "Futuro",
  mixto: "Mixto",
};

const CAMPOS_DIRECTRICES: Record<string, string> = {
  punto_de_vista: "Punto de vista",
  focalizacion: "Focalización",
  persona: "Persona",
  tiempo_verbal: "Tiempo verbal",
  tipo_narrador: "Narrador",
};

const CONFIANZA: Record<RecomendacionesEstructura["confianza"], string> = {
  insuficiente: "insuficiente",
  baja: "baja",
  moderada: "moderada",
};

const SUFICIENCIA: Record<"insuficiente" | "parcial" | "suficiente", string> = {
  insuficiente: "La premisa apenas muestra pistas.",
  parcial: "La premisa muestra algunas pistas, pero no todas.",
  suficiente: "La premisa muestra objetivo y obstáculo.",
};

const ESTADO: Record<PropuestaEstructura["estado"], string> = {
  pendiente: "Pendiente",
  aceptada: "Aceptada",
  rechazada: "Rechazada",
};

function nombreDelModelo(data: RecomendacionesEstructura, clave: string): string {
  return data.ranking.find((item) => item.clave === clave)?.nombre ?? clave;
}

/**
 * Recomendación de estructura (F2): ranking con sus motivos, datos usados, etapas propuestas.
 * Las etapas son propuestas: aceptarlas crea un acto provisional de origen IA, nunca canon.
 */
export function EstructuraRecomendada({ projectId, onActoCreado }: { projectId: number; onActoCreado: () => void }) {
  const [data, setData] = useState<RecomendacionesEstructura | null>(null);
  const [archived, setArchived] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<{ id: number; title: string; summary: string } | null>(null);

  const load = useCallback(async () => {
    try {
      const [recomendaciones, project] = await Promise.all([
        api.getRecomendacionesEstructura(projectId),
        api.getProject(projectId),
      ]);
      setData(recomendaciones);
      setArchived(project.status === "archivado");
      setError(null);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "No se pudieron cargar las recomendaciones.");
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  const original = editing ? data?.propuestas.find((item) => item.id === editing.id) ?? null : null;
  const dirty = editing !== null && original !== null && (editing.title !== original.title || editing.summary !== (original.summary ?? ""));
  useDirty("estructura-recomendada", dirty);

  async function run(action: () => Promise<unknown>, success: string, opciones: { acto?: boolean } = {}) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
      setNotice(success);
      await load();
      if (opciones.acto) onActoCreado();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "No se pudo completar la acción.");
    } finally {
      setBusy(false);
    }
  }

  if (!data) {
    return (
      <section aria-labelledby="recomendada-titulo" className="flex flex-col gap-3">
        <h2 id="recomendada-titulo" className="ne-section-title">
          Recomendación de estructura
        </h2>
        {error ? (
          <p role="alert" className="ne-notice ne-notice--danger">
            {error}
          </p>
        ) : (
          <p className="ne-meta">Cargando…</p>
        )}
      </section>
    );
  }

  const elegido = data.modelo_elegido;
  const pendientesDelModelo = elegido ? data.propuestas.some((p) => p.model_key === elegido && p.estado === "pendiente") : false;
  const lotes = Array.from(new Set(data.propuestas.map((p) => p.lote))).sort((a, b) => b - a);

  return (
    <section aria-labelledby="recomendada-titulo" className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h2 id="recomendada-titulo" className="ne-section-title">
          Recomendación de estructura
        </h2>
        <p className="ne-meta">
          Son propuestas para decidir. Elegir un modelo no cambia ninguna etapa existente, y una etapa aceptada es un acto
          provisional de origen IA: no es canon.
        </p>
      </header>

      {error ? (
        <p role="alert" className="ne-notice ne-notice--danger">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p role="status" className="ne-notice ne-notice--ok">
          {notice}
        </p>
      ) : null}

      <div className="ne-panel flex flex-col gap-3">
        <h3 className="ne-label">Evaluación de la premisa</h3>
        {data.recomendacion_provisional ? (
          <p role="note" className="ne-notice ne-notice--warn">
            Recomendación provisional: la confianza es {CONFIANZA[data.confianza]}. El orden sirve de punto de partida, no como
            certeza.
          </p>
        ) : (
          <p className="ne-notice ne-notice--ok">Confianza moderada: el primer modelo supera al segundo con margen.</p>
        )}
        <p className="ne-meta">{SUFICIENCIA[data.evaluacion_premisa.suficiencia]}</p>
        {data.evaluacion_premisa.hechos.length ? (
          <div className="flex flex-col gap-1">
            <p className="ne-label">Lo que escribiste</p>
            <ul className="ne-list">
              {data.evaluacion_premisa.hechos.map((hecho) => (
                <li key={hecho.texto} className="text-[0.9375rem]">
                  <span className="ne-badge">Dato tuyo</span> {hecho.texto}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {data.evaluacion_premisa.inferencias.length ? (
          <div className="flex flex-col gap-1">
            <p className="ne-label">Pistas que sugiere la premisa</p>
            <p className="ne-meta">Son hipótesis a revisar, con confianza baja. No son canon y no se guardan como tales.</p>
            <ul className="ne-list">
              {data.evaluacion_premisa.inferencias.map((inferencia) => (
                <li key={inferencia.texto} className="text-[0.9375rem]">
                  <span className="ne-badge">Inferencia · confianza baja</span> {inferencia.texto}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        <h3 className="ne-label">Datos que se usan</h3>
        <p className="ne-meta">Esto es todo lo que la recomendación toma de tu novela. Si cambias un dato, las propuestas ya generadas conservan el suyo.</p>
        <dl className="grid gap-x-4 gap-y-2 text-[0.9375rem] sm:grid-cols-[max-content_1fr]">
          <dt className="ne-meta">Premisa</dt>
          <dd>{data.datos.premisa ? <blockquote className="ne-prose">{data.datos.premisa}</blockquote> : "Sin premisa todavía."}</dd>
          <dt className="ne-meta">Géneros</dt>
          <dd>{data.datos.generos.length ? data.datos.generos.join(", ") : "Ninguno seleccionado."}</dd>
          {Object.entries(CAMPOS_DIRECTRICES).map(([campo, etiqueta]) => {
            const valor = data.datos.directrices[campo];
            return (
              <div key={campo} className="contents">
                <dt className="ne-meta">{etiqueta}</dt>
                <dd>{valor ? VALOR[valor] ?? valor : "Sin decidir."}</dd>
              </div>
            );
          })}
        </dl>
        {data.preguntas_pendientes.length ? (
          <div className="flex flex-col gap-1">
            <p className="ne-label">Preguntas pendientes</p>
            <ul className="ne-list">
              {data.preguntas_pendientes.map((pregunta) => (
                <li key={pregunta} className="ne-meta">
                  {pregunta}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>

      <div className="flex flex-col gap-3">
        <h3 className="ne-section-title">Modelos, del más al menos pertinente</h3>
        <p className="ne-meta">
          El orden sale de los datos de arriba. Cada motivo indica si es un dato tuyo, una inferencia de una regla o una
          convención del género que puedes ignorar.
        </p>
        <div className="grid gap-4 md:grid-cols-3">
          {data.ranking.map((modelo) => {
            const esElegido = modelo.clave === elegido;
            return (
              <article key={modelo.clave} aria-labelledby={`modelo-${modelo.clave}`} className="ne-panel flex flex-col gap-3">
                <h4 id={`modelo-${modelo.clave}`} className="font-medium">
                  {modelo.posicion}. {modelo.nombre}
                </h4>
                <p className="ne-meta">{modelo.motivo_de_posicion}</p>
                <div className="flex flex-col gap-2 text-[0.9375rem]">
                  <p>
                    <span className="ne-label">Pertinencia. </span>
                    {modelo.pertinencia}
                  </p>
                  <p>
                    <span className="ne-label">Favorece. </span>
                    {modelo.favorece}
                  </p>
                  <p>
                    <span className="ne-label">Limitaciones. </span>
                    {modelo.limitaciones}
                  </p>
                  <p className="ne-meta">
                    {modelo.origen} Ámbito: {modelo.ambito}. {modelo.numero_de_etapas} etapas.
                  </p>
                </div>
                {modelo.razones.length ? (
                  <ul className="ne-list flex flex-col gap-2">
                    {modelo.razones.map((razon) => (
                      <li key={`${razon.regla}-${razon.texto}`} className="text-[0.9375rem]">
                        <span className="ne-badge">{TIPO_MOTIVO[razon.tipo]}</span> {razon.texto}
                      </li>
                    ))}
                  </ul>
                ) : null}
                {modelo.limites_de_la_premisa.length ? (
                  <div className="flex flex-col gap-1 text-[0.9375rem]">
                    <p className="ne-label">Lo que la premisa no muestra</p>
                    {modelo.limites_de_la_premisa.map((limite) => (
                      <p key={limite}>{limite}</p>
                    ))}
                  </div>
                ) : null}
                <div className="mt-auto">
                  <button
                    type="button"
                    disabled={busy || archived || esElegido}
                    aria-pressed={esElegido}
                    onClick={() =>
                      void run(() => api.elegirModeloEstructura(projectId, modelo.clave), `Modelo elegido: ${modelo.nombre}.`)
                    }
                    className="ne-button ne-button--small"
                  >
                    {esElegido ? "Modelo elegido" : "Elegir este modelo"}
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      </div>

      <div className="flex flex-col gap-4">
        <h3 className="ne-section-title">Etapas propuestas</h3>
        {elegido ? (
          <div className="flex flex-col gap-2">
            <div>
              <button
                type="button"
                disabled={busy || archived || pendientesDelModelo}
                onClick={() =>
                  void run(
                    () => api.generarPropuestasEstructura(projectId, null),
                    `Propuestas generadas para «${nombreDelModelo(data, elegido)}». Ninguna crea un acto hasta que la aceptes.`,
                  )
                }
                className="ne-button ne-button--primary"
              >
                Generar etapas de «{nombreDelModelo(data, elegido)}»
              </button>
            </div>
            {pendientesDelModelo ? (
              <p className="ne-meta">Ya hay etapas pendientes de este modelo. Acéptalas o recházalas antes de generar otras.</p>
            ) : null}
          </div>
        ) : (
          <p className="ne-meta">Elige un modelo para generar sus etapas.</p>
        )}
        {archived ? <p className="ne-meta">El proyecto está archivado: no se generan ni deciden propuestas.</p> : null}

        {lotes.length === 0 ? <p className="ne-empty">Todavía no hay etapas propuestas.</p> : null}

        {lotes.map((lote) => {
          const etapas = data.propuestas.filter((p) => p.lote === lote).sort((a, b) => a.position - b.position);
          const nombre = nombreDelModelo(data, etapas[0].model_key);
          return (
            <div key={lote} className="flex flex-col gap-3">
              <h4 className="ne-label">
                Lote {lote}: {nombre}
              </h4>
              <ol className="flex flex-col gap-4">
                {etapas.map((etapa) => {
                  const anteriorPendiente = etapas.some((otra) => otra.position < etapa.position && otra.estado === "pendiente");
                  const enEdicion = editing?.id === etapa.id;
                  return (
                    <li key={etapa.id} className="ne-panel flex flex-col gap-3">
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <span className="font-medium">
                          {etapa.position + 1}. {etapa.title}
                        </span>
                        <span className="ne-badge">{ESTADO[etapa.estado]}</span>
                      </div>

                      <p className="text-[0.9375rem]">
                        <span className="ne-label">Función del modelo. </span>
                        {etapa.funcion}
                        <span className="ne-meta"> ({TIPO_MOTIVO.inferencia})</span>
                      </p>
                      <p className="text-[0.9375rem]">
                        <span className="ne-label">Decide tú. </span>
                        {etapa.pregunta}
                        <span className="ne-meta"> ({TIPO_MOTIVO.pregunta_pendiente})</span>
                      </p>
                      <p className="ne-meta">
                        {etapa.base_tipo === "confirmado"
                          ? "Base: la premisa y los datos guardados de tu novela."
                          : "Base: sin premisa. La función es genérica y la decides tú."}
                      </p>
                      {etapa.summary ? <p className="text-[0.9375rem]">Resumen: {etapa.summary}</p> : null}

                      {enEdicion && editing ? (
                        <form
                          className="flex flex-col gap-3"
                          onSubmit={(event) => {
                            event.preventDefault();
                            void run(
                              () =>
                                api.editarPropuestaEstructura(projectId, etapa.id, {
                                  title: editing.title,
                                  summary: editing.summary || null,
                                }),
                              "Propuesta guardada.",
                            );
                            setEditing(null);
                          }}
                        >
                          <label className="flex flex-col gap-1">
                            <span className="ne-label">Título del acto</span>
                            <input
                              required
                              maxLength={200}
                              value={editing.title}
                              onChange={(event) => setEditing({ ...editing, title: event.target.value })}
                            />
                          </label>
                          <label className="flex flex-col gap-1">
                            <span className="ne-label">Resumen (opcional, lo escribes tú)</span>
                            <textarea
                              rows={3}
                              maxLength={4000}
                              value={editing.summary}
                              onChange={(event) => setEditing({ ...editing, summary: event.target.value })}
                              className="ne-prose-field"
                            />
                          </label>
                          <div className="flex flex-wrap gap-2">
                            <button type="submit" disabled={busy} className="ne-button ne-button--primary ne-button--small">
                              Guardar cambios
                            </button>
                            <button type="button" onClick={() => setEditing(null)} className="ne-button ne-button--small">
                              Cancelar
                            </button>
                          </div>
                        </form>
                      ) : null}

                      {etapa.estado === "pendiente" && !enEdicion ? (
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            disabled={busy || archived}
                            onClick={() => setEditing({ id: etapa.id, title: etapa.title, summary: etapa.summary ?? "" })}
                            className="ne-button ne-button--small"
                          >
                            Editar
                          </button>
                          <button
                            type="button"
                            disabled={busy || archived || anteriorPendiente}
                            title={anteriorPendiente ? "Acepta o rechaza antes las etapas anteriores." : undefined}
                            onClick={() =>
                              void run(
                                () => api.aceptarPropuestaEstructura(projectId, etapa.id),
                                "Acto creado como provisional, de origen IA. No es canon: revísalo en la estructura.",
                                { acto: true },
                              )
                            }
                            className="ne-button ne-button--small ne-button--primary"
                          >
                            Aceptar como acto provisional
                          </button>
                          <button
                            type="button"
                            disabled={busy || archived}
                            onClick={() =>
                              void run(() => api.rechazarPropuestaEstructura(projectId, etapa.id), "Propuesta rechazada.")
                            }
                            className="ne-button ne-button--small"
                          >
                            Rechazar
                          </button>
                        </div>
                      ) : null}

                      <details className="text-[0.9375rem]">
                        <summary className="ne-meta cursor-pointer">Datos usados al generar esta etapa</summary>
                        <div className="mt-2 flex flex-col gap-1">
                          <p>Premisa: {etapa.entradas.premisa ?? "sin premisa"}</p>
                          <p>Géneros: {etapa.entradas.generos.length ? etapa.entradas.generos.join(", ") : "ninguno"}</p>
                          <p>
                            Directrices:{" "}
                            {Object.entries(etapa.entradas.directrices)
                              .filter(([, valor]) => valor)
                              .map(([campo, valor]) => `${CAMPOS_DIRECTRICES[campo] ?? campo}: ${VALOR[valor ?? ""] ?? valor}`)
                              .join("; ") || "sin decidir"}
                          </p>
                          <p>Reglas que sumaron: {etapa.entradas.reglas.length ? etapa.entradas.reglas.join(", ") : "ninguna"}</p>
                        </div>
                      </details>
                    </li>
                  );
                })}
              </ol>
            </div>
          );
        })}
      </div>
    </section>
  );
}
