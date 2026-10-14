/**
 * Lógica de la planificación narrativa sin React: campos de cada tipo, etiquetas de canon,
 * árbol de la estructura y cálculo de reordenación. Todo se deriva de la respuesta de la API.
 */

import type { CanonState, ElementRoute, PlotKind, StructureKind, StructureNode } from "@/lib/api";

export type FieldDef = {
  name: string;
  label: string;
  multiline?: boolean;
  type?: "text" | "number";
  options?: { value: string; label: string }[];
  hint?: string;
};

export type CollectionConfig = {
  route: ElementRoute;
  singular: string;
  plural: string;
  /** Campo que actúa de nombre visible y es el único obligatorio para crear. */
  titleField: string;
  titleLabel: string;
  /** Campos del formulario de edición, en orden. */
  fields: FieldDef[];
  emptyText: string;
};

export const PLOT_KIND_LABELS: Record<PlotKind, string> = {
  acontecimiento: "Acontecimiento",
  conflicto: "Conflicto",
  subtrama: "Subtrama",
  misterio: "Misterio",
  pregunta_abierta: "Pregunta abierta",
};

const PLOT_OPTIONS = Object.entries(PLOT_KIND_LABELS).map(([value, label]) => ({ value, label }));

export const COLLECTIONS: Record<"personajes" | "lugares" | "trama" | "cronologia", CollectionConfig> = {
  personajes: {
    route: "personajes",
    singular: "personaje",
    plural: "personajes",
    titleField: "name",
    titleLabel: "Nombre",
    emptyText: "Todavía no hay personajes. Basta con un nombre para empezar.",
    fields: [
      { name: "name", label: "Nombre" },
      { name: "description", label: "Descripción", multiline: true },
      { name: "goals", label: "Objetivos", multiline: true },
      { name: "motivations", label: "Motivaciones", multiline: true },
      { name: "conflicts", label: "Conflictos", multiline: true },
      { name: "evolution", label: "Evolución", multiline: true },
      { name: "notes", label: "Notas libres", multiline: true },
    ],
  },
  lugares: {
    route: "lugares",
    singular: "lugar",
    plural: "lugares",
    titleField: "name",
    titleLabel: "Nombre",
    emptyText: "Todavía no hay lugares. Basta con un nombre para empezar.",
    fields: [
      { name: "name", label: "Nombre" },
      { name: "description", label: "Descripción", multiline: true },
      { name: "features", label: "Características", multiline: true },
      { name: "notes", label: "Notas libres", multiline: true },
    ],
  },
  trama: {
    route: "elementos-trama",
    singular: "elemento de trama",
    plural: "trama y misterios",
    titleField: "title",
    titleLabel: "Título",
    emptyText: "Todavía no hay elementos de trama. Un título basta para empezar.",
    fields: [
      { name: "kind", label: "Tipo", options: PLOT_OPTIONS },
      { name: "title", label: "Título" },
      { name: "description", label: "Descripción", multiline: true },
      { name: "notes", label: "Notas libres", multiline: true },
    ],
  },
  cronologia: {
    route: "acontecimientos",
    singular: "acontecimiento",
    plural: "cronología",
    titleField: "title",
    titleLabel: "Título",
    emptyText: "Todavía no hay acontecimientos en la cronología.",
    fields: [
      { name: "title", label: "Título" },
      {
        name: "narrative_order",
        label: "Orden en el relato",
        type: "number",
        hint: "Posición en el relato. Puedes dejarlo vacío.",
      },
      { name: "story_time", label: "Momento en la historia", hint: "Texto libre, por ejemplo «tres años antes»." },
      { name: "description", label: "Descripción", multiline: true },
      { name: "notes", label: "Notas libres", multiline: true },
    ],
  },
};

/** Campos editables de una escena o de un acto o capítulo. */
export const STRUCTURE_FIELDS: FieldDef[] = [
  { name: "title", label: "Título" },
  { name: "summary", label: "Resumen o planificación", multiline: true, hint: "Lo que ocurre o debe ocurrir. Puedes dejarlo vacío." },
  { name: "notes", label: "Notas libres", multiline: true },
];

export const CANON_LABELS: Record<CanonState, string> = {
  provisional: "Provisional",
  propuesta_ia: "Propuesta de IA",
  canonico: "Canónico",
};

export const CANON_HELP: Record<CanonState, string> = {
  provisional: "Material del autor. Puede cambiar libremente.",
  propuesta_ia: "Sugerencia que no forma parte de los hechos de la novela hasta que la apruebes.",
  canonico: "Aprobado por el autor. Cambiarlo exige confirmación y queda registrado en una decisión.",
};

export const STRUCTURE_LABELS: Record<StructureKind, string> = {
  acto: "Acto",
  capitulo: "Capítulo",
  escena: "Escena",
};

/** Qué tipos puede contener cada tipo de nodo. Refleja las reglas del servicio. */
export const ALLOWED_CHILDREN: Record<StructureKind, StructureKind[]> = {
  acto: ["capitulo", "escena"],
  capitulo: ["escena"],
  escena: [],
};

/** Tipos que pueden colgar de la raíz o de un padre concreto. Refleja PARENT_KINDS del backend. */
export function allowedParentKinds(kind: StructureKind): (StructureKind | null)[] {
  if (kind === "acto") return [null];
  if (kind === "capitulo") return [null, "acto"];
  return [null, "acto", "capitulo"];
}

export type TreeNode = { node: StructureNode; children: TreeNode[]; depth: number };

/** Árbol a partir de la lista plana. Los hermanos se ordenan por posición y, a igualdad, por id. */
export function buildTree(nodes: StructureNode[]): TreeNode[] {
  const byParent = new Map<number | null, StructureNode[]>();
  for (const node of nodes) {
    const list = byParent.get(node.parent_id) ?? [];
    list.push(node);
    byParent.set(node.parent_id, list);
  }
  const build = (parentId: number | null, depth: number): TreeNode[] =>
    siblingsOf(byParent, parentId).map((node) => ({ node, children: build(node.id, depth + 1), depth }));
  return build(null, 0);
}

function siblingsOf(byParent: Map<number | null, StructureNode[]>, parentId: number | null): StructureNode[] {
  return [...(byParent.get(parentId) ?? [])].sort((a, b) => a.position - b.position || a.id - b.id);
}

/**
 * Nuevo orden de los hermanos al mover uno arriba o abajo. Devuelve null si no es posible.
 * Incluye a todos los hermanos (archivados también), porque la API lo exige.
 */
export function moveSibling(nodes: StructureNode[], nodeId: number, direction: -1 | 1): number[] | null {
  const target = nodes.find((node) => node.id === nodeId);
  if (!target) return null;
  const siblings = nodes
    .filter((node) => node.parent_id === target.parent_id)
    .sort((a, b) => a.position - b.position || a.id - b.id)
    .map((node) => node.id);
  const index = siblings.indexOf(nodeId);
  const swap = index + direction;
  if (swap < 0 || swap >= siblings.length) return null;
  const order = [...siblings];
  [order[index], order[swap]] = [order[swap], order[index]];
  return order;
}

/** Relaciones permitidas hacia una escena, según el tipo del elemento. Refleja RELATIONS del backend. */
export const SCENE_RELATIONS: Record<string, { relation: string; label: string; route: ElementRoute }> = {
  personaje: { relation: "participa_en", label: "participa en", route: "personajes" },
  lugar: { relation: "ocurre_en", label: "ocurre en", route: "lugares" },
  elemento_trama: { relation: "aparece_en", label: "aparece en", route: "elementos-trama" },
};

export const RELATION_LABELS: Record<string, string> = {
  participa_en: "participa en",
  ocurre_en: "ocurre en",
  aparece_en: "aparece en",
};

/** Nombre visible de un elemento: su campo de título, o un texto neutro si no tiene ninguno todavía. */
export function labelOf(item: { id: number } & Record<string, unknown>, titleField: string): string {
  const value = item[titleField];
  return typeof value === "string" && value.trim() !== "" ? value : `Sin nombre (${item.id})`;
}

/** Texto para formularios: vacío significa «no informado», que la API guarda como nulo. */
export function toNullable(value: string): string | null {
  return value.trim() === "" ? null : value;
}
