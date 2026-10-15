"use client";

import { useParams } from "next/navigation";
import { ManuscriptPage } from "@/components/manuscritos/ManuscriptPage";

/** Manuscrito dentro de su novela. Si pertenece a otra novela o a ninguna, la página no carga su contenido. */
export default function ProjectManuscriptPage() {
  const params = useParams<{ id: string; mid: string }>();
  return <ManuscriptPage manuscriptId={Number(params.mid)} expectedProjectId={Number(params.id)} />;
}
