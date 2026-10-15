"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

/** No hay página de lista: los manuscritos de la novela se abren desde «Manuscrito», su entrada principal. */
export default function ProjectManuscriptsRedirect() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);
  useEffect(() => {
    if (Number.isInteger(projectId) && projectId > 0) router.replace(`/proyectos/${projectId}/libro`);
  }, [projectId, router]);
  return (
    <main className="mx-auto max-w-3xl px-4 py-12">
      <p className="ne-meta">Cargando…</p>
    </main>
  );
}
