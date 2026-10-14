"use client";

import type { SaveStatus } from "@/lib/draft-saver";

type Props = {
  status: SaveStatus | null;
  onRetry: () => void;
  onUseServer: () => void;
  onKeepMine: () => void;
  onDownload: () => void;
};

/**
 * Estado visible del borrador. «Guardado» solo aparece tras una respuesta correcta del servidor.
 * Cada estado lleva icono y texto, no solo color. Ante un error o un conflicto, el texto del editor no se toca.
 */
export default function DraftStatus({ status, onRetry, onUseServer, onKeepMine, onDownload }: Props) {
  if (status === null) {
    return (
      <p role="status" className="ne-status">
        <span aria-hidden="true" className="ne-status__icon">…</span> Cargando borrador…
      </p>
    );
  }

  switch (status.kind) {
    case "saved":
      return (
        <p role="status" className="ne-status ne-status--ok">
          <span aria-hidden="true" className="ne-status__icon">✓</span>
          Borrador guardado{status.at ? ` a las ${status.at.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}` : ""}.
        </p>
      );
    case "pending":
      return (
        <p role="status" className="ne-status">
          <span aria-hidden="true" className="ne-status__icon">•</span> Cambios sin guardar.
        </p>
      );
    case "saving":
      return (
        <p role="status" className="ne-status">
          <span aria-hidden="true" className="ne-status__icon">…</span> Guardando…
        </p>
      );
    case "error":
      return (
        <div role="alert" className="ne-notice ne-notice--danger flex-col">
          <p>No guardado. {status.message} El texto sigue en el editor.</p>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={onRetry} className="ne-button ne-button--small">
              Reintentar
            </button>
            <button type="button" onClick={onDownload} className="ne-button ne-button--small">
              Descargar copia .txt
            </button>
          </div>
        </div>
      );
    case "conflict":
      return (
        <div role="alert" className="ne-notice ne-notice--danger flex-col">
          <p>
            Conflicto: este borrador se ha modificado en otra ventana. Tu texto no se ha perdido: está guardado en un
            punto de recuperación de tipo «conflicto».
          </p>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={onUseServer} className="ne-button ne-button--small">
              Usar la versión guardada
            </button>
            <button type="button" onClick={onKeepMine} className="ne-button ne-button--small">
              Mantener mi texto
            </button>
          </div>
        </div>
      );
  }
}
