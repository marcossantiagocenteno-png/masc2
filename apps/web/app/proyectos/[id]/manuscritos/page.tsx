"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

/** No hay página propia: los manuscritos de la novela están en su resumen, en «Manuscritos del proyecto». */
export default function ProjectManuscriptsRedirect() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);
  useEffect(() => {
    if (Number.isInteger(projectId) && projectId > 0) router.replace(`/proyectos/${projectId}#manuscritos`);
  }, [projectId, router]);
  return (
    <main className="mx-auto max-w-3xl px-4 py-12">
      <p className="ne-meta">Cargando…</p>
    </main>
  );
}
