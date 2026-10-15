import { expect, test } from "@playwright/test";
import type { StructureNode } from "../../lib/api";
import { buildBook, chapterSequence } from "../../lib/book";

function node(id: number, kind: StructureNode["kind"], parent: number | null, position: number, escritura?: StructureNode["escritura"]): StructureNode {
  return {
    id,
    project_id: 1,
    estado: "provisional",
    origen: "autor",
    approved_decision_id: null,
    created_at: "2026-01-01T00:00:00",
    updated_at: "2026-01-01T00:00:00",
    archived_at: null,
    parent_id: parent,
    kind,
    position,
    title: `${kind} ${id}`,
    summary: null,
    notes: null,
    escritura,
  };
}

test("un acto y un capítulo sin escenas aparecen como vacíos y no generan nada", () => {
  const book = buildBook([node(1, "acto", null, 0), node(2, "capitulo", 1, 0)]);
  expect(book[0].state).toBe("vacio");
  expect(book[0].children[0].state).toBe("vacio");
  expect(book[0].children[0].children).toEqual([]);
});

test("un capítulo está en desarrollo con alguna escena sin texto y terminado cuando todas tienen texto", () => {
  const mixto = buildBook([
    node(1, "capitulo", null, 0),
    node(2, "escena", 1, 0, "con_texto"),
    node(3, "escena", 1, 1, "sin_escritura"),
  ]);
  expect(mixto[0].state).toBe("en_desarrollo");

  const completo = buildBook([
    node(1, "capitulo", null, 0),
    node(2, "escena", 1, 0, "con_texto"),
    node(3, "escena", 1, 1, "con_texto"),
  ]);
  expect(completo[0].state).toBe("terminado");
});

test("las escenas se ordenan por posición y el orden de capítulos es de lectura", () => {
  const book = buildBook([
    node(1, "acto", null, 0),
    node(2, "capitulo", 1, 1),
    node(3, "capitulo", 1, 0),
    node(4, "escena", 3, 1),
    node(5, "escena", 3, 0),
  ]);
  expect(book[0].children.map((c) => c.node.id)).toEqual([3, 2]);
  expect(book[0].children[0].children.map((c) => c.node.id)).toEqual([5, 4]);
  expect(chapterSequence(book).map((c) => c.node.id)).toEqual([3, 2]);
});
