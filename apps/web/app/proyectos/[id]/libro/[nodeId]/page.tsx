"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { EditorCapituloVacio } from "@/components/libro/EditorCapituloVacio";
import { EstadoCapitulo } from "@/components/libro/EstadoCapitulo";
import { api, ApiError, type StructureNode } from "@/lib/api";
import { buildBook, chapterSequence, ESCRITURA_LABELS, nodeLabel, type BookNode } from "@/lib/book";
import { STRUCTURE_LABELS } from "@/lib/planning";

/** Vista de un acto o de un capítulo. Un capítulo sin escenas muestra su editor, sin crear nada hasta escribir. */
export default function LibroNodoPage() {
  const router = useRouter();
  const params = useParams<{ id: string; nodeId: string }>();
  const projectId = Number(params.id);
  const nodeId = Number(params.nodeId);
  const [nodes, setNodes] = useState<StructureNode[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api.listStructure(projectId, false).then(setNodes, (reason: unknown) =>
      setError(reason instanceof ApiError ? reason.message : "No se pudo cargar el capítulo."),
    );
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  const book = nodes ? buildBook(nodes) : null;
  const found = book ? findNode(book, nodeId) : null;

  // Una escena tiene su propia página: el índice la lleva allí directamente.
  useEffect(() => {
    if (found?.node.kind === "escena") router.replace(`/proyectos/${projectId}/estructura/${nodeId}`);
  }, [found, nodeId, projectId, router]);

  if (error) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-10">
        <p role="alert" className="ne-notice ne-notice--danger">
          {error}
        </p>
      </main>
    );
  }
  if (book === null) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-10">
        <p className="ne-meta">Cargando…</p>
      </main>
    );
  }
  if (found === null) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-10">
        <p role="alert" className="ne-notice ne-notice--danger">
          Este elemento no existe en esta novela.
        </p>
        <Link href={`/proyectos/${projectId}/libro`} className="ne-link">
          Volver al índice
        </Link>
      </main>
    );
  }
  if (found.node.kind === "escena") return null;

  const { node, children, state } = found;
  const parent = findParent(book, nodeId);
  const chapters = chapterSequence(book);
  const index = chapters.findIndex((chapter) => chapter.node.id === nodeId);
  const previous = index > 0 ? chapters[index - 1] : null;
  const next = index >= 0 && index < chapters.length - 1 ? chapters[index + 1] : null;

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-10 sm:px-6">
      <nav aria-label="Ubicación" className="ne-meta flex flex-wrap gap-x-2">
        <Link href={`/proyectos/${projectId}/libro`} className="ne-link">
          Índice
        </Link>
        {parent ? (
          <>
            <span aria-hidden="true">/</span>
            <Link href={`/proyectos/${projectId}/libro/${parent.node.id}`} className="ne-link">
              {nodeLabel(parent.node)}
            </Link>
          </>
        ) : null}
      </nav>

      <header className="flex flex-col gap-2">
        <p className="ne-kicker">{STRUCTURE_LABELS[node.kind]}</p>
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h1 className="ne-page-title">{nodeLabel(node)}</h1>
          {state ? <EstadoCapitulo state={state} /> : null}
        </div>
      </header>

      {node.kind === "capitulo" && children.length === 0 ? (
        <EditorCapituloVacio projectId={projectId} chapterId={nodeId} onDone={load} />
      ) : null}

      {children.length > 0 ? (
        <section aria-labelledby="contenido-titulo" className="flex flex-col gap-3">
          <h2 id="contenido-titulo" className="ne-section-title">
            {node.kind === "acto" ? "Capítulos" : "Escenas"}
          </h2>
          <ol className="flex flex-col divide-y divide-[var(--color-line)]">
            {children.map((child) => (
              <li key={child.node.id} className="flex flex-wrap items-baseline justify-between gap-2 py-3">
                <Link
                  href={
                    child.node.kind === "escena"
                      ? `/proyectos/${projectId}/estructura/${child.node.id}`
                      : `/proyectos/${projectId}/libro/${child.node.id}`
                  }
                  className="ne-link font-medium"
                >
                  {nodeLabel(child.node)}
                </Link>
                {child.node.kind === "escena" ? (
                  <span className="ne-meta">{ESCRITURA_LABELS[child.node.escritura ?? "sin_escritura"]}</span>
                ) : child.state ? (
                  <EstadoCapitulo state={child.state} />
                ) : null}
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      {node.kind === "capitulo" ? (
        <nav aria-label="Navegar entre capítulos" className="flex flex-wrap justify-between gap-3 border-t border-[var(--color-line)] pt-4">
          {previous ? (
            <Link href={`/proyectos/${projectId}/libro/${previous.node.id}`} className="ne-link">
              ← {nodeLabel(previous.node)}
            </Link>
          ) : (
            <span />
          )}
          {next ? (
            <Link href={`/proyectos/${projectId}/libro/${next.node.id}`} className="ne-link">
              {nodeLabel(next.node)} →
            </Link>
          ) : null}
        </nav>
      ) : null}
    </main>
  );
}

function findNode(items: BookNode[], id: number): BookNode | null {
  for (const item of items) {
    if (item.node.id === id) return item;
    const inner = findNode(item.children, id);
    if (inner) return inner;
  }
  return null;
}

function findParent(items: BookNode[], id: number, parent: BookNode | null = null): BookNode | null {
  for (const item of items) {
    if (item.node.id === id) return parent;
    const inner = findParent(item.children, id, item);
    if (inner !== undefined && inner !== null) return inner;
  }
  return null;
}
