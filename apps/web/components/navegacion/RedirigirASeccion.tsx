"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

/**
 * Ruta antigua de una sección que ahora vive en la visión general. Lleva a la misma novela, con el ancla de la sección.
 * Así los enlaces guardados siguen funcionando.
 */
export function RedirigirASeccion({ ancla }: { ancla: string }) {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);
  useEffect(() => {
    if (!Number.isInteger(projectId) || projectId <= 0) return;
    // Un enlace antiguo con ?seleccionado=id se traduce a la colección de esta sección, que es la que debe seleccionarlo.
    const entrada = new URLSearchParams(window.location.search);
    const destino = new URLSearchParams();
    if (entrada.get("seleccionado") !== null) {
      destino.set("coleccion", ancla);
      destino.set("seleccionado", entrada.get("seleccionado") ?? "");
    }
    const query = destino.toString();
    router.replace(`/proyectos/${projectId}${query ? `?${query}` : ""}#${ancla}`);
  }, [ancla, projectId, router]);
  return (
    <main className="mx-auto max-w-3xl px-4 py-12">
      <p className="ne-meta">Cargando…</p>
    </main>
  );
}
