"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  api,
  ApiError,
  type Character,
  type NarrativeLink,
  type PlotElement,
  type Place,
  type StructureNode,
} from "@/lib/api";
import { COLLECTION_PATH, labelOf, RELATION_LABELS, SCENE_RELATIONS, STRUCTURE_FIELDS, STRUCTURE_LABELS } from "@/lib/planning";
import { CanonBadge } from "./CanonBadge";
import { ConfirmPanel } from "./ConfirmPanel";
import { ElementEditor, type Item } from "./ElementEditor";
import { SceneWriting } from "./SceneWriting";

type Endpoint = { kind: string; id: number; name: string; archived: boolean };

/**
 * Escena: identidad estable por id (la URL no cambia al reordenar), planificación y vínculos.
 * Los vínculos solo se crean y se archivan con las operaciones validadas de la API.
 */
export function SceneDetail({ projectId, nodeId }: { projectId: number; nodeId: number }) {
  const [node, setNode] = useState<StructureNode | null>(null);
  const [missing, setMissing] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [links, setLinks] = useState<NarrativeLink[] | null>(null);
  const [elements, setElements] = useState<Endpoint[]>([]);
  const [kind, setKind] = useState("personaje");
  const [elementId, setElementId] = useState("");
  const [linkError, setLinkError] = useState<string | null>(null);
  const [linking, setLinking] = useState(false);
  const [removing, setRemoving] = useState<number | null>(null);
  const [removeBusy, setRemoveBusy] = useState(false);
  const [removeError, setRemoveError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      // Primero se comprueba que la escena existe en ESTA novela: una escena de otra no se muestra.
      const structure = await api.listStructure(projectId, true);
      const found = structure.find((item) => item.id === nodeId && item.kind === "escena") ?? null;
      setNode(found);
      setMissing(found === null);
      if (found === null) {
        setLinks([]);
        return;
      }
      const [nodeLinks, characters, places, plots] = await Promise.all([
        api.listNodeLinks(projectId, nodeId, false),
        api.listElements<Character>(projectId, "personajes", true),
        api.listElements<Place>(projectId, "lugares", true),
        api.listElements<PlotElement>(projectId, "elementos-trama", true),
      ]);
      setLinks(nodeLinks);
      setElements([
        ...characters.map((item) => ({ kind: "personaje", id: item.id, name: labelOf(item, "name"), archived: !!item.archived_at })),
        ...places.map((item) => ({ kind: "lugar", id: item.id, name: labelOf(item, "name"), archived: !!item.archived_at })),
        ...plots.map((item) => ({ kind: "elemento_trama", id: item.id, name: labelOf(item, "title"), archived: !!item.archived_at })),
      ]);
    } catch (reason) {
      setLoadError(reason instanceof ApiError ? reason.message : "No se pudo cargar la escena.");
    }
  }, [projectId, nodeId]);

  useEffect(() => {
    void load();
  }, [load]);

  const byKey = useMemo(() => new Map(elements.map((item) => [`${item.kind}:${item.id}`, item])), [elements]);
  const linkedKeys = useMemo(
    () => new Set((links ?? []).map((link) => `${link.source_kind}:${link.source_id}`)),
    [links],
  );
  const candidates = elements.filter((item) => item.kind === kind && !item.archived && !linkedKeys.has(`${item.kind}:${item.id}`));

  async function link(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const id = Number(elementId);
    if (!elementId || !SCENE_RELATIONS[kind]) return;
    setLinking(true);
    setLinkError(null);
    setNotice(null);
    try {
      await api.createLink(projectId, {
        origen: { tipo: kind, id },
        destino: { tipo: "escena", id: nodeId },
        relacion: SCENE_RELATIONS[kind].relation,
      });
      setElementId("");
      setNotice("Vínculo creado.");
      setLinks(await api.listNodeLinks(projectId, nodeId, false));
    } catch (reason) {
      // La selección se conserva para corregir el problema.
      setLinkError(reason instanceof ApiError ? reason.message : "No se pudo crear el vínculo.");
    } finally {
      setLinking(false);
    }
  }

  async function unlink(item: NarrativeLink) {
    setRemoveBusy(true);
    setRemoveError(null);
    try {
      await api.archiveLink(projectId, item.id, item.estado === "canonico");
      setRemoving(null);
      setNotice("Vínculo retirado. No se ha borrado: queda archivado.");
      setLinks(await api.listNodeLinks(projectId, nodeId, false));
    } catch (reason) {
      setRemoveError(reason instanceof ApiError ? reason.message : "No se pudo retirar el vínculo.");
    } finally {
      setRemoveBusy(false);
    }
  }

  if (loadError) {
    return (
      <p role="alert" className="text-red-700">
        {loadError}
      </p>
    );
  }
  if (links === null) return <p className="text-[var(--color-muted)]">Cargando escena…</p>;
  if (missing || node === null) {
    return (
      <div className="flex flex-col gap-3">
        <p>Esta escena no existe en esta novela.</p>
        <Link href={`/proyectos/${projectId}/estructura`} className="underline">
          Volver a la estructura
        </Link>
      </div>
    );
  }

  const sceneTitle = node.title?.trim() || "Escena sin título";

  return (
    <div className="flex flex-col gap-10">
      <div className="flex flex-col gap-3">
        <Link href={`/proyectos/${projectId}/estructura`} className="text-sm underline">
          Volver a la estructura
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-sm uppercase tracking-widest text-[var(--color-muted)]">{STRUCTURE_LABELS[node.kind]}</p>
          <CanonBadge state={node.estado} origin={node.origen} />
        </div>
        <p className="text-sm text-[var(--color-muted)]">
          Una escena no es un capítulo del manuscrito y no tiene texto propio: aquí se planifica lo que ocurre en ella.
        </p>
      </div>

      <section aria-labelledby="escena-escritura" className="flex flex-col gap-4">
        <h2 id="escena-escritura" className="text-xl font-medium">
          Escritura
        </h2>
        <SceneWriting projectId={projectId} nodeId={node.id} sceneTitle={sceneTitle} />
      </section>

      <section aria-labelledby="escena-datos" className="flex flex-col gap-4">
        <h2 id="escena-datos" className="text-xl font-medium">
          Planificación de «{sceneTitle}»
        </h2>
        <ElementEditor
          key={node.id}
          projectId={projectId}
          route="estructura"
          item={node as Item}
          fields={STRUCTURE_FIELDS}
          itemLabel={sceneTitle}
          onChanged={(message) => {
            setNotice(message);
            void load();
          }}
        />
      </section>

      <section aria-labelledby="vinculos" className="flex flex-col gap-4">
        <h2 id="vinculos" className="text-xl font-medium">
          Personajes, lugares y trama en esta escena
        </h2>
        {links.length === 0 ? (
          <p className="text-[var(--color-muted)]">Todavía no hay nada vinculado a esta escena.</p>
        ) : null}
        <ul className="flex flex-col divide-y divide-[var(--color-muted)]/40">
          {links.map((item) => {
            const other = byKey.get(`${item.source_kind}:${item.source_id}`);
            const name = other?.name ?? `Elemento ${item.source_id}`;
            const relation = RELATION_LABELS[item.relation] ?? item.relation;
            const open = removing === item.id;
            const route = SCENE_RELATIONS[item.source_kind]?.route;
            return (
              <li key={item.id} className="flex flex-col gap-2 py-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="min-w-0 break-words">
                    {route ? (
                      <Link href={`/proyectos/${projectId}/${COLLECTION_PATH[route]}?seleccionado=${item.source_id}`} className="font-medium underline">
                        {name}
                      </Link>
                    ) : (
                      <span className="font-medium">{name}</span>
                    )}{" "}
                    {relation} esta escena
                    {other?.archived ? <span className="text-xs text-[var(--color-muted)]"> · archivado</span> : null}
                  </span>
                  <span className="flex items-center gap-2">
                    <CanonBadge state={item.estado} origin={item.origen} />
                    <button
                      type="button"
                      onClick={() => setRemoving(open ? null : item.id)}
                      aria-expanded={open}
                      aria-label={`Quitar ${name} de esta escena`}
                      className="rounded border border-[var(--color-muted)] px-2 py-0.5 text-xs"
                    >
                      Quitar
                    </button>
                  </span>
                </div>
                {open ? (
                  <ConfirmPanel
                    message={
                      <>
                        Quitar a <strong>{name}</strong> de esta escena. El vínculo se archiva y no se borra.
                        {item.estado === "canonico" ? " Es un vínculo canónico: el cambio quedará registrado." : ""}
                      </>
                    }
                    confirmLabel="Quitar vínculo"
                    checkboxLabel={item.estado === "canonico" ? "Confirmo el cambio de un vínculo canónico" : undefined}
                    busy={removeBusy}
                    onConfirm={() => void unlink(item)}
                    onCancel={() => setRemoving(null)}
                  />
                ) : null}
              </li>
            );
          })}
        </ul>
        {removeError ? (
          <p role="alert" className="text-sm text-red-700">
            {removeError}
          </p>
        ) : null}

        <form onSubmit={link} aria-label="Vincular un elemento a la escena" className="flex flex-col gap-3 rounded border border-[var(--color-muted)]/60 p-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1 text-sm">
              <label htmlFor="escena-tipo" className="font-medium">Tipo de elemento</label>
              <select
                id="escena-tipo"
                value={kind}
                onChange={(event) => {
                  setKind(event.target.value);
                  setElementId("");
                }}
                className="rounded border border-[var(--color-muted)] bg-transparent px-2 py-1.5"
              >
                <option value="personaje">Personaje</option>
                <option value="lugar">Lugar</option>
                <option value="elemento_trama">Elemento de trama</option>
              </select>
            </div>
            <div className="flex flex-col gap-1 text-sm">
              <label htmlFor="escena-elemento" className="font-medium">Elemento</label>
              <select
                id="escena-elemento"
                value={elementId}
                onChange={(event) => setElementId(event.target.value)}
                disabled={candidates.length === 0}
                className="rounded border border-[var(--color-muted)] bg-transparent px-2 py-1.5"
              >
                <option value="">{candidates.length === 0 ? "No hay elementos disponibles" : "Elige uno"}</option>
                {candidates.map((item) => (
                  <option key={`${item.kind}-${item.id}`} value={String(item.id)}>
                    {item.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <p className="text-xs text-[var(--color-muted)]">
            La relación se establece por el tipo: {SCENE_RELATIONS[kind] ? RELATION_LABELS[SCENE_RELATIONS[kind].relation] : ""}.
          </p>
          <div>
            <button type="submit" disabled={linking || !elementId} className="rounded bg-[var(--color-ink)] px-3 py-2 text-sm text-[var(--color-paper)] disabled:opacity-50">
              {linking ? "Vinculando…" : "Vincular a la escena"}
            </button>
          </div>
          {linkError ? (
            <p role="alert" className="text-sm text-red-700">
              {linkError}
            </p>
          ) : null}
        </form>
        {notice ? (
          <p role="status" className="text-sm text-green-800">
            {notice}
          </p>
        ) : null}
      </section>
    </div>
  );
}
