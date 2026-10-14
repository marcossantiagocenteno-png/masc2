"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import DraftStatus from "@/components/DraftStatus";
import { api, ApiError, type DraftOut, type SceneWriting as Writing } from "@/lib/api";
import { DraftSaver, type SaveStatus } from "@/lib/draft-saver";
import { useDirty } from "./UnsavedChanges";

type Props = { projectId: number; nodeId: number; sceneTitle: string };

/**
 * Escritura de una escena. El texto vive en su manuscrito propio: el editor usa el mismo guardado
 * (``DraftSaver``) y el mismo estado visible (``DraftStatus``) que el manuscrito. Crear una versión formal
 * o ver los puntos de recuperación sigue siendo una acción de la página del manuscrito.
 */
export function SceneWriting({ projectId, nodeId, sceneTitle }: Props) {
  const [writing, setWriting] = useState<Writing | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [status, setStatus] = useState<SaveStatus | null>(null);
  const saverRef = useRef<DraftSaver | null>(null);

  // Cualquier cambio que aún no ha confirmado el servidor se avisa como en el resto de la planificación.
  // Al salir de la página, el texto pendiente se envía primero (ver UnsavedChanges).
  const flushPending = useCallback(async () => (saverRef.current ? saverRef.current.flush() : true), []);
  useDirty(`escritura:${nodeId}`, status !== null && status.kind !== "saved", flushPending);

  /** Crea el guardado sobre un borrador ya cargado. Sustituye al anterior sin perder nada del servidor. */
  function attach(draft: DraftOut) {
    saverRef.current?.dispose();
    saverRef.current = new DraftSaver(
      draft,
      (body) => api.saveSceneDraft(projectId, nodeId, body),
      (next) => setStatus(next),
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
      <p className="ne-meta">
        <Link href={`/manuscritos/${writing.manuscript_id}`} className="ne-link">
          Versiones y puntos de recuperación
        </Link>{" "}
        · crear una versión formal es una acción aparte, en esa página.
      </p>
    </div>
  );
}
