"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError, type ElementRoute, type NarrativeLink, type StructureNode } from "@/lib/api";
import { RELATION_LABELS } from "@/lib/planning";
import { CanonBadge } from "./CanonBadge";

type Props = {
  projectId: number;
  route: ElementRoute;
  elementId: number;
  includeArchived: boolean;
};

/**
 * Escenas en las que aparece un elemento. Solo muestra vínculos que ya existen: los vínculos se crean
 * desde la escena, nunca desde aquí ni automáticamente.
 */
export function RelatedScenes({ projectId, route, elementId, includeArchived }: Props) {
  const [links, setLinks] = useState<NarrativeLink[] | null>(null);
  const [scenes, setScenes] = useState<Map<number, StructureNode>>(new Map());
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLinks(null);
    setError(null);
    Promise.all([
      api.listElementLinks(projectId, route, elementId, includeArchived),
      api.listStructure(projectId, true),
    ])
      .then(([found, structure]) => {
        if (!active) return;
        setLinks(found.filter((link) => link.source_kind === "escena" || link.target_kind === "escena"));
        setScenes(new Map(structure.filter((node) => node.kind === "escena").map((node) => [node.id, node])));
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof ApiError ? reason.message : "No se pudieron cargar las escenas relacionadas.");
      });
    return () => {
      active = false;
    };
  }, [projectId, route, elementId, includeArchived]);

  return (
    <section aria-labelledby="escenas-relacionadas" className="flex flex-col gap-3">
      <h3 id="escenas-relacionadas" className="ne-subtitle">
        Escenas relacionadas
      </h3>
      {error ? (
        <p role="alert" className="ne-notice ne-notice--danger">
          {error}
        </p>
      ) : null}
      {links === null && !error ? <p className="ne-meta">Cargando escenas…</p> : null}
      {links?.length === 0 ? (
        <p className="ne-meta">
          Todavía no aparece en ninguna escena. Los vínculos se crean desde cada escena.
        </p>
      ) : null}
      <ul className="flex flex-col divide-y divide-[var(--color-muted)]/40">
        {links?.map((link) => {
          const sceneId = link.target_kind === "escena" ? link.target_id : link.source_id;
          const scene = scenes.get(sceneId);
          const title = scene?.title?.trim() || "Escena sin título";
          return (
            <li key={link.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span className="min-w-0 break-words text-sm">
                {RELATION_LABELS[link.relation] ?? link.relation}{" "}
                {scene ? (
                  <Link href={`/proyectos/${projectId}/estructura/${sceneId}`} className="ne-link font-medium">
                    {title}
                  </Link>
                ) : (
                  <span>Escena no disponible</span>
                )}
                {scene?.archived_at || link.archived_at ? (
                  <span className="ne-hint"> · {scene?.archived_at ? "escena archivada" : "vínculo archivado"}</span>
                ) : null}
              </span>
              <CanonBadge state={link.estado} origin={link.origen} />
            </li>
          );
        })}
      </ul>
    </section>
  );
}
