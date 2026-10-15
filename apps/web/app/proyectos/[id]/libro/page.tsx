"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { EstadoCapitulo } from "@/components/libro/EstadoCapitulo";
import { api, ApiError, type ProjectDetail, type StructureNode } from "@/lib/api";
import { buildBook, ESCRITURA_LABELS, nodeLabel, type BookNode } from "@/lib/book";

/** Índice de la novela: actos, capítulos y escenas en orden. Cada elemento lleva a su sección. */
export default function LibroPage() {
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [nodes, setNodes] = useState<StructureNode[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([api.getProject(projectId), api.listStructure(projectId, false)]).then(
      ([detail, structure]) => {
        if (!active) return;
        setProject(detail);
        setNodes(structure);
      },
      (reason: unknown) => {
        if (active) setError(reason instanceof ApiError ? reason.message : "No se pudo cargar el índice.");
      },
    );
    return () => {
      active = false;
    };
  }, [projectId]);

  const book = nodes ? buildBook(nodes) : null;

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-10 sm:px-6">
      <header className="flex flex-col gap-2">
        <p className="ne-kicker">Manuscrito</p>
        <h1 className="ne-page-title">{project?.name ?? "Cargando…"}</h1>
        <p className="ne-lede">Índice de la novela. Cada acto, capítulo y escena lleva a su sección.</p>
      </header>

      {error ? (
        <p role="alert" className="ne-notice ne-notice--danger">
          {error}
        </p>
      ) : null}
      {book === null && !error ? <p className="ne-meta">Cargando…</p> : null}
      {book !== null && book.length === 0 ? (
        <div className="ne-empty">
          <p>Todavía no hay actos, capítulos ni escenas.</p>
          <Link href={`/proyectos/${projectId}/estructura`} className="ne-link">
            Crear la estructura
          </Link>
        </div>
      ) : null}
      {book !== null && book.length > 0 ? (
        <nav aria-label="Índice de la novela">
          <ol className="flex flex-col gap-6">
            {book.map((item) => (
              <Entrada key={item.node.id} item={item} projectId={projectId} />
            ))}
          </ol>
        </nav>
      ) : null}
    </main>
  );
}

function Entrada({ item, projectId }: { item: BookNode; projectId: number }) {
  const { node } = item;
  if (node.kind === "escena") {
    return (
      <li className="flex flex-wrap items-baseline justify-between gap-2">
        <Link href={`/proyectos/${projectId}/estructura/${node.id}`} className="ne-link">
          {nodeLabel(node)}
        </Link>
        <span className="ne-meta">{ESCRITURA_LABELS[node.escritura ?? "sin_escritura"]}</span>
      </li>
    );
  }
  return (
    <li className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <Link href={`/proyectos/${projectId}/libro/${node.id}`} className={node.kind === "acto" ? "ne-subtitle ne-link" : "ne-link font-medium"}>
          {nodeLabel(node)}
        </Link>
        {item.state ? <EstadoCapitulo state={item.state} /> : null}
      </div>
      {item.children.length > 0 ? (
        <ol className="flex flex-col gap-3 border-l border-[var(--color-line)] pl-4">
          {item.children.map((child) => (
            <Entrada key={child.node.id} item={child} projectId={projectId} />
          ))}
        </ol>
      ) : null}
    </li>
  );
}
