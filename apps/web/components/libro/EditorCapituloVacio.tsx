"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useDirty } from "@/components/planning/UnsavedChanges";

type Props = {
  projectId: number;
  chapterId: number;
  onDone: () => void;
};

/**
 * Editor de un capítulo sin escenas. Escribir no crea nada en el servidor. Solo «Empezar a escribir» crea la primera
 * escena y su manuscrito, con el texto escrito como primer borrador. Si el servidor falla después de crear la escena,
 * el texto se conserva en pantalla y el botón reintenta solo el guardado.
 */
export function EditorCapituloVacio({ projectId, chapterId, onDone }: Props) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sceneId, setSceneId] = useState<number | null>(null);
  useDirty(`libro:${chapterId}`, text.trim().length > 0);

  async function start() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      let nodeId = sceneId;
      if (nodeId === null) {
        const scene = await api.createStructureNode(projectId, { kind: "escena", parent_id: chapterId });
        nodeId = scene.id;
        setSceneId(nodeId);
      }
      // Idempotente: si la escritura ya existe, el servidor devuelve la existente.
      const writing = await api.startSceneWriting(projectId, nodeId);
      if (text.trim().length > 0) {
        if (!writing.draft) throw new ApiError("La escena no tiene borrador.", 500);
        await api.saveSceneDraft(projectId, nodeId, {
          content: text,
          base_revision: writing.draft.revision,
          keep_previous: false,
        });
      }
      onDone();
    } catch (reason) {
      const message = reason instanceof ApiError ? reason.message : "No se pudo completar la operación.";
      setError(
        sceneId === null
          ? `No se ha creado nada. ${message}`
          : `La escena se ha creado, pero el texto no se ha guardado. ${message} Tu texto sigue aquí: reintenta el guardado.`,
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="escribir-capitulo" className="flex flex-col gap-4">
      <h2 id="escribir-capitulo" className="ne-section-title">
        Escribir este capítulo
      </h2>
      <p className="ne-meta">
        Este capítulo todavía no tiene escenas ni manuscrito. Al pulsar «Empezar a escribir» se crea su primera escena y su
        manuscrito con el texto escrito. Hasta entonces no se crea nada.
      </p>
      <label className="flex flex-col gap-1">
        <span className="ne-label">Texto del capítulo</span>
        <textarea
          rows={12}
          value={text}
          disabled={busy}
          onChange={(event) => setText(event.target.value)}
          className="ne-prose-field"
        />
      </label>
      <div>
        <button type="button" onClick={() => void start()} disabled={busy} className="ne-button ne-button--primary">
          {busy ? "Guardando…" : sceneId === null ? "Empezar a escribir" : "Reintentar guardar el texto"}
        </button>
      </div>
      {error ? (
        <p role="alert" className="ne-notice ne-notice--danger">
          {error}
        </p>
      ) : null}
    </section>
  );
}
