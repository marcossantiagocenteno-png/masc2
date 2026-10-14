"use client";

import { useParams } from "next/navigation";
import { ElementCollection } from "@/components/planning/ElementCollection";
import { COLLECTIONS } from "@/lib/planning";

/** Lugares. Datos de la API de planificación de la novela indicada en la URL. */
export default function Page() {
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);
  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-8 px-4 py-10 sm:px-6">
      <header className="flex flex-col gap-2">
        <h1 className="ne-page-title">Lugares</h1>
        <p className="ne-meta">Basta con un nombre para crear un lugar.</p>
      </header>
      <ElementCollection projectId={projectId} config={COLLECTIONS.lugares} />
    </main>
  );
}
