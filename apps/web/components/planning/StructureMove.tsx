"use client";

import { useMemo, useState, type FormEvent } from "react";
import type { StructureNode } from "@/lib/api";
import { moveTargets, STRUCTURE_LABELS } from "@/lib/planning";

type Props = {
  node: StructureNode;
  nodes: StructureNode[];
  busy: boolean;
  /** ``parentId`` null = raíz de la novela. ``position`` = índice entre los hermanos del destino. */
  onMove: (parentId: number | null, position: number) => void;
};

/**
 * Movimiento accesible: se elige un padre compatible y una posición con selectores, y se confirma con un botón.
 * No depende de arrastrar. Solo ofrece destinos que la API aceptará.
 */
export function StructureMove({ node, nodes, busy, onMove }: Props) {
  const targets = useMemo(() => moveTargets(nodes, node), [nodes, node]);
  const currentParent = node.parent_id === null ? "root" : String(node.parent_id);
  const [parentValue, setParentValue] = useState(currentParent);

  if (node.archived_at) {
    return <p className="text-sm text-[var(--color-muted)]">Un elemento archivado no se puede mover.</p>;
  }
  if (!targets.root && targets.parents.length === 0) {
    return <p className="text-sm text-[var(--color-muted)]">No hay ningún lugar compatible al que mover este elemento.</p>;
  }

  const parentId = parentValue === "root" ? null : Number(parentValue);
  // Igual que la API: cuentan todos los hermanos del destino, archivados incluidos, sin contar el propio nodo.
  const siblingCount = nodes.filter((item) => item.parent_id === parentId && item.id !== node.id).length;
  // Ya está en ese lugar si ya es el último de sus hermanos.
  const unchanged = parentId === node.parent_id && node.position === siblingCount;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (parentId !== null && !targets.parents.some((item) => item.id === parentId)) return;
    onMove(parentId, siblingCount);
  }

  return (
    <form onSubmit={submit} aria-label="Mover a otro lugar de la estructura" className="flex flex-col gap-3 rounded border border-[var(--color-muted)]/60 p-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="flex flex-col gap-1 text-sm">
          <label htmlFor="mover-destino" className="font-medium">Nuevo lugar</label>
          <select
            id="mover-destino"
            value={parentValue}
            onChange={(event) => setParentValue(event.target.value)}
            disabled={busy}
            className="min-w-0 rounded border border-[var(--color-muted)] bg-transparent px-2 py-1.5"
          >
            {targets.root ? <option value="root">Raíz de la novela</option> : null}
            {targets.parents.map((item) => (
              <option key={item.id} value={String(item.id)}>
                {STRUCTURE_LABELS[item.kind]}: {item.title?.trim() || "Sin título"}
              </option>
            ))}
          </select>
        </div>
        <p className="self-end text-xs text-[var(--color-muted)]">
          Se coloca al final de los elementos que ya hay en el nuevo lugar. Para cambiar su orden dentro de él, usa Subir y Bajar.
        </p>
      </div>
      <div>
        <button
          type="submit"
          disabled={busy || unchanged}
          className="rounded bg-[var(--color-ink)] px-3 py-2 text-sm text-[var(--color-paper)] disabled:opacity-50"
        >
          {busy ? "Moviendo…" : "Mover aquí"}
        </button>
        {unchanged ? <span className="ml-3 text-xs text-[var(--color-muted)]">Ya está en ese lugar.</span> : null}
      </div>
    </form>
  );
}
