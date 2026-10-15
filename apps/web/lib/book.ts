import type { StructureNode } from "@/lib/api";

/**
 * Índice de la novela a partir de la estructura guardada. Solo deriva: no escribe nada y no crea manuscritos.
 * Un capítulo sin escenas está vacío. Un capítulo está terminado cuando todas sus escenas tienen texto; hasta que el
 * autor pueda marcarlo (E4), «terminado» se deduce de sus escenas. Un acto se deduce de sus capítulos.
 */
export type BookState = "vacio" | "en_desarrollo" | "terminado";

export type BookNode = {
  node: StructureNode;
  children: BookNode[];
  /** Estado derivado para actos y capítulos; ``null`` para escenas, que muestran su escritura. */
  state: BookState | null;
};

const byPosition = (a: StructureNode, b: StructureNode) => a.position - b.position || a.id - b.id;

function stateOfChapter(scenes: StructureNode[]): BookState {
  if (scenes.length === 0) return "vacio";
  return scenes.every((scene) => scene.escritura === "con_texto") ? "terminado" : "en_desarrollo";
}

function stateOfAct(chapters: BookNode[]): BookState {
  if (chapters.every((chapter) => chapter.state === "vacio")) return "vacio";
  if (chapters.every((chapter) => chapter.state === "terminado")) return "terminado";
  return "en_desarrollo";
}

/** Construye el árbol de actos, capítulos y escenas en orden de posición. */
export function buildBook(nodes: StructureNode[]): BookNode[] {
  const byParent = new Map<number | null, StructureNode[]>();
  for (const node of nodes) {
    const siblings = byParent.get(node.parent_id) ?? [];
    siblings.push(node);
    byParent.set(node.parent_id, siblings);
  }

  function build(node: StructureNode): BookNode {
    const children = (byParent.get(node.id) ?? []).sort(byPosition).map(build);
    if (node.kind === "escena") return { node, children: [], state: null };
    if (node.kind === "capitulo") {
      const scenes = children.map((child) => child.node);
      return { node, children, state: stateOfChapter(scenes) };
    }
    return { node, children, state: stateOfAct(children) };
  }

  return (byParent.get(null) ?? []).sort(byPosition).map(build);
}

/** Capítulos en orden de lectura, para navegar entre ellos. */
export function chapterSequence(book: BookNode[]): BookNode[] {
  const chapters: BookNode[] = [];
  for (const root of book) {
    if (root.node.kind === "capitulo") chapters.push(root);
    for (const child of root.children) if (child.node.kind === "capitulo") chapters.push(child);
  }
  return chapters;
}

export const BOOK_STATE_LABELS: Record<BookState, string> = {
  vacio: "Vacío",
  en_desarrollo: "En desarrollo",
  terminado: "Terminado",
};

export const ESCRITURA_LABELS = {
  sin_escritura: "Sin manuscrito",
  sin_texto: "Sin texto",
  con_texto: "Con texto",
} as const;

/** Título visible de un nodo; un nodo sin título se nombra por su tipo, nunca queda en blanco. */
export function nodeLabel(node: StructureNode): string {
  const kind = node.kind === "acto" ? "Acto" : node.kind === "capitulo" ? "Capítulo" : "Escena";
  return node.title?.trim() || `${kind} sin título`;
}
