"use client";

import { usePathname } from "next/navigation";
import { useEffect, useId, useState, type ReactNode } from "react";
import {
  api,
  ApiError,
  formatDate,
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
  const panelId = useId();

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

  if (projectId === null) return null;

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

function Fila({ nombre, valor }: { nombre: string; valor: ReactNode }) {
  return (
    <>
      <dt className="ne-meta">{nombre}</dt>
      <dd>{valor}</dd>
    </>
  );
}
