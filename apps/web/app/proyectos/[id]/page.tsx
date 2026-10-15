"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { DirectivesForm } from "@/components/planning/DirectivesForm";
import { NarrativeForm } from "@/components/planning/NarrativeForm";
import { manuscriptPath } from "@/lib/manuscript-paths";
import {
  api,
  ApiError,
  formatDate,
  type ManuscriptSummary,
  type ProjectDetail,
} from "@/lib/api";

/** Panel de un proyecto: estado, último trabajo, manuscritos y acciones del proyecto. */
export default function ProjectPanelPage() {
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);

  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [manuscripts, setManuscripts] = useState<ManuscriptSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [rename, setRename] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [detail, list] = await Promise.all([api.getProject(projectId), api.listProjectManuscripts(projectId)]);
      setProject(detail);
      setManuscripts(list);
      setRename(detail.name);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Error desconocido.");
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  function fail(reason: unknown, fallback: string) {
    setNotice(null);
    setError(reason instanceof ApiError ? reason.message : fallback);
  }

  async function handleCreateManuscript(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await api.createProjectManuscript(projectId, { title, content });
      setTitle("");
      setContent("");
      setNotice(`Manuscrito «${created.title}» creado en este proyecto.`);
      await load();
    } catch (reason) {
      fail(reason, "No se pudo crear el manuscrito.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRename(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      await api.renameProject(projectId, rename);
      setNotice("Nombre del proyecto actualizado.");
      await load();
    } catch (reason) {
      fail(reason, "No se pudo renombrar el proyecto.");
    } finally {
      setBusy(false);
    }
  }

  async function handleArchive() {
    // Archivar no borra nada: se pide confirmación solo para evitar un clic accidental.
    if (!window.confirm("Archivar el proyecto. No se borra nada: podrás restaurarlo después. ¿Continuar?")) return;
    setBusy(true);
    try {
      await api.archiveProject(projectId);
      setNotice("Proyecto archivado. Sus textos siguen disponibles.");
      await load();
    } catch (reason) {
      fail(reason, "No se pudo archivar el proyecto.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRestore() {
    setBusy(true);
    try {
      await api.restoreProject(projectId);
      setNotice("Proyecto restaurado.");
      await load();
    } catch (reason) {
      fail(reason, "No se pudo restaurar el proyecto.");
    } finally {
      setBusy(false);
    }
  }

  if (project === null && error) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-12">
        <p role="alert" className="ne-notice ne-notice--danger">
          {error}
        </p>
        <Link href="/proyectos" className="ne-link">
          Volver a proyectos
        </Link>
      </main>
    );
  }

  const archived = project?.status === "archivado";
  const latest = manuscripts?.[0] ?? null;

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-10 px-4 py-8 sm:px-6">
      <header className="flex flex-col gap-2">
        <Link href="/proyectos" className="ne-meta ne-link">
          Proyectos
        </Link>
        <h1 className="ne-page-title">{project?.name ?? "Cargando…"}</h1>
        {project ? (
          <p className="ne-meta">
            {archived ? "Archivado" : "Activo"} · {project.manuscript_count}{" "}
            {project.manuscript_count === 1 ? "manuscrito" : "manuscritos"}
            {project.last_activity_at ? ` · última actividad ${formatDate(project.last_activity_at)}` : ""}
          </p>
        ) : null}
      </header>

      <section aria-labelledby="vision" className="flex flex-col gap-4">
        <h2 id="vision" className="ne-section-title">
          Visión general de la novela
        </h2>
        <NarrativeForm projectId={projectId} />
      </section>

      <section aria-labelledby="directrices" className="flex flex-col gap-4">
        <h2 id="directrices" className="ne-section-title">
          Directrices narrativas
        </h2>
        <DirectivesForm projectId={projectId} />
      </section>

      {error ? (
        <p role="alert" className="ne-notice ne-notice--danger">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p role="status" className="ne-notice ne-notice--ok">
          {notice}
        </p>
      ) : null}

      {latest ? (
        <section aria-labelledby="continuar" className="flex flex-col gap-2">
          <h2 id="continuar" className="ne-section-title">
            Dónde te quedaste
          </h2>
          <p>
            Último manuscrito: <span className="font-medium">{latest.title}</span>
          </p>
          <div className="text-sm">
            <Link href={manuscriptPath(projectId, latest.id)} className="ne-link">
              Abrir «{latest.title}» para escribir o revisar
            </Link>
          </div>
        </section>
      ) : null}

      <section aria-labelledby="nuevo-manuscrito" className="flex flex-col gap-4">
        <h2 id="nuevo-manuscrito" className="ne-section-title">
          Nuevo manuscrito en este proyecto
        </h2>
        {archived ? (
          <p className="ne-meta">El proyecto está archivado. Restáuralo para añadir manuscritos.</p>
        ) : (
          <form onSubmit={handleCreateManuscript} className="flex flex-col gap-4">
            <label className="flex flex-col gap-1">
              <span className="ne-label">Título</span>
              <input
                required
                maxLength={200}
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="ne-label">Texto de la versión 1</span>
              <textarea
                required
                rows={6}
                value={content}
                onChange={(event) => setContent(event.target.value)}
                className="ne-prose-field"
              />
            </label>
            <div>
              <button
                type="submit"
                disabled={busy}
                className="ne-button ne-button--primary"
              >
                Crear manuscrito
              </button>
            </div>
          </form>
        )}
      </section>

      <section aria-labelledby="gestion" className="flex flex-col gap-4">
        <h2 id="gestion" className="ne-section-title">
          Gestión del proyecto
        </h2>
        <form onSubmit={handleRename} className="flex flex-wrap items-end gap-3">
          <label className="flex min-w-64 flex-1 flex-col gap-1">
            <span className="ne-label">Nombre</span>
            <input
              required
              maxLength={120}
              value={rename}
              onChange={(event) => setRename(event.target.value)}
              
            />
          </label>
          <button type="submit" disabled={busy} className="ne-button">
            Guardar nombre
          </button>
        </form>
        {archived ? (
          <button type="button" onClick={handleRestore} disabled={busy} className="self-start ne-button">
            Restaurar proyecto
          </button>
        ) : (
          <div className="flex flex-col gap-1">
            <button type="button" onClick={handleArchive} disabled={busy} className="self-start ne-button">
              Archivar proyecto
            </button>
            <p className="ne-meta">Archivar no borra nada. Los textos siguen disponibles.</p>
          </div>
        )}
      </section>
    </main>
  );
}
