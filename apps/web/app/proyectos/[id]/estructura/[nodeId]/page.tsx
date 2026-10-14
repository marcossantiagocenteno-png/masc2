"use client";

import { useParams } from "next/navigation";
import { SceneDetail } from "@/components/planning/SceneDetail";

/** Escena. La identidad es el id de la URL: no cambia aunque la reordenes. */
export default function ScenePage() {
  const params = useParams<{ id: string; nodeId: string }>();
  const projectId = Number(params.id);
  const nodeId = Number(params.nodeId);
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-10 sm:px-6">
      {Number.isInteger(nodeId) && nodeId > 0 ? (
        <SceneDetail projectId={projectId} nodeId={nodeId} />
      ) : (
        <p role="alert" className="ne-notice ne-notice--danger">La dirección de la escena no es válida.</p>
      )}
    </main>
  );
}
