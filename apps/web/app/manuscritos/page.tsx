"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { api, ApiError, formatDate, type ManuscriptSummary, type Project } from "@/lib/api";
import { manuscriptPath } from "@/lib/manuscript-paths";

/**
 * Manuscritos fuera de los espacios de trabajo: los que no tienen proyecto y los de las novelas, agrupados por novela.
 * Los manuscritos de escena son el texto de una escena y se abren desde esa escena: no aparecen aquí.
 */
export default function ManuscriptsPage() {
  const router = useRouter();
  const [items, setItems] = useState<ManuscriptSummary[] | null>(null);
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.all([api.listManuscripts(), api.listProjects("todos")])
      .then(([list, projectList]) => {
        if (!active) return;
        setItems(list);
        setProjects(projectList);
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : "Error desconocido.");
      });
    return () => {
      active = false;
    };
  }, []);

  const visibles = useMemo(() => (items ?? []).filter((item) => item.scene_node_id === null), [items]);
  const sinProyecto = visibles.filter((item) => item.project_id === null);
  const enNovelas = visibles.filter((item) => item.project_id !== null);
  const nombres = useMemo(() => new Map((projects ?? []).map((project) => [project.id, project.name])), [projects]);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const created = await api.createManuscript({ title, content, note: note || undefined });
      router.push(manuscriptPath(null, created.id));
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "No se pudo crear el manuscrito.");
      setSaving(false);
    }
  }

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-10 px-4 py-12 sm:px-6">
      <header className="flex flex-col gap-2">
        <Link href="/" className="ne-meta ne-link">
          Inicio
        </Link>
        <h1 className="ne-page-title">Manuscritos</h1>
        <p className="ne-meta">
          Cada manuscrito tiene versiones numeradas. Una versión guardada no se modifica: los cambios crean una versión nueva.
          Los manuscritos de una novela se abren desde su espacio de trabajo.
        </p>
      </header>

      <section aria-labelledby="crear-titulo" className="flex flex-col gap-4">
        <h2 id="crear-titulo" className="ne-section-title">
          Crear manuscrito
        </h2>
        <p className="ne-meta">Se crea en «Sin proyecto». Para crearlo dentro de una novela, usa su espacio de trabajo.</p>
        <form onSubmit={handleCreate} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1">
            <span className="ne-label">Título del manuscrito</span>
            <input
              required
              maxLength={200}
              value={title}
              onChange={(event) => setTitle(event.target.value)}

            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="ne-label">Contenido de la versión 1</span>
            <textarea
              rows={8}
              value={content}
              onChange={(event) => setContent(event.target.value)}
              className="ne-prose-field"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="ne-label">Nota de la versión (opcional)</span>
            <input
              maxLength={200}
              value={note}
              onChange={(event) => setNote(event.target.value)}

            />
          </label>
          <div>
            <button type="submit" disabled={saving} className="ne-button ne-button--primary">
              {saving ? "Guardando…" : "Crear manuscrito"}
            </button>
          </div>
        </form>
        {error ? (
          <p role="alert" className="ne-notice ne-notice--danger">
            {error}
          </p>
        ) : null}
      </section>

      <section aria-labelledby="sin-proyecto-titulo" className="flex flex-col gap-3">
        <h2 id="sin-proyecto-titulo" className="ne-section-title">
          Sin proyecto
        </h2>
        {items === null && !error ? <p className="ne-meta">Cargando…</p> : null}
        {items !== null && sinProyecto.length === 0 ? (
          <p className="ne-empty">No hay manuscritos sin proyecto.</p>
        ) : null}
        <ul className="divide-y divide-[var(--color-muted)]/40">
          {sinProyecto.map((item) => (
            <li key={item.id} className="flex flex-wrap items-baseline justify-between gap-2 py-3">
              <Link href={manuscriptPath(null, item.id)} className="ne-link font-medium">
                {item.title}
              </Link>
              <span className="ne-meta">
                {item.version_count} {item.version_count === 1 ? "versión" : "versiones"} · creado {formatDate(item.created_at)}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="en-novelas-titulo" className="flex flex-col gap-3">
        <h2 id="en-novelas-titulo" className="ne-section-title">
          Manuscritos de las novelas
        </h2>
        {items !== null && enNovelas.length === 0 ? <p className="ne-empty">Ninguna novela tiene manuscritos todavía.</p> : null}
        <ul className="divide-y divide-[var(--color-muted)]/40">
          {enNovelas.map((item) => (
            <li key={item.id} className="flex flex-wrap items-baseline justify-between gap-2 py-3">
              <Link href={manuscriptPath(item.project_id, item.id)} className="ne-link font-medium">
                {item.title}
              </Link>
              <span className="ne-meta">
                {nombres.get(item.project_id ?? -1) ?? "Novela"} · {item.version_count}{" "}
                {item.version_count === 1 ? "versión" : "versiones"}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
