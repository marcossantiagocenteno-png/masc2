"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError, formatDate, type ManuscriptSummary } from "@/lib/api";

/** Lista de manuscritos y formulario para crear uno con su versión 1. */
export default function ManuscriptsPage() {
  const router = useRouter();
  const [items, setItems] = useState<ManuscriptSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .listManuscripts()
      .then(setItems)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Error desconocido."));
  }, []);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const created = await api.createManuscript({ title, content, note: note || undefined });
      router.push(`/manuscritos/${created.id}`);
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
        <p className="text-[var(--color-muted)]">
          Cada manuscrito tiene versiones numeradas. Una versión guardada no se modifica: los cambios crean una versión nueva.
        </p>
      </header>

      <section aria-labelledby="crear-titulo" className="flex flex-col gap-4">
        <h2 id="crear-titulo" className="ne-section-title">
          Crear manuscrito
        </h2>
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
            <button
              type="submit"
              disabled={saving}
              className="ne-button ne-button--primary"
            >
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

      <section aria-labelledby="lista-titulo" className="flex flex-col gap-3">
        <h2 id="lista-titulo" className="ne-section-title">
          Manuscritos guardados
        </h2>
        {items === null ? <p className="text-[var(--color-muted)]">Cargando…</p> : null}
        {items?.length === 0 ? <p className="text-[var(--color-muted)]">Todavía no hay manuscritos.</p> : null}
        <ul className="divide-y divide-[var(--color-muted)]/40">
          {items?.map((item) => (
            <li key={item.id} className="flex flex-wrap items-baseline justify-between gap-2 py-3">
              <Link href={`/manuscritos/${item.id}`} className="ne-link font-medium">
                {item.title}
              </Link>
              <span className="ne-meta">
                {item.version_count} {item.version_count === 1 ? "versión" : "versiones"} · creado {formatDate(item.created_at)}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
