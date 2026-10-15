"use client";

import { useParams } from "next/navigation";
import { AsistenteChat } from "@/components/asistente/AsistenteChat";

/** Página del asistente de una novela. Toda la lógica vive en el componente de chat. */
export default function AsistentePage() {
  const params = useParams<{ id: string }>();
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-10 px-4 py-8 sm:px-6">
      <AsistenteChat projectId={Number(params.id)} />
    </main>
  );
}
