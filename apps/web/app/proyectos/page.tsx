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
        <Link href="/" className="ne-meta ne-link">
          Inicio
        </Link>
        <h1 className="ne-page-title">Proyectos</h1>
        <p className="ne-lede">
          Cada novela es un proyecto independiente. Sus manuscritos, versiones y análisis no se mezclan con los de otros proyectos.
        </p>
      </header>

      <section aria-labelledby="nuevo-proyecto" className="flex flex-col gap-4">
        <h2 id="nuevo-proyecto" className="ne-section-title">
          Nuevo proyecto
        </h2>
        <form onSubmit={handleCreate} className="flex flex-wrap items-end gap-3">
          <label className="flex min-w-64 flex-1 flex-col gap-1">
            <span className="ne-label">Nombre de la novela</span>
            <input
              required
              maxLength={120}
              value={name}
              onChange={(event) => setName(event.target.value)}
              
            />
          </label>
          <button
            type="submit"
            disabled={saving}
            className="ne-button ne-button--primary"
          >
            {saving ? "Creando…" : "Crear proyecto"}
          </button>
        </form>
      </section>

      <section aria-labelledby="lista-proyectos" className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="lista-proyectos" className="ne-section-title">
            {filter === "activo" ? "Proyectos activos" : "Proyectos archivados"}
          </h2>
          <div role="group" aria-label="Filtrar por estado" className="ne-segment">
            <button type="button" aria-pressed={filter === "activo"} onClick={() => setFilter("activo")}>
              Activos
            </button>
            <button type="button" aria-pressed={filter === "archivado"} onClick={() => setFilter("archivado")}>
              Archivados
            </button>
          </div>
        </div>

        {error ? (
          <p role="alert" className="ne-notice ne-notice--danger">
            {error}
          </p>
        ) : null}
        {projects === null && !error ? <p className="ne-meta">Cargando…</p> : null}
        {projects?.length === 0 ? (
          <p className="ne-meta">
            {filter === "activo" ? "Todavía no hay proyectos activos." : "No hay proyectos archivados."}
          </p>
        ) : null}
        <ul className="ne-list ne-project-list">
          {projects?.map((project) => (
            <li key={project.id} className="ne-project-row">
              <Link href={`/proyectos/${project.id}`} className="ne-project-name">
                {project.name}
              </Link>
              <span className="ne-meta">
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
