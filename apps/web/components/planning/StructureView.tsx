"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { api, ApiError, type SceneWritingState, type StructureKind, type StructureNode } from "@/lib/api";
import {
  allowedParentKinds,
  buildTree,
  moveSibling,
  planMove,
  planReorder,
  STRUCTURE_FIELDS,
  STRUCTURE_LABELS,
  type PlannedChange,
  type TreeNode,
} from "@/lib/planning";
import { CanonBadge } from "./CanonBadge";
import { ConfirmPanel } from "./ConfirmPanel";
import { ElementEditor, type Item } from "./ElementEditor";
import { StructureMove } from "./StructureMove";
import { useUnsavedChanges } from "./UnsavedChanges";

const KIND_OPTIONS: StructureKind[] = ["acto", "capitulo", "escena"];

const WRITING_LABELS: Record<SceneWritingState, string> = {
  sin_escritura: "Sin escritura",
  sin_texto: "Sin texto",
  con_texto: "Con texto",
};

/** Una operación que cambia el canon de algún nodo: se muestra antes de enviarla y se envía solo con confirmación. */
type PendingChange = {
  id: number;
  canonNodes: StructureNode[];
  confirmLabel: string;
  run: (confirmCanon: boolean) => Promise<string>;
};

/**
 * Árbol de actos, capítulos y escenas. Cada operación se previsualiza con la misma regla que el servidor:
 * si toca elementos canónicos, se pide confirmación explícita antes de enviarla.
 */
export function StructureView({ projectId }: { projectId: number }) {
  const { isDirty } = useUnsavedChanges();
  const [nodes, setNodes] = useState<StructureNode[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [collapsed, setCollapsed] = useState<Set<number>>(() => new Set());
  const [notice, setNotice] = useState<string | null>(null);
  const [operationError, setOperationError] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingChange | null>(null);
  const [busy, setBusy] = useState(false);
  // Renombrado en la propia fila. Los elementos canónicos se renombran en el panel de edición, con su confirmación.
  const [renaming, setRenaming] = useState<{ id: number; value: string } | null>(null);
  const [renameError, setRenameError] = useState<string | null>(null);
  const [kind, setKind] = useState<StructureKind>("capitulo");
  const [parentValue, setParentValue] = useState("root");
  const [title, setTitle] = useState("");
  const [addError, setAddError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const titleRef = useRef<HTMLInputElement>(null);
  const pendingSeq = useRef(0);

  const load = useCallback(async () => {
    setLoadError(null);
    setOperationError(null);
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

  /** Prepara el formulario de añadir para un tipo y un padre, sin enviar nada, y enfoca el título. */
  function prepareAdd(next: StructureKind, parentId: number | null) {
    setKind(next);
    setParentValue(parentId === null ? "root" : String(parentId));
    if (parentId !== null) setCollapsed((current) => withoutId(current, parentId));
    setAddError(null);
    titleRef.current?.focus();
  }

  /** Cambiar de nodo, o moverlo o reordenarlo, reemplaza su formulario: no se descarta texto sin preguntar. */
  function confirmDiscard(ids: number[]): boolean {
    if (selectedId === null || !ids.includes(selectedId) || !isDirty(`estructura:${selectedId}`)) return true;
    return window.confirm("Hay cambios sin guardar en este nodo. ¿Descartarlos y continuar?");
  }

  function select(id: number) {
    if (id === selectedId) return;
    if (!confirmDiscard([selectedId ?? -1])) return;
    setNotice(null);
    setOperationError(null);
    setPending(null);
    setSelectedId(id);
  }

  function toggle(id: number) {
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parent = parentValue === "root" || parentValue === "" ? null : Number(parentValue);
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
      setNotice(`${STRUCTURE_LABELS[kind]} añadid${kind === "escena" ? "a" : "o"}. Su identidad no cambiará aunque lo muevas o reordenes.`);
      setSelectedId(created.id);
      if (parent !== null) setCollapsed((current) => withoutId(current, parent));
      await load();
    } catch (reason) {
      // Se conservan el tipo, el padre y el título para corregirlos.
      setAddError(reason instanceof ApiError ? reason.message : "No se pudo añadir el elemento.");
    } finally {
      setAdding(false);
    }
  }

  /**
   * Ejecuta una operación del servidor. Si cambia canon y no hay confirmación, la muestra y espera.
   * Si el servidor la rechaza, la vista se queda como estaba y el error se explica sin simular éxito.
   */
  async function execute(run: (confirmCanon: boolean) => Promise<string>, canonNodes: StructureNode[], confirmed = false) {
    const hasCanon = canonNodes.length > 0;
    if (hasCanon && !confirmed) {
      pendingSeq.current += 1;
      setPending({ id: pendingSeq.current, canonNodes, confirmLabel: "Confirmar y continuar", run });
      return;
    }
    setBusy(true);
    setNotice(null);
    setOperationError(null);
    try {
      const message = await run(hasCanon);
      setPending(null);
      setNotice(message);
      await load();
    } catch (reason) {
      setPending(null);
      setOperationError(describeFailure(reason));
    } finally {
      setBusy(false);
    }
  }

  function requestReorder(node: StructureNode, direction: -1 | 1) {
    if (!nodes) return;
    const order = moveSibling(nodes, node.id, direction);
    if (!order) return;
    const changes = planReorder(nodes, node.id, direction);
    if (!confirmDiscard(changes.map((change) => change.node.id))) return;
    void execute(
      (confirmCanon) =>
        api.reorderStructure(projectId, node.parent_id, order, confirmCanon).then(() => "Orden actualizado. Los elementos conservan su identidad."),
      canonOf(changes),
    );
  }

  function requestMove(node: StructureNode, parentId: number | null, position: number) {
    if (!nodes) return;
    const changes = planMove(nodes, node.id, parentId, position);
    if (changes === null) {
      setOperationError("Ese lugar no admite la posición indicada. No se ha cambiado nada.");
      return;
    }
    if (changes.length === 0) {
      setNotice("El elemento ya está en ese lugar. No se ha cambiado nada.");
      return;
    }
    if (!confirmDiscard([node.id])) return;
    void execute(
      (confirmCanon) =>
        api
          .moveNode(projectId, node.id, { parent_id: parentId, posicion: position, confirmar_cambio_canon: confirmCanon })
          .then(() => "Movido a su nuevo lugar. Conserva su identidad, su canon y sus vínculos."),
      canonOf(changes),
    );
  }

  async function saveRename(node: StructureNode, value: string) {
    setBusy(true);
    setRenameError(null);
    try {
      await api.updateElement(projectId, "estructura", node.id, { title: value.trim() === "" ? null : value });
      setRenaming(null);
      setNotice("Título guardado.");
      await load();
    } catch (reason) {
      setRenameError(describeFailure(reason));
    } finally {
      setBusy(false);
    }
  }

  function renderNode(entry: TreeNode): ReactNode {
    const { node, children, depth } = entry;
    const name = node.title?.trim() || "Sin título";
    const label = `${STRUCTURE_LABELS[node.kind]}: ${name}`;
    const canUp = !!nodes && moveSibling(nodes, node.id, -1) !== null;
    const canDown = !!nodes && moveSibling(nodes, node.id, 1) !== null;
    const expanded = !collapsed.has(node.id);
    const addChild: StructureKind[] = node.kind === "acto" ? ["capitulo", "escena"] : node.kind === "capitulo" ? ["escena"] : [];
    return (
      <li key={node.id} data-node-id={node.id} data-level={depth + 1} className="flex flex-col">
        <div className="ne-tree__row">
          <div className="ne-tree__identity">
            {children.length > 0 ? (
              <button
                type="button"
                onClick={() => toggle(node.id)}
                aria-expanded={expanded}
                aria-label={`${expanded ? "Contraer" : "Expandir"} ${label}`}
                className="ne-button ne-button--ghost ne-button--small ne-tree__toggle"
              >
                <span aria-hidden="true">{expanded ? "▾" : "▸"}</span>
              </button>
            ) : (
              <span className="ne-tree__toggle-space" aria-hidden="true" />
            )}
            <button
              type="button"
              onClick={() => select(node.id)}
              aria-current={node.id === selectedId ? "true" : undefined}
              className={`ne-tree__name ne-tree__name--${node.kind} ${node.archived_at ? "ne-tree__name--archived" : ""}`}
            >
              {label}
            </button>
            <CanonBadge state={node.estado} origin={node.origen} />
            {node.archived_at ? <span className="ne-badge">Archivado</span> : null}
            {node.kind === "escena" ? (
              <span className={`ne-badge ${node.escritura === "con_texto" ? "ne-badge--ok" : ""}`}>
                {WRITING_LABELS[node.escritura ?? "sin_escritura"]}
              </span>
            ) : null}
          </div>
          <div className="ne-tree__actions">
            <button type="button" disabled={!canUp || busy} onClick={() => requestReorder(node, -1)} aria-label={`Subir ${label}`} className="ne-button ne-button--ghost ne-button--small">
              Subir
            </button>
            <button type="button" disabled={!canDown || busy} onClick={() => requestReorder(node, 1)} aria-label={`Bajar ${label}`} className="ne-button ne-button--ghost ne-button--small">
              Bajar
            </button>
            {addChild.map((child) => (
              <button
                key={child}
                type="button"
                onClick={() => prepareAdd(child, node.id)}
                aria-label={`Añadir ${childLabel(child)} dentro de ${label}`}
                className="ne-button ne-button--ghost ne-button--small"
              >
                Añadir {childLabel(child)}
              </button>
            ))}
            <button
              type="button"
              disabled={busy || node.estado === "canonico"}
              title={node.estado === "canonico" ? "Los elementos canónicos se renombran en el panel de edición, con su confirmación." : undefined}
              onClick={() => {
                setRenameError(null);
                setRenaming({ id: node.id, value: node.title ?? "" });
              }}
              aria-label={`Renombrar ${label}`}
              className="ne-button ne-button--ghost ne-button--small"
            >
              Renombrar
            </button>
            {node.kind === "escena" ? (
              <Link href={`/proyectos/${projectId}/estructura/${node.id}`} aria-label={`Abrir ${label}`} className="ne-button ne-button--small">
                Escribir
              </Link>
            ) : null}
          </div>
        </div>
        {renaming?.id === node.id ? (
          <form
            aria-label={`Renombrar ${label}`}
            onSubmit={(event) => {
              event.preventDefault();
              void saveRename(node, renaming.value);
            }}
            className="ne-tree__rename flex flex-wrap items-end gap-2 pb-2 pl-8"
          >
            <label className="flex flex-col gap-1 text-[0.9375rem]">
              <span className="ne-label">Nuevo título</span>
              <input
                autoFocus
                maxLength={200}
                value={renaming.value}
                onChange={(event) => setRenaming({ id: node.id, value: event.target.value })}
                onKeyDown={(event) => {
                  if (event.key === "Escape") setRenaming(null);
                }}
              />
            </label>
            <button type="submit" disabled={busy} className="ne-button ne-button--small ne-button--primary">
              Guardar título
            </button>
            <button type="button" onClick={() => setRenaming(null)} className="ne-button ne-button--small">
              Cancelar
            </button>
            {renameError ? (
              <p role="alert" className="ne-notice ne-notice--danger w-full">
                {renameError}
              </p>
            ) : null}
          </form>
        ) : null}
        {children.length > 0 && expanded ? <ul className="ne-tree__children">{children.map(renderNode)}</ul> : null}
      </li>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-8 md:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
      <div className="flex min-w-0 flex-col gap-6">
        <form onSubmit={add} aria-label="Añadir a la estructura" className="ne-panel flex flex-col gap-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1 text-sm">
              <label htmlFor="estructura-tipo" className="font-medium">Tipo</label>
              <select id="estructura-tipo" value={kind} onChange={(event) => chooseKind(event.target.value as StructureKind)} >
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
                className="min-w-0"
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
            <input id="estructura-titulo" ref={titleRef} value={title} onChange={(event) => setTitle(event.target.value)} maxLength={200}  />
          </div>
          <div>
            <button type="submit" disabled={adding || (!rootAllowed && parentOptions.length === 0)} className="ne-button ne-button--primary ne-button--small">
              {adding ? "Añadiendo…" : `Añadir ${STRUCTURE_LABELS[kind].toLowerCase()}`}
            </button>
          </div>
          {addError ? (
            <p role="alert" className="ne-notice ne-notice--danger">
              {addError}
            </p>
          ) : null}
        </form>

        {nodes === null && !loadError ? <p className="ne-meta">Cargando estructura…</p> : null}
        {loadError ? (
          <p role="alert" className="ne-notice ne-notice--danger">
            {loadError}
          </p>
        ) : null}
        {nodes?.length === 0 ? (
          <div className="ne-meta flex flex-col gap-3">
            <p>Todavía no hay actos, capítulos ni escenas. Empieza con un acto o, si prefieres, con una escena suelta.</p>
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => prepareAdd("acto", null)} className="ne-button ne-button--small">
                Añadir un acto
              </button>
              <button type="button" onClick={() => prepareAdd("escena", null)} className="ne-button ne-button--small">
                Añadir una escena suelta
              </button>
            </div>
          </div>
        ) : null}
        <ul className="flex flex-col" aria-label="Árbol de la estructura">
          {tree.map(renderNode)}
        </ul>

        {pending ? (
          <ConfirmPanel
            key={pending.id}
            message={canonMessage(pending.canonNodes)}
            confirmLabel={pending.confirmLabel}
            checkboxLabel="Confirmo el cambio en elementos canónicos"
            busy={busy}
            onConfirm={() => void execute(pending.run, pending.canonNodes, true)}
            onCancel={() => setPending(null)}
          />
        ) : null}
        {operationError ? (
          <div role="alert" className="ne-notice ne-notice--danger flex-col items-start">
            <p>{operationError}</p>
            <button type="button" onClick={() => void load()} className="ne-button ne-button--small ne-button--danger">
              Actualizar la estructura
            </button>
          </div>
        ) : null}
        {notice ? (
          <p role="status" className="ne-notice ne-notice--ok">
            {notice}
          </p>
        ) : null}
        <p className="ne-hint">
          Las escenas no tienen texto propio: no se convierten en capítulos del manuscrito ni duplican el editor.
        </p>
      </div>

      <div className="min-w-0">
        {selected ? (
          <div className="flex flex-col gap-8">
            <section aria-labelledby="estructura-mover" className="flex flex-col gap-3">
              <h2 id="estructura-mover" className="ne-subtitle">
                Mover «{selected.title?.trim() || STRUCTURE_LABELS[selected.kind]}»
              </h2>
              {nodes ? (
                <StructureMove
                  key={`${selected.id}-${selected.parent_id}-${selected.position}`}
                  node={selected}
                  nodes={nodes}
                  busy={busy}
                  onMove={(parentId, position) => requestMove(selected, parentId, position)}
                />
              ) : null}
            </section>
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
          </div>
        ) : (
          <p className="ne-empty">Selecciona un acto, capítulo o escena para editarlo o moverlo.</p>
        )}
      </div>
    </div>
  );
}

/** Explica un fallo del servidor sin simular éxito. Las operaciones validan antes de escribir: no cambian nada. */
function describeFailure(reason: unknown): string {
  const text = reason instanceof ApiError ? reason.message.trim() : "No se pudo completar la operación.";
  return /No se ha cambiado nada/.test(text) ? text : `${text} No se ha cambiado nada.`;
}

function childLabel(kind: StructureKind): string {
  return kind === "capitulo" ? "capítulo" : kind === "escena" ? "escena" : "acto";
}

function withoutId(current: Set<number>, id: number): Set<number> {
  if (!current.has(id)) return current;
  const next = new Set(current);
  next.delete(id);
  return next;
}

/** Nodos canónicos que cambian de posición en una operación. */
function canonOf(changes: PlannedChange[]): StructureNode[] {
  return changes.filter((change) => change.node.estado === "canonico").map((change) => change.node);
}

function canonMessage(nodes: StructureNode[]): ReactNode {
  const names = nodes.map((node) => `«${node.title?.trim() || STRUCTURE_LABELS[node.kind]}»`).join(", ");
  const count = nodes.length;
  return (
    <>
      Esta operación cambia la posición de {count} elemento{count === 1 ? "" : "s"} canónico{count === 1 ? "" : "s"}: {names}. El
      canon no cambia, pero el cambio quedará registrado.
    </>
  );
}
