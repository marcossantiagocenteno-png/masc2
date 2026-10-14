"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type FormEvent, type MouseEvent } from "react";
import DraftStatus from "@/components/DraftStatus";
import RecoveryPoints from "@/components/RecoveryPoints";
import {
  api,
  ApiError,
  formatDate,
  manuscriptOps,
  type ManuscriptOps,
  type ManuscriptSummary,
  type RecoveryPointSummary,
  type VersionOut,
  type VersionSummary,
} from "@/lib/api";
import { DraftSaver, type SaveStatus } from "@/lib/draft-saver";

const NETWORK_HINT = "No se pudo completar la operación.";

function messageOf(reason: unknown, fallback = NETWORK_HINT): string {
  return reason instanceof ApiError ? reason.message : fallback;
}

/**
 * Versiones de un manuscrito y su borrador de trabajo.
 *
 * El texto del editor es el borrador. Se guarda en el servidor mientras se escribe
 * (ver ``DraftSaver``), se recupera al volver a abrir la página y tiene puntos de
 * recuperación. Crear una versión formal sigue siendo una acción explícita.
 */
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
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<SaveStatus | null>(null);
  const [points, setPoints] = useState<RecoveryPointSummary[] | null>(null);
  const [pointsError, setPointsError] = useState<string | null>(null);
  const [restoreError, setRestoreError] = useState<string | null>(null);
  const saverRef = useRef<DraftSaver | null>(null);
  // Operaciones con el ámbito del proyecto del manuscrito; se fijan al cargarlo.
  const opsRef = useRef<ManuscriptOps | null>(null);

  const byId = useMemo(() => new Map((versions ?? []).map((v) => [v.id, v])), [versions]);
  const ready = status !== null;

  function refreshPoints() {
    const ops = opsRef.current;
    if (!ops) return;
    ops.listRecoveryPoints().then(
      (list) => {
        setPoints(list);
        setPointsError(null);
      },
      (reason: unknown) => setPointsError(messageOf(reason, "No se pudieron cargar los puntos.")),
    );
  }

  // Carga: versiones, manuscrito y borrador. El borrador existente nunca se reemplaza.
  useEffect(() => {
    let active = true;
    async function load() {
      try {
        // Primero el manuscrito: dice a qué proyecto pertenece y, por tanto, qué rutas usar.
        const manuscriptData = await api.getManuscript(manuscriptId);
        const ops = manuscriptOps(manuscriptData.project_id, manuscriptId);
        opsRef.current = ops;
        const [versionData, initialized] = await Promise.all([ops.listVersions(), ops.initDraft()]);
        if (!active) return;
        setManuscript(manuscriptData);
        setVersions(versionData);
        const latest = versionData[versionData.length - 1];
        if (latest) setBaseId(latest.id);

        saverRef.current?.dispose();
        // Un guardado confirmado puede haber creado un punto de recuperación: la lista se refresca.
        let savingInFlight = false;
        saverRef.current = new DraftSaver(
          initialized.draft,
          (body) => ops.saveDraft(body),
          (next) => {
            if (!active) return;
            if (next.kind === "saving") savingInFlight = true;
            if (next.kind === "saved" && savingInFlight) {
              savingInFlight = false;
              void ops.listRecoveryPoints().then(
                (list) => active && setPoints(list),
                () => undefined,
              );
            }
            setStatus(next);
          },
        );
        setContent(initialized.draft.content);
        setStatus({ kind: "saved", at: null });
        const list = await ops.listRecoveryPoints();
        if (active) setPoints(list);
      } catch (reason: unknown) {
        if (active) setError(messageOf(reason, "Error desconocido."));
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [manuscriptId]);

  useEffect(() => {
    return () => saverRef.current?.dispose();
  }, []);

  // Cerrar o recargar con cambios sin confirmar: aviso del navegador y envío de último recurso.
  useEffect(() => {
    function onBeforeUnload(event: BeforeUnloadEvent) {
      if (saverRef.current?.hasUnsavedChanges()) {
        event.preventDefault();
        event.returnValue = "";
      }
    }
    function onPageHide() {
      const body = saverRef.current?.keepaliveRequest();
      if (body) opsRef.current?.saveDraftKeepalive(body);
    }
    window.addEventListener("beforeunload", onBeforeUnload);
    window.addEventListener("pagehide", onPageHide);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
      window.removeEventListener("pagehide", onPageHide);
    };
  }, [manuscriptId]);

  function handleEdit(value: string) {
    setContent(value);
    saverRef.current?.edit(value);
  }

  /** Cambia la versión de partida. Si el texto difiere, pide confirmación y lo guarda como punto antes de reemplazarlo. */
  async function handleBaseChange(nextId: number) {
    if (nextId === baseId || !saverRef.current || !opsRef.current) return;
    setFormError(null);
    let version: VersionOut;
    try {
      version = await opsRef.current.getVersion(nextId);
    } catch (reason) {
      setFormError(messageOf(reason, "No se pudo cargar la versión elegida."));
      return;
    }
    if (
      version.content !== content &&
      !window.confirm(
        "Se reemplazará el texto del editor por el de la versión elegida. El texto anterior queda en los puntos de recuperación. ¿Continuar?",
      )
    ) {
      return; // El select es controlado: vuelve a mostrar la versión anterior.
    }
    const replaced = await saverRef.current.replace(version.content);
    if (!replaced) {
      setFormError("No se ha podido guardar el texto actual; no se ha reemplazado. Reintenta o descarga una copia.");
      return;
    }
    setContent(version.content);
    setBaseId(nextId);
    refreshPoints();
  }

  /** Antes de salir por un enlace interno, guarda lo pendiente. Si no puede, avisa. */
  async function guardNavigation(event: MouseEvent<HTMLElement>) {
    const saver = saverRef.current;
    const anchor = (event.target as HTMLElement).closest("a");
    if (!saver || !anchor || !saver.hasUnsavedChanges()) return;
    const href = anchor.getAttribute("href");
    if (!href || !href.startsWith("/")) return;
    event.preventDefault();
    if (await saver.flush()) {
      router.push(href);
      return;
    }
    if (window.confirm("No se ha podido guardar el texto. ¿Salir igualmente? El texto que no está guardado se perdería.")) {
      router.push(href);
    }
  }

  async function handleRetry() {
    await saverRef.current?.retry();
  }

  function handleUseServer() {
    const text = saverRef.current?.useServerContent();
    if (text !== null && text !== undefined) setContent(text);
    refreshPoints();
  }

  async function handleKeepMine() {
    await saverRef.current?.keepMine();
    refreshPoints();
  }

  function downloadCopy() {
    const safeName = (manuscript?.title ?? "manuscrito").replace(/[^\p{L}\p{N} _-]+/gu, "_");
    const url = URL.createObjectURL(new Blob([content], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${safeName}.txt`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function handleRestore(point: RecoveryPointSummary) {
    const saver = saverRef.current;
    if (!saver) return;
    if (
      !window.confirm(
        "El texto actual se guardará como punto «Antes de restaurar» y el borrador pasará a ser el de este punto. ¿Restaurar?",
      )
    ) {
      return;
    }
    setRestoreError(null);
    if (!(await saver.flush())) {
      setRestoreError("No se ha podido guardar el texto actual. No se ha restaurado nada.");
      return;
    }
    try {
      const draft = await opsRef.current!.restoreRecoveryPoint(point.id, saver.getRevision());
      saver.reset(draft);
      setContent(draft.content);
      refreshPoints();
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 409) {
        setRestoreError("El borrador ha cambiado en otra ventana. Recarga la página antes de restaurar.");
      } else {
        setRestoreError(messageOf(reason, "No se pudo restaurar el punto."));
      }
    }
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (baseId === null || !saverRef.current || !opsRef.current) return;
    setSaving(true);
    setFormError(null);
    // El borrador debe contener el mismo texto que la versión que se crea, así que se guarda antes.
    if (!(await saverRef.current.flush())) {
      setFormError("No se ha podido guardar el borrador; la versión no se ha creado.");
      setSaving(false);
      return;
    }
    try {
      const created = await opsRef.current.createVersion({
        content,
        note: note || undefined,
        based_on_version_id: baseId,
      });
      router.push(`/manuscritos/${manuscriptId}/versiones/${created.id}`);
    } catch (reason) {
      setFormError(messageOf(reason, "No se pudo crear la versión."));
      setSaving(false);
    }
  }

  if (error && !manuscript) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-12">
        <p role="alert" className="ne-notice ne-notice--danger">
          {error}
        </p>
        <Link href="/manuscritos" className="ne-link">
          Volver a manuscritos
        </Link>
      </main>
    );
  }

  return (
    <main
      onClickCapture={guardNavigation}
      className="mx-auto flex max-w-3xl flex-col gap-10 px-4 py-12 sm:px-6"
    >
      <header className="flex flex-col gap-2">
        <Link href="/manuscritos" className="ne-meta ne-link">
          Manuscritos
        </Link>
        <p className="ne-kicker">Manuscrito</p>
        <h1 className="ne-page-title">{manuscript?.title ?? "Cargando…"}</h1>
        {manuscript?.scene_node_id ? (
          <p className="ne-meta">
            Es el texto de una escena. Su título es el de la escena y se cambia allí:{" "}
            <Link href={`/proyectos/${manuscript.project_id}/estructura/${manuscript.scene_node_id}`} className="ne-link">
              editar la escena
            </Link>
            .
          </p>
        ) : null}
      </header>

      <section aria-labelledby="versiones-titulo" className="flex flex-col gap-3">
        <h2 id="versiones-titulo" className="ne-section-title">
          Versiones
        </h2>
        {versions === null ? <p className="ne-meta">Cargando…</p> : null}
        <ol className="divide-y divide-[var(--color-muted)]/40">
          {versions?.map((version) => {
            const parent = version.parent_version_id !== null ? byId.get(version.parent_version_id) : undefined;
            return (
              <li key={version.id} className="flex flex-col gap-1 py-3">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <Link
                    href={`/manuscritos/${manuscriptId}/versiones/${version.id}`}
                    className="ne-link font-medium"
                  >
                    Versión {version.number}
                  </Link>
                  <span className="ne-meta">{formatDate(version.created_at)}</span>
                </div>
                <p className="ne-meta">
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
        <h2 id="nueva-titulo" className="ne-section-title">
          Nueva versión
        </h2>
        <p className="ne-meta">
          El texto se guarda como borrador mientras escribes. Guardar como nueva versión crea una versión formal; las
          anteriores no cambian.
        </p>
        <form onSubmit={handleCreate} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1">
            <span className="ne-label">Partir de</span>
            <select
              value={baseId ?? ""}
              onChange={(event) => void handleBaseChange(Number(event.target.value))}
              
            >
              {versions?.map((version) => (
                <option key={version.id} value={version.id}>
                  Versión {version.number}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="ne-label">Contenido de la nueva versión</span>
            <textarea
              required
              rows={12}
              disabled={!ready}
              value={content}
              onChange={(event) => handleEdit(event.target.value)}
              className="ne-prose-field"
            />
          </label>
          <DraftStatus
            status={status}
            onRetry={() => void handleRetry()}
            onUseServer={handleUseServer}
            onKeepMine={() => void handleKeepMine()}
            onDownload={downloadCopy}
          />
          <label className="flex flex-col gap-1">
            <span className="ne-label">Nota (opcional)</span>
            <input
              maxLength={200}
              value={note}
              onChange={(event) => setNote(event.target.value)}
              
            />
          </label>
          <div>
            <button
              type="submit"
              disabled={saving || baseId === null || !ready}
              className="ne-button ne-button--primary"
            >
              {saving ? "Guardando…" : "Guardar como nueva versión"}
            </button>
          </div>
        </form>
        {formError ? (
          <p role="alert" className="ne-notice ne-notice--danger">
            {formError}
          </p>
        ) : null}
      </section>

      <RecoveryPoints points={points} error={pointsError} onRestore={(point) => void handleRestore(point)} onRefresh={refreshPoints} />
      {restoreError ? (
        <p role="alert" className="ne-notice ne-notice--danger">
          {restoreError}
        </p>
      ) : null}
    </main>
  );
}
