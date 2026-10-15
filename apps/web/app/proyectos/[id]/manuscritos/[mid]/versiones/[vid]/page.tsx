"use client";

import { useParams } from "next/navigation";
import { VersionPage } from "@/components/manuscritos/VersionPage";

/** Versión dentro de su novela. Si el manuscrito pertenece a otra novela o a ninguna, no se muestra su contenido. */
export default function ProjectVersionPage() {
  const params = useParams<{ id: string; mid: string; vid: string }>();
  return (
    <VersionPage
      manuscriptId={Number(params.mid)}
      versionId={Number(params.vid)}
      expectedProjectId={Number(params.id)}
    />
  );
}
