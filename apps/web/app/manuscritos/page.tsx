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
        <Link href="/" className="text-sm text-[var(--color-muted)] underline">
          Inicio
        </Link>
        <h1 className="text-3xl font-semibold">Manuscritos</h1>
        <p className="text-[var(--color-muted)]">
          Cada manuscrito tiene versiones numeradas. Una versión guardada no se modifica: los cambios crean una versión nueva.
        </p>
      </header>

      <section aria-labelledby="crear-titulo" className="flex flex-col gap-4">
        <h2 id="crear-titulo" className="text-xl font-medium">
          Crear manuscrito
        </h2>
        <form onSubmit={handleCreate} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium">Título del manuscrito</span>
            <input
              required
              maxLength={200}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              className="rounded border border-[var(--color-muted)] bg-transparent px-3 py-2"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium">Contenido de la versión 1</span>
            <textarea
              rows={8}
              value={content}
              onChange={(event) => setContent(event.target.value)}
              className="rounded border border-[var(--color-muted)] bg-transparent px-3 py-2 font-serif"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium">Nota de la versión (opcional)</span>
            <input
              maxLength={200}
              value={note}
              onChange={(event) => setNote(event.target.value)}
              className="rounded border border-[var(--color-muted)] bg-transparent px-3 py-2"
            />
          </label>
          <div>
            <button
              type="submit"
              disabled={saving}
              className="rounded bg-[var(--color-ink)] px-4 py-2 text-[var(--color-paper)] disabled:opacity-50"
            >
              {saving ? "Guardando…" : "Crear manuscrito"}
            </button>
          </div>
        </form>
        {error ? (
          <p role="alert" className="text-red-700">
            {error}
          </p>
        ) : null}
      </section>

      <section aria-labelledby="lista-titulo" className="flex flex-col gap-3">
        <h2 id="lista-titulo" className="text-xl font-medium">
          Manuscritos guardados
        </h2>
        {items === null ? <p className="text-[var(--color-muted)]">Cargando…</p> : null}
        {items?.length === 0 ? <p className="text-[var(--color-muted)]">Todavía no hay manuscritos.</p> : null}
        <ul className="divide-y divide-[var(--color-muted)]/40">
          {items?.map((item) => (
            <li key={item.id} className="flex flex-wrap items-baseline justify-between gap-2 py-3">
              <Link href={`/manuscritos/${item.id}`} className="font-medium underline">
                {item.title}
              </Link>
              <span className="text-sm text-[var(--color-muted)]">
                {item.version_count} {item.version_count === 1 ? "versión" : "versiones"} · creado {formatDate(item.created_at)}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
