"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { api, ApiError, type StructureKind, type StructureNode } from "@/lib/api";
import {
  allowedParentKinds,
  buildTree,
  moveSibling,
  STRUCTURE_FIELDS,
  STRUCTURE_LABELS,
  type TreeNode,
} from "@/lib/planning";
import { CanonBadge } from "./CanonBadge";
import { ElementEditor, type Item } from "./ElementEditor";
import { useUnsavedChanges } from "./UnsavedChanges";

const KIND_OPTIONS: StructureKind[] = ["acto", "capitulo", "escena"];

/**
 * Árbol de actos, capítulos y escenas. Reordenar mueve entre hermanos con botones: no hay arrastre
 * entre padres porque la API no permite cambiar el padre de un nodo todavía.
 */
export function StructureView({ projectId }: { projectId: number }) {
  const { isDirty } = useUnsavedChanges();
  const [nodes, setNodes] = useState<StructureNode[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [moveError, setMoveError] = useState<string | null>(null);
  const [kind, setKind] = useState<StructureKind>("capitulo");
  const [parentValue, setParentValue] = useState("root");
  const [title, setTitle] = useState("");
  const [addError, setAddError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      // Se piden también los archivados: la API exige a los hermanos completos al reordenar.
      setNodes(await api.listStructure(projectId, true));
    } catch (reason) {
      setLoadError(reason instanceof ApiError ? reason.message : "No se pudo cargar la estructura.");
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  const tree = useMemo(() => buildTree(nodes ?? []), [nodes]);
  const selected = nodes?.find((node) => node.id === selectedId) ?? null;

  const parentOptions = useMemo(() => {
    const allowed = allowedParentKinds(kind).filter((item): item is StructureKind => item !== null);
    return (nodes ?? []).filter((node) => !node.archived_at && allowed.includes(node.kind));
  }, [nodes, kind]);
  const rootAllowed = allowedParentKinds(kind).includes(null);

  function chooseKind(next: StructureKind) {
    setKind(next);
    setParentValue(allowedParentKinds(next).includes(null) ? "root" : "");
  }

  function select(id: number) {
    if (id === selectedId) return;
    if (selectedId !== null && isDirty(`estructura:${selectedId}`)) {
      if (!window.confirm("Hay cambios sin guardar en este nodo. ¿Descartarlos y abrir otro?")) return;
    }
    setNotice(null);
    setMoveError(null);
    setSelectedId(id);
  }

  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parent = parentValue === "root" ? null : Number(parentValue);
    if (parent === null && !rootAllowed) {
      setAddError(`Un ${STRUCTURE_LABELS[kind].toLowerCase()} debe ir dentro de otro nodo.`);
      return;
    }
    setAdding(true);
    setAddError(null);
    try {
      const created = await api.createStructureNode(projectId, {
        kind,
        parent_id: parent,
        title: title.trim() || undefined,
      });
      setTitle("");
      setNotice(`${STRUCTURE_LABELS[kind]} añadido. Su identidad no cambiará aunque lo reordenes.`);
      setSelectedId(created.id);
      await load();
    } catch (reason) {
      // Se conservan el tipo, el padre y el título para corregirlos.
      setAddError(reason instanceof ApiError ? reason.message : "No se pudo añadir el elemento.");
    } finally {
      setAdding(false);
    }
  }

  async function move(node: StructureNode, direction: -1 | 1) {
    const order = nodes ? moveSibling(nodes, node.id, direction) : null;
    if (!order) return;
    setMoveError(null);
    setNotice(null);
    try {
      await api.reorderStructure(projectId, node.parent_id, order);
      setNotice("Orden actualizado. Los elementos conservan su identidad.");
    } catch (reason) {
      setMoveError(reason instanceof ApiError ? reason.message : "No se pudo reordenar.");
    } finally {
      await load();
    }
  }

  function renderNode(entry: TreeNode): React.ReactNode {
    const { node, children, depth } = entry;
    const label = `${STRUCTURE_LABELS[node.kind]}: ${node.title?.trim() || "Sin título"}`;
    const canUp = !!nodes && moveSibling(nodes, node.id, -1) !== null;
    const canDown = !!nodes && moveSibling(nodes, node.id, 1) !== null;
    return (
      <li key={node.id} data-node-id={node.id} className="flex flex-col">
        <div className="flex flex-wrap items-center gap-2 py-1.5" style={{ paddingLeft: `${depth * 1.25}rem` }}>
          <button
            type="button"
            onClick={() => select(node.id)}
            aria-current={node.id === selectedId ? "true" : undefined}
            className={`text-left ${node.archived_at ? "text-[var(--color-muted)] line-through" : ""} ${node.id === selectedId ? "font-medium underline" : ""}`}
          >
            {label}
          </button>
          <CanonBadge state={node.estado} origin={node.origen} />
          {node.archived_at ? <span className="text-xs text-[var(--color-muted)]">Archivado</span> : null}
          <button type="button" disabled={!canUp} onClick={() => void move(node, -1)} aria-label={`Subir ${label}`} className="rounded border border-[var(--color-muted)] px-2 py-0.5 text-xs disabled:opacity-40">
            Subir
          </button>
          <button type="button" disabled={!canDown} onClick={() => void move(node, 1)} aria-label={`Bajar ${label}`} className="rounded border border-[var(--color-muted)] px-2 py-0.5 text-xs disabled:opacity-40">
            Bajar
          </button>
          {node.kind === "escena" ? (
            <Link href={`/proyectos/${projectId}/estructura/${node.id}`} aria-label={`Abrir ${label}`} className="text-xs underline">
              Abrir escena
            </Link>
          ) : null}
        </div>
        {children.length > 0 ? <ul className="flex flex-col">{children.map(renderNode)}</ul> : null}
      </li>
    );
  }

  return (
    <div className="grid gap-8 md:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
      <div className="flex flex-col gap-6">
        <form onSubmit={add} aria-label="Añadir a la estructura" className="flex flex-col gap-3 rounded border border-[var(--color-muted)]/60 p-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1 text-sm">
              <label htmlFor="estructura-tipo" className="font-medium">Tipo</label>
              <select id="estructura-tipo" value={kind} onChange={(event) => chooseKind(event.target.value as StructureKind)} className="rounded border border-[var(--color-muted)] bg-transparent px-2 py-1.5">
                {KIND_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {STRUCTURE_LABELS[option]}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1 text-sm">
              <label htmlFor="estructura-padre" className="font-medium">Dentro de</label>
              <select
                id="estructura-padre"
                value={parentValue}
                disabled={!rootAllowed && parentOptions.length === 0}
                onChange={(event) => setParentValue(event.target.value)}
                className="rounded border border-[var(--color-muted)] bg-transparent px-2 py-1.5"
              >
                {rootAllowed ? <option value="root">Raíz de la novela</option> : null}
                {!rootAllowed && parentOptions.length === 0 ? <option value="">No hay dónde colocarlo</option> : null}
                {parentOptions.map((node) => (
                  <option key={node.id} value={String(node.id)}>
                    {STRUCTURE_LABELS[node.kind]}: {node.title?.trim() || "Sin título"}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex flex-col gap-1 text-sm">
            <label htmlFor="estructura-titulo" className="font-medium">Título (opcional)</label>
            <input id="estructura-titulo" value={title} onChange={(event) => setTitle(event.target.value)} maxLength={200} className="rounded border border-[var(--color-muted)] bg-transparent px-2 py-1.5" />
          </div>
          <div>
            <button type="submit" disabled={adding || (!rootAllowed && parentOptions.length === 0)} className="rounded bg-[var(--color-ink)] px-3 py-2 text-sm text-[var(--color-paper)] disabled:opacity-50">
              {adding ? "Añadiendo…" : `Añadir ${STRUCTURE_LABELS[kind].toLowerCase()}`}
            </button>
          </div>
          {addError ? (
            <p role="alert" className="text-sm text-red-700">
              {addError}
            </p>
          ) : null}
        </form>

        {nodes === null && !loadError ? <p className="text-[var(--color-muted)]">Cargando estructura…</p> : null}
        {loadError ? (
          <p role="alert" className="text-red-700">
            {loadError}
          </p>
        ) : null}
        {nodes?.length === 0 ? (
          <p className="text-[var(--color-muted)]">
            Todavía no hay actos, capítulos ni escenas. Puedes empezar con un acto o directamente con una escena.
          </p>
        ) : null}
        <ul className="flex flex-col" aria-label="Árbol de la estructura">
          {tree.map(renderNode)}
        </ul>
        {moveError ? (
          <p role="alert" className="text-sm text-red-700">
            {moveError}
          </p>
        ) : null}
        {notice ? (
          <p role="status" className="text-sm text-green-800">
            {notice}
          </p>
        ) : null}
        <p className="text-xs text-[var(--color-muted)]">
          Las escenas no tienen texto propio: no se convierten en capítulos del manuscrito ni duplican el editor.
        </p>
      </div>

      <div className="min-w-0">
        {selected ? (
          <ElementEditor
            key={selected.id}
            projectId={projectId}
            route="estructura"
            item={selected as Item}
            fields={STRUCTURE_FIELDS}
            itemLabel={`${STRUCTURE_LABELS[selected.kind]}: ${selected.title?.trim() || "Sin título"}`}
            onChanged={(message, changed) => {
              setNotice(message);
              if (changed === "archived") setSelectedId(null);
              void load();
            }}
          />
        ) : (
          <p className="text-[var(--color-muted)]">Selecciona un acto, capítulo o escena para editarlo.</p>
        )}
      </div>
    </div>
  );
}
