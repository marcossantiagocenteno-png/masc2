"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { EstructuraRecomendada } from "@/components/planning/EstructuraRecomendada";
import { StructureView } from "@/components/planning/StructureView";

/**
 * Estructura. Datos de la API de planificación de la novela indicada en la URL.
 * Las recomendaciones van primero; al aceptar una etapa, la vista de actos se vuelve a cargar para mostrar el acto nuevo.
 */
export default function Page() {
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);
  const [revision, setRevision] = useState(0);
  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-12 px-4 py-10 sm:px-6">
      <header className="flex flex-col gap-2">
        <h1 className="ne-page-title">Estructura</h1>
        <p className="ne-meta">Actos, capítulos y escenas. Reordena con los botones de cada fila; cada elemento conserva su identidad.</p>
      </header>
      <EstructuraRecomendada projectId={projectId} onActoCreado={() => setRevision((value) => value + 1)} />
      <StructureView key={revision} projectId={projectId} />
    </main>
  );
}
