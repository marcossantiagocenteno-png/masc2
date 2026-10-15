"use client";

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useId, useState, type ReactNode } from "react";
import { ANALISIS_GUARDADO } from "@/lib/workspace-events";
import {
  api,
  ApiError,
  formatDate,
  versionOps,
  type AnalysisRun,
  type Character,
  type PlotElement,
  type ProjectDetail,
  type StructureNode,
  type TimelineEvent,
} from "@/lib/api";

type Guardado = {
  project: ProjectDetail;
  personajes: number;
  lugares: number;
  acontecimientos: number;
  trama: Record<string, number>;
  capitulos: number;
  escenas: number;
  escenasConTexto: number;
};

/** Cuenta los elementos de trama por tipo. Solo cuentan los no archivados. */
function countByKind(items: PlotElement[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const item of items) counts[item.kind] = (counts[item.kind] ?? 0) + 1;
  return counts;
}

async function loadGuardado(projectId: number): Promise<Guardado> {
  const [project, personajes, lugares, trama, acontecimientos, estructura] = await Promise.all([
    api.getProject(projectId),
    api.listElements<Character>(projectId, "personajes"),
    api.listElements<{ id: number }>(projectId, "lugares"),
    api.listElements<PlotElement>(projectId, "elementos-trama"),
    api.listElements<TimelineEvent>(projectId, "acontecimientos"),
    api.listStructure(projectId, false),
  ]);
  const nodes: StructureNode[] = estructura;
  const escenas = nodes.filter((node) => node.kind === "escena");
  return {
    project,
    personajes: personajes.length,
    lugares: lugares.length,
    acontecimientos: acontecimientos.length,
    trama: countByKind(trama),
    capitulos: nodes.filter((node) => node.kind === "capitulo").length,
    escenas: escenas.length,
    escenasConTexto: escenas.filter((node) => node.escritura === "con_texto").length,
  };
}

type Ejecutado = { key: string; runs: AnalysisRun[] } | { key: string; error: string };

/** Ruta de una versión: ``proyecto/manuscrito/versión``, o null si no estamos en una versión. */
function versionKeyOf(pathname: string): string | null {
  const match = /^\/proyectos\/(\d+)\/manuscritos\/(\d+)\/versiones\/(\d+)/.exec(pathname);
  return match ? `${match[1]}/${match[2]}/${match[3]}` : null;
}

/**
 * Contexto de la novela abierta: columna derecha desde 1280 px y bajo el contenido por debajo.
 * Solo lee datos guardados. Cada cifra procede de la planificación o del manuscrito, no de una estimación.
 */
export function ContextPanel() {
  const pathname = usePathname();
  const projectId = /^\/proyectos\/(\d+)/.exec(pathname)?.[1] ?? null;
  const [open, setOpen] = useState(false);
  const [guardado, setGuardado] = useState<Guardado | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ejecutado, setEjecutado] = useState<Ejecutado | null>(null);
  const panelId = useId();
  const versionKey = versionKeyOf(pathname);

  useEffect(() => {
    if (projectId === null) return;
    let active = true;
    setGuardado(null);
    setError(null);
    loadGuardado(Number(projectId)).then(
      (data) => {
        if (active) setGuardado(data);
      },
      (reason: unknown) => {
        if (active) setError(reason instanceof ApiError ? reason.message : "No se pudo cargar el contexto de la novela.");
      },
    );
    return () => {
      active = false;
    };
  }, [projectId, pathname]);

  // Análisis realmente ejecutados sobre la versión abierta. Se piden solo al entrar en una versión.
  const cargarEjecutado = useCallback(
    (key: string): Promise<void> => {
      const [project, manuscript, version] = key.split("/").map(Number);
      return versionOps(project, manuscript, version).listAnalyses().then(
        (runs) => setEjecutado({ key, runs }),
        (reason: unknown) =>
          setEjecutado({
            key,
            error: reason instanceof ApiError ? reason.message : "No se pudieron cargar los análisis de esta versión.",
          }),
      );
    },
    [],
  );

  useEffect(() => {
    if (versionKey === null) return;
    void cargarEjecutado(versionKey);
    // Un análisis nuevo de esta versión se anuncia y vuelve a leerse: el bloque no queda desactualizado.
    const onAnalisis = () => void cargarEjecutado(versionKey);
    window.addEventListener(ANALISIS_GUARDADO, onAnalisis);
    return () => window.removeEventListener(ANALISIS_GUARDADO, onAnalisis);
  }, [versionKey, cargarEjecutado]);

  if (projectId === null) return null;
  const ejecutadoActual = ejecutado && versionKey !== null && ejecutado.key === versionKey ? ejecutado : null;

  return (
    <section aria-labelledby={`${panelId}-titulo`} className="ne-workspace__context">
      <div className="ne-workspace__contexto-cabecera">
        <h2 id={`${panelId}-titulo`} className="ne-kicker">
          Contexto de la novela
        </h2>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((value) => !value)}
          className="ne-button ne-button--small ne-workspace__toggle"
        >
          {open ? "Ocultar contexto de la novela" : "Mostrar contexto de la novela"}
        </button>
      </div>
      <div id={panelId} className={`ne-workspace__panel ${open ? "ne-workspace__panel--open" : ""}`}>
        {error ? (
          <p role="alert" className="ne-notice ne-notice--danger">
            {error}
          </p>
        ) : null}
        {guardado === null && !error ? <p className="ne-meta">Cargando…</p> : null}
        {guardado ? <GuardadoBloque data={guardado} /> : null}
        {versionKey !== null ? <EjecutadoBloque estado={ejecutadoActual} /> : null}
      </div>
    </section>
  );
}

function GuardadoBloque({ data }: { data: Guardado }) {
  const { project } = data;
  return (
    <section aria-labelledby="contexto-guardado" className="flex flex-col gap-3">
      <h3 id="contexto-guardado" className="ne-subtitle">
        Guardado
      </h3>
      <p className="ne-hint">Datos guardados en la novela. Sin estimaciones.</p>
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-2 text-sm">
        <Fila nombre="Manuscritos" valor={String(project.manuscript_count)} />
        <Fila
          nombre="Última actividad"
          valor={project.last_activity_at ? formatDate(project.last_activity_at) : "Sin actividad"}
        />
        <Fila nombre="Personajes" valor={String(data.personajes)} />
        <Fila nombre="Lugares" valor={String(data.lugares)} />
        <Fila nombre="Acontecimientos" valor={String(data.acontecimientos)} />
        <Fila
          nombre="Trama"
          valor={`conflictos ${data.trama.conflicto ?? 0} · subtramas ${data.trama.subtrama ?? 0} · misterios ${
            data.trama.misterio ?? 0
          } · preguntas abiertas ${data.trama.pregunta_abierta ?? 0}`}
        />
        <Fila nombre="Capítulos" valor={String(data.capitulos)} />
        <Fila nombre="Escenas" valor={String(data.escenas)} />
        <Fila
          nombre="Escenas con texto"
          valor={data.escenas === 0 ? "Ninguna escena todavía" : `${data.escenasConTexto} de ${data.escenas}`}
        />
      </dl>
    </section>
  );
}

function EjecutadoBloque({ estado }: { estado: Ejecutado | null }) {
  return (
    <section aria-labelledby="contexto-ejecutado" className="flex flex-col gap-3">
      <h3 id="contexto-ejecutado" className="ne-subtitle">
        Ejecutado
      </h3>
      <p className="ne-hint">Análisis realmente ejecutados sobre esta versión.</p>
      {estado === null ? <p className="ne-meta">Cargando…</p> : null}
      {estado && "error" in estado ? (
        <p role="alert" className="ne-notice ne-notice--danger">
          {estado.error}
        </p>
      ) : null}
      {estado && "runs" in estado && estado.runs.length === 0 ? (
        <p className="ne-meta">Esta versión no tiene análisis ejecutados.</p>
      ) : null}
      {estado && "runs" in estado && estado.runs.length > 0 ? <ResumenAnalisis runs={estado.runs} /> : null}
    </section>
  );
}

/** Resumen de los análisis guardados. El tipo de cada uno se indica con texto, no solo con etiquetas. */
function ResumenAnalisis({ runs }: { runs: AnalysisRun[] }) {
  const reales = runs.filter((run) => run.sent_external).length;
  const simulados = runs.length - reales;
  const ultimo = runs[runs.length - 1];
  const tipo = ultimo.sent_external ? `proveedor real (${ultimo.provider_name})` : "analizador simulado, no es una IA";
  return (
    <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-2 text-sm">
      <Fila nombre="Análisis" valor={`${runs.length} en total · ${simulados} simulados · ${reales} con proveedor real`} />
      <Fila nombre="Último" valor={`${formatDate(ultimo.created_at)} · ${tipo}`} />
      <Fila nombre="Fragmento" valor={`caracteres ${ultimo.fragment_start}–${ultimo.fragment_end}`} />
    </dl>
  );
}

function Fila({ nombre, valor }: { nombre: string; valor: ReactNode }) {
  return (
    <>
      <dt className="ne-meta">{nombre}</dt>
      <dd>{valor}</dd>
    </>
  );
}
