"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ManuscriptPage } from "@/components/manuscritos/ManuscriptPage";
import { api, ApiError } from "@/lib/api";
import { manuscriptPath } from "@/lib/manuscript-paths";

/**
 * Ruta anterior de un manuscrito. Si tiene proyecto, se redirige a su ruta dentro de la novela. El proyecto se lee
 * del propio manuscrito, nunca de la URL, así que la redirección no puede llevar a otra novela. Sin proyecto, se muestra aquí.
 */
export default function LegacyManuscriptPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const manuscriptId = Number(params.id);
  const [state, setState] = useState<{ kind: "checking" } | { kind: "ready" } | { kind: "error"; message: string }>({
    kind: "checking",
  });

  useEffect(() => {
    let active = true;
    api.getManuscript(manuscriptId).then(
      (manuscript) => {
        if (!active) return;
        if (manuscript.project_id !== null) {
          router.replace(manuscriptPath(manuscript.project_id, manuscript.id));
          return;
        }
        setState({ kind: "ready" });
      },
      (reason: unknown) => {
        if (active) setState({ kind: "error", message: reason instanceof ApiError ? reason.message : "No se pudo abrir el manuscrito." });
      },
    );
    return () => {
      active = false;
    };
  }, [manuscriptId, router]);

  if (state.kind === "ready") return <ManuscriptPage manuscriptId={manuscriptId} expectedProjectId={null} />;
  if (state.kind === "error") {
    return (
      <main className="mx-auto max-w-3xl px-4 py-12">
        <p role="alert" className="ne-notice ne-notice--danger">
          {state.message}
        </p>
        <Link href="/manuscritos" className="ne-link">
          Volver a manuscritos
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
