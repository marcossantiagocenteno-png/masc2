"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError, formatDate, type Project, type ProjectStatus } from "@/lib/api";

/** Biblioteca de proyectos: cada novela es un proyecto aislado. */
export default function ProjectLibraryPage() {
  const router = useRouter();
  const [filter, setFilter] = useState<ProjectStatus>("activo");
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    setProjects(null);
    api
      .listProjects(filter)
      .then((list) => active && setProjects(list))
      .catch((reason: unknown) => active && setError(reason instanceof Error ? reason.message : "Error desconocido."));
    return () => {
      active = false;
    };
  }, [filter]);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const created = await api.createProject(name);
      router.push(`/proyectos/${created.id}`);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "No se pudo crear el proyecto.");
      setSaving(false);
    }
  }

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-10 px-4 py-12 sm:px-6">
      <header className="flex flex-col gap-2">
        <Link href="/" className="text-sm text-[var(--color-muted)] underline">
          Inicio
        </Link>
        <h1 className="text-3xl font-semibold">Proyectos</h1>
        <p className="text-[var(--color-muted)]">
          Cada novela es un proyecto independiente. Sus manuscritos, versiones y análisis no se mezclan con los de otros proyectos.
        </p>
      </header>

      <section aria-labelledby="nuevo-proyecto" className="flex flex-col gap-4">
        <h2 id="nuevo-proyecto" className="text-xl font-medium">
          Nuevo proyecto
        </h2>
        <form onSubmit={handleCreate} className="flex flex-wrap items-end gap-3">
          <label className="flex min-w-64 flex-1 flex-col gap-1">
            <span className="text-sm font-medium">Nombre de la novela</span>
            <input
              required
              maxLength={120}
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="rounded border border-[var(--color-muted)] bg-transparent px-3 py-2"
            />
          </label>
          <button
            type="submit"
            disabled={saving}
            className="rounded bg-[var(--color-ink)] px-4 py-2 text-[var(--color-paper)] disabled:opacity-50"
          >
            {saving ? "Creando…" : "Crear proyecto"}
          </button>
        </form>
      </section>

      <section aria-labelledby="lista-proyectos" className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="lista-proyectos" className="text-xl font-medium">
            {filter === "activo" ? "Proyectos activos" : "Proyectos archivados"}
          </h2>
          <div role="group" aria-label="Filtrar por estado" className="flex gap-2 text-sm">
            <button
              type="button"
              aria-pressed={filter === "activo"}
              onClick={() => setFilter("activo")}
              className={`rounded px-3 py-1 ${filter === "activo" ? "bg-[var(--color-ink)] text-[var(--color-paper)]" : "border border-[var(--color-muted)]"}`}
            >
              Activos
            </button>
            <button
              type="button"
              aria-pressed={filter === "archivado"}
              onClick={() => setFilter("archivado")}
              className={`rounded px-3 py-1 ${filter === "archivado" ? "bg-[var(--color-ink)] text-[var(--color-paper)]" : "border border-[var(--color-muted)]"}`}
            >
              Archivados
            </button>
          </div>
        </div>

        {error ? (
          <p role="alert" className="text-red-700">
            {error}
          </p>
        ) : null}
        {projects === null && !error ? <p className="text-[var(--color-muted)]">Cargando…</p> : null}
        {projects?.length === 0 ? (
          <p className="text-[var(--color-muted)]">
            {filter === "activo" ? "Todavía no hay proyectos activos." : "No hay proyectos archivados."}
          </p>
        ) : null}
        <ul className="divide-y divide-[var(--color-muted)]/40">
          {projects?.map((project) => (
            <li key={project.id} className="flex flex-wrap items-baseline justify-between gap-2 py-3">
              <Link href={`/proyectos/${project.id}`} className="font-medium underline">
                {project.name}
              </Link>
              <span className="text-sm text-[var(--color-muted)]">
                {project.status === "archivado" && project.archived_at
                  ? `archivado el ${formatDate(project.archived_at)}`
                  : `actualizado ${formatDate(project.updated_at)}`}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
