"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import DraftStatus from "@/components/DraftStatus";
import RecoveryPoints from "@/components/RecoveryPoints";
import {
  api,
  ApiError,
  formatDate,
  manuscriptOps,
  type DraftOut,
  type ManuscriptOps,
  type RecoveryPointSummary,
  type SceneWriting as Writing,
  type VersionSummary,
} from "@/lib/api";
import { DraftSaver, type SaveStatus } from "@/lib/draft-saver";
import { manuscriptPath, versionPath } from "@/lib/manuscript-paths";
import { useDirty } from "./UnsavedChanges";

type Props = { projectId: number; nodeId: number; sceneTitle: string };

function messageOf(reason: unknown, fallback: string): string {
  return reason instanceof ApiError ? reason.message : fallback;
}

/**
 * Escritura de una escena: el único editor del texto de la escena.
 *
 * El texto vive en su manuscrito propio y se guarda como borrador mientras se escribe (``DraftSaver``).
 * Desde aquí también se crean las versiones formales y se restauran los puntos de recuperación, sobre el mismo
 * borrador, así que nunca hay dos copias de trabajo. La página del manuscrito solo muestra el historial.
 */
export function SceneWriting({ projectId, nodeId, sceneTitle }: Props) {
  const router = useRouter();
  const [writing, setWriting] = useState<Writing | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [status, setStatus] = useState<SaveStatus | null>(null);
  const saverRef = useRef<DraftSaver | null>(null);
  // Operaciones del manuscrito de la escena, con el ámbito de su proyecto.
  const opsRef = useRef<ManuscriptOps | null>(null);
  const [versions, setVersions] = useState<VersionSummary[] | null>(null);
  const [baseId, setBaseId] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [points, setPoints] = useState<RecoveryPointSummary[] | null>(null);
  const [pointsError, setPointsError] = useState<string | null>(null);
  const [restoreError, setRestoreError] = useState<string | null>(null);

  // Cualquier cambio que aún no ha confirmado el servidor se avisa como en el resto de la planificación.
  // Al salir de la página, el texto pendiente se envía primero (ver UnsavedChanges).
  const flushPending = useCallback(async () => (saverRef.current ? saverRef.current.flush() : true), []);
  useDirty(`escritura:${nodeId}`, status !== null && status.kind !== "saved", flushPending);

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

  /** Carga el historial del manuscrito de la escena: versiones y puntos. No toca el borrador. */
  async function loadHistory(manuscriptId: number) {
    const ops = manuscriptOps(projectId, manuscriptId);
    opsRef.current = ops;
    try {
      const [list, pointList] = await Promise.all([ops.listVersions(), ops.listRecoveryPoints()]);
      setVersions(list);
      setBaseId(list.length > 0 ? list[list.length - 1].id : null);
      setPoints(pointList);
      setPointsError(null);
    } catch (reason) {
      setPointsError(messageOf(reason, "No se pudo cargar el historial."));
    }
  }

  /** Crea el guardado sobre un borrador ya cargado. Sustituye al anterior sin perder nada del servidor. */
  function attach(draft: DraftOut) {
    saverRef.current?.dispose();
    // Un guardado confirmado puede haber creado un punto de recuperación: la lista se refresca.
    let savingInFlight = false;
    saverRef.current = new DraftSaver(
      draft,
      (body) => api.saveSceneDraft(projectId, nodeId, body),
      (next) => {
        if (next.kind === "saving") savingInFlight = true;
        if (next.kind === "saved" && savingInFlight) {
          savingInFlight = false;
          refreshPoints();
        }
        setStatus(next);
      },
    );
    setContent(draft.content);
    setStatus({ kind: "saved", at: null });
  }

  useEffect(() => {
    let active = true;
    setLoadError(null);
    api.getSceneWriting(projectId, nodeId).then(
      (data) => {
        if (!active) return;
        setWriting(data);
        if (data.draft) attach(data.draft);
        if (data.manuscript_id !== null) void loadHistory(data.manuscript_id);
      },
      (reason: unknown) => {
        if (active) setLoadError(reason instanceof ApiError ? reason.message : "No se pudo cargar la escritura.");
      },
    );
    return () => {
      active = false;
      saverRef.current?.dispose();
      saverRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, nodeId]);

  useEffect(() => {
    function onBeforeUnload(event: BeforeUnloadEvent) {
      if (saverRef.current?.hasUnsavedChanges()) {
        event.preventDefault();
        event.returnValue = "";
      }
    }
    function onPageHide() {
      const body = saverRef.current?.keepaliveRequest();
      if (body) api.saveSceneDraftKeepalive(projectId, nodeId, body);
    }
    window.addEventListener("beforeunload", onBeforeUnload);
    window.addEventListener("pagehide", onPageHide);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
      window.removeEventListener("pagehide", onPageHide);
    };
  }, [projectId, nodeId]);

  async function start() {
    setStarting(true);
    setStartError(null);
    try {
      const created = await api.startSceneWriting(projectId, nodeId);
      setWriting(created);
      if (created.draft) attach(created.draft);
      if (created.manuscript_id !== null) void loadHistory(created.manuscript_id);
    } catch (reason) {
      // Un segundo clic o una segunda pestaña recibe la escritura existente: nunca se duplica.
      setStartError(reason instanceof ApiError ? reason.message : "No se pudo empezar la escritura. No se ha creado nada.");
    } finally {
      setStarting(false);
    }
  }

  function edit(value: string) {
    setContent(value);
    saverRef.current?.edit(value);
  }

  /** Cambia la versión de partida. Si el texto difiere, pide confirmación y lo guarda como punto antes de reemplazarlo. */
  async function handleBaseChange(nextId: number) {
    if (nextId === baseId || !saverRef.current || !opsRef.current) return;
    setFormError(null);
    let version;
    try {
      version = await opsRef.current.getVersion(nextId);
    } catch (reason) {
      setFormError(messageOf(reason, "No se pudo cargar la versión elegida."));
      return;
    }
    if (
      version.content !== content &&
      !window.confirm(
        "Se reemplazará el texto de la escena por el de la versión elegida. El texto anterior queda en los puntos de recuperación. ¿Continuar?",
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

  async function handleRestore(point: RecoveryPointSummary) {
    const saver = saverRef.current;
    if (!saver || !opsRef.current) return;
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
      const draft = await opsRef.current.restoreRecoveryPoint(point.id, saver.getRevision());
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
      router.push(versionPath(projectId, writing?.manuscript_id ?? 0, created.id));
    } catch (reason) {
      setFormError(messageOf(reason, "No se pudo crear la versión."));
      setSaving(false);
    }
  }

  function downloadCopy() {
    const safeName = sceneTitle.replace(/[^\p{L}\p{N} _-]+/gu, "_");
    const url = URL.createObjectURL(new Blob([content], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${safeName}.txt`;
    link.click();
    URL.revokeObjectURL(url);
  }

  if (loadError) {
    return (
      <p role="alert" className="ne-notice ne-notice--danger">
        {loadError}
      </p>
    );
  }
  if (writing === null) return <p className="ne-meta">Cargando escritura…</p>;

  if (writing.state === "sin_escritura" || writing.manuscript_id === null) {
    return (
      <div className="flex flex-col gap-3">
        <p className="ne-meta">
          Esta escena todavía no tiene texto. Empezar a escribirla crea su propio manuscrito vacío; no crea nada más.
        </p>
        <div>
          <button
            type="button"
            onClick={() => void start()}
            disabled={starting}
            className="ne-button ne-button--primary ne-button--small"
          >
            {starting ? "Empezando…" : "Empezar a escribir esta escena"}
          </button>
        </div>
        {startError ? (
          <p role="alert" className="ne-notice ne-notice--danger">
            {startError}
          </p>
        ) : null}
      </div>
    );
  }

  const ready = status !== null;
  const hasText = content.trim() !== "";

  return (
    <div className="flex flex-col gap-10">
      <div className="flex flex-col gap-4">
        <p className="text-sm">
          <span className="font-medium">{hasText ? "Con texto" : "Sin texto todavía"}</span>
          <span className="ne-meta"> · el texto se guarda como borrador mientras escribes.</span>
        </p>
        <label htmlFor="escena-texto" className="flex flex-col gap-1">
          <span className="ne-label">Texto de «{sceneTitle}»</span>
          <textarea
            id="escena-texto"
            rows={12}
            disabled={!ready}
            value={content}
            onChange={(event) => edit(event.target.value)}
            className="ne-prose-field"
          />
        </label>
        <DraftStatus
          status={status}
          onRetry={() => void saverRef.current?.retry()}
          onUseServer={() => {
            const text = saverRef.current?.useServerContent();
            if (text !== null && text !== undefined) setContent(text);
          }}
          onKeepMine={() => void saverRef.current?.keepMine()}
          onDownload={downloadCopy}
        />
      </div>

      <section aria-labelledby="escena-version-titulo" className="flex flex-col gap-4">
        <h2 id="escena-version-titulo" className="ne-section-title">
          Nueva versión
        </h2>
        <p className="ne-meta">
          Guardar como nueva versión crea una versión formal del texto actual. Las versiones anteriores no cambian.
        </p>
        <form onSubmit={handleCreate} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1">
            <span className="ne-label">Partir de</span>
            <select value={baseId ?? ""} onChange={(event) => void handleBaseChange(Number(event.target.value))}>
              {versions?.map((version) => (
                <option key={version.id} value={version.id}>
                  Versión {version.number}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="ne-label">Nota (opcional)</span>
            <input maxLength={200} value={note} onChange={(event) => setNote(event.target.value)} />
          </label>
          <div>
            <button type="submit" disabled={saving || baseId === null || !ready} className="ne-button ne-button--primary">
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

      <section aria-labelledby="escena-versiones-titulo" className="flex flex-col gap-3">
        <h2 id="escena-versiones-titulo" className="ne-section-title">
          Versiones de la escena
        </h2>
        {versions === null ? <p className="ne-meta">Cargando…</p> : null}
        <ol className="divide-y divide-[var(--color-muted)]/40">
          {versions?.map((version) => (
            <li key={version.id} className="flex flex-wrap items-baseline justify-between gap-2 py-2">
              <Link href={versionPath(projectId, writing.manuscript_id ?? 0, version.id)} className="ne-link font-medium">
                Versión {version.number}
              </Link>
              <span className="ne-meta">
                {version.char_count} caracteres · {formatDate(version.created_at)}
              </span>
            </li>
          ))}
        </ol>
      </section>

      <RecoveryPoints points={points} error={pointsError} onRestore={(point) => void handleRestore(point)} onRefresh={refreshPoints} />
      {restoreError ? (
        <p role="alert" className="ne-notice ne-notice--danger">
          {restoreError}
        </p>
      ) : null}

      <p className="ne-meta">
        <Link href={manuscriptPath(projectId, writing.manuscript_id)} className="ne-link">
          Versiones y puntos de recuperación
        </Link>
      </p>
    </div>
  );
}
