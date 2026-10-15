"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError, type Project } from "@/lib/api";

/**
 * Lista de novelas activas. El servidor las devuelve por última modificación, de la más reciente a la más antigua.
 * Se vuelve a pedir en cada cambio de ruta para que un proyecto creado o renombrado aparezca sin recargar.
 */
export function ProjectsSidebar() {
  const pathname = usePathname();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    api
      .listProjects("activo")
      .then((list) => {
        if (!active) return;
        setProjects(list);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof ApiError ? reason.message : "No se pudieron cargar los proyectos.");
      });
    return () => {
      active = false;
    };
  }, [pathname]);

  const currentId = /^\/proyectos\/(\d+)/.exec(pathname)?.[1];

  return (
    <div className="flex flex-col gap-3">
      <p className="ne-kicker">Novelas</p>
      {projects === null && !error ? <p className="ne-meta">Cargando…</p> : null}
      {error ? (
        <p role="alert" className="ne-notice ne-notice--danger">
          {error}
        </p>
      ) : null}
      {projects?.length === 0 ? <p className="ne-meta">Todavía no hay proyectos activos.</p> : null}
      {projects && projects.length > 0 ? (
        <ul className="ne-list">
          {projects.map((project) => {
            const current = String(project.id) === currentId;
            return (
              <li key={project.id}>
                <Link
                  href={`/proyectos/${project.id}`}
                  aria-current={current ? "page" : undefined}
                  className={`ne-project-name block py-2 ${current ? "font-medium" : ""}`}
                >
                  {project.name}
                </Link>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
