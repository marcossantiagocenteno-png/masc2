"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { VersionPage } from "@/components/manuscritos/VersionPage";
import { api, ApiError } from "@/lib/api";
import { versionPath } from "@/lib/manuscript-paths";

/** Ruta anterior de una versión. Si el manuscrito tiene proyecto, se redirige a su ruta dentro de la novela. */
export default function LegacyVersionPage() {
  const router = useRouter();
  const params = useParams<{ id: string; versionId: string }>();
  const manuscriptId = Number(params.id);
  const versionId = Number(params.versionId);
  const [state, setState] = useState<{ kind: "checking" } | { kind: "ready" } | { kind: "error"; message: string }>({
    kind: "checking",
  });

  useEffect(() => {
    let active = true;
    api.getManuscript(manuscriptId).then(
      (manuscript) => {
        if (!active) return;
        if (manuscript.project_id !== null) {
          router.replace(versionPath(manuscript.project_id, manuscript.id, versionId));
          return;
        }
        setState({ kind: "ready" });
      },
      (reason: unknown) => {
        if (active) setState({ kind: "error", message: reason instanceof ApiError ? reason.message : "No se pudo abrir la versión." });
      },
    );
    return () => {
      active = false;
    };
  }, [manuscriptId, versionId, router]);

  if (state.kind === "ready") {
    return <VersionPage manuscriptId={manuscriptId} versionId={versionId} expectedProjectId={null} />;
  }
  if (state.kind === "error") {
    return (
      <main className="mx-auto max-w-3xl px-4 py-12">
        <p role="alert" className="ne-notice ne-notice--danger">
          {state.message}
        </p>
        <Link href={`/manuscritos/${manuscriptId}`} className="ne-link">
          Volver al manuscrito
        </Link>
      </main>
    );
  }
  return (
    <main className="mx-auto max-w-3xl px-4 py-12">
      <p className="ne-meta">Cargando…</p>
    </main>
  );
}
