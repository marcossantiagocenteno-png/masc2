"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { api, ApiError, formatDate, type ManuscriptSummary, type VersionOut, type VersionSummary } from "@/lib/api";

/** Versiones de un manuscrito y creación de una versión nueva a partir de cualquiera de ellas. */
export default function ManuscriptPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const manuscriptId = Number(params.id);

  const [manuscript, setManuscript] = useState<ManuscriptSummary | null>(null);
  const [versions, setVersions] = useState<VersionSummary[] | null>(null);
  const [baseId, setBaseId] = useState<number | null>(null);
  const [content, setContent] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const byId = useMemo(() => new Map((versions ?? []).map((v) => [v.id, v])), [versions]);

  useEffect(() => {
    let active = true;
    Promise.all([api.getManuscript(manuscriptId), api.listVersions(manuscriptId)])
      .then(([manuscriptData, versionData]) => {
        if (!active) return;
        setManuscript(manuscriptData);
        setVersions(versionData);
        const latest = versionData[versionData.length - 1];
        if (latest) setBaseId(latest.id);
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : "Error desconocido.");
      });
    return () => {
      active = false;
    };
  }, [manuscriptId]);

  // Al cambiar la versión de partida, se carga su contenido para editarlo como punto de partida.
  useEffect(() => {
    if (baseId === null) return;
    api
      .getVersion(baseId)
      .then((version: VersionOut) => setContent(version.content))
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Error desconocido."));
  }, [baseId]);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (baseId === null) return;
    setSaving(true);
    setError(null);
    try {
      const created = await api.createVersion(manuscriptId, {
        content,
        note: note || undefined,
        based_on_version_id: baseId,
      });
      router.push(`/manuscritos/${manuscriptId}/versiones/${created.id}`);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "No se pudo crear la versión.");
      setSaving(false);
    }
  }

  if (error && !manuscript) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-12">
        <p role="alert" className="text-red-700">
          {error}
        </p>
        <Link href="/manuscritos" className="underline">
          Volver a manuscritos
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-10 px-4 py-12 sm:px-6">
      <header className="flex flex-col gap-2">
        <Link href="/manuscritos" className="text-sm text-[var(--color-muted)] underline">
          Manuscritos
        </Link>
        <p className="text-sm uppercase tracking-widest text-[var(--color-muted)]">Manuscrito</p>
        <h1 className="text-3xl font-semibold">{manuscript?.title ?? "Cargando…"}</h1>
      </header>

      <section aria-labelledby="versiones-titulo" className="flex flex-col gap-3">
        <h2 id="versiones-titulo" className="text-xl font-medium">
          Versiones
        </h2>
        {versions === null ? <p className="text-[var(--color-muted)]">Cargando…</p> : null}
        <ol className="divide-y divide-[var(--color-muted)]/40">
          {versions?.map((version) => {
            const parent = version.parent_version_id !== null ? byId.get(version.parent_version_id) : undefined;
            return (
              <li key={version.id} className="flex flex-col gap-1 py-3">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <Link
                    href={`/manuscritos/${manuscriptId}/versiones/${version.id}`}
                    className="font-medium underline"
                  >
                    Versión {version.number}
                  </Link>
                  <span className="text-sm text-[var(--color-muted)]">{formatDate(version.created_at)}</span>
                </div>
                <p className="text-sm text-[var(--color-muted)]">
                  {version.char_count} caracteres · hash {version.sha256.slice(0, 12)}…
                  {parent ? ` · creada a partir de la versión ${parent.number}` : ""}
                  {version.note ? ` · nota: ${version.note}` : ""}
                </p>
              </li>
            );
          })}
        </ol>
      </section>

      <section aria-labelledby="nueva-titulo" className="flex flex-col gap-4">
        <h2 id="nueva-titulo" className="text-xl font-medium">
          Nueva versión
        </h2>
        <p className="text-sm text-[var(--color-muted)]">
          Guardar crea una versión nueva. Las versiones anteriores no cambian.
        </p>
        <form onSubmit={handleCreate} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium">Partir de</span>
            <select
              value={baseId ?? ""}
              onChange={(event) => setBaseId(Number(event.target.value))}
              className="rounded border border-[var(--color-muted)] bg-transparent px-3 py-2"
            >
              {versions?.map((version) => (
                <option key={version.id} value={version.id}>
                  Versión {version.number}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium">Contenido de la nueva versión</span>
            <textarea
              required
              rows={12}
              value={content}
              onChange={(event) => setContent(event.target.value)}
              className="rounded border border-[var(--color-muted)] bg-transparent px-3 py-2 font-serif"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium">Nota (opcional)</span>
            <input
              maxLength={200}
              value={note}
              onChange={(event) => setNote(event.target.value)}
              className="rounded border border-[var(--color-muted)] bg-transparent px-3 py-2"
            />
          </label>
          <div>
            <button
              type="submit"
              disabled={saving || baseId === null}
              className="rounded bg-[var(--color-ink)] px-4 py-2 text-[var(--color-paper)] disabled:opacity-50"
            >
              {saving ? "Guardando…" : "Guardar como nueva versión"}
            </button>
          </div>
        </form>
        {error ? (
          <p role="alert" className="text-red-700">
            {error}
          </p>
        ) : null}
      </section>
    </main>
  );
}
