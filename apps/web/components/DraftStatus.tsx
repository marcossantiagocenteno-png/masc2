"use client";

import type { SaveStatus } from "@/lib/draft-saver";

type Props = {
  status: SaveStatus | null;
  onRetry: () => void;
  onUseServer: () => void;
  onKeepMine: () => void;
  onDownload: () => void;
};

const buttonClass =
  "rounded border border-[var(--color-muted)] px-3 py-1 text-sm hover:bg-[var(--color-muted)]/20 disabled:opacity-50";

/**
 * Estado visible del borrador. «Guardado» solo aparece tras una respuesta correcta del
 * servidor. Ante un error o un conflicto, el texto del editor no se toca.
 */
export default function DraftStatus({ status, onRetry, onUseServer, onKeepMine, onDownload }: Props) {
  if (status === null) {
    return (
      <p role="status" className="text-sm text-[var(--color-muted)]">
        Cargando borrador…
      </p>
    );
  }

  switch (status.kind) {
    case "saved":
      return (
        <p role="status" className="text-sm text-[var(--color-muted)]">
          Borrador guardado{status.at ? ` a las ${status.at.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}` : ""}.
        </p>
      );
    case "pending":
      return (
        <p role="status" className="text-sm text-[var(--color-muted)]">
          Cambios sin guardar.
        </p>
      );
    case "saving":
      return (
        <p role="status" className="text-sm text-[var(--color-muted)]">
          Guardando…
        </p>
      );
    case "error":
      return (
        <div role="alert" className="flex flex-col gap-2 text-sm text-red-700">
          <p>No guardado. {status.message} El texto sigue en el editor.</p>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={onRetry} className={buttonClass}>
              Reintentar
            </button>
            <button type="button" onClick={onDownload} className={buttonClass}>
              Descargar copia .txt
            </button>
          </div>
        </div>
      );
    case "conflict":
      return (
        <div role="alert" className="flex flex-col gap-2 text-sm text-red-700">
          <p>
            Conflicto: este borrador se ha modificado en otra ventana. Tu texto no se ha perdido: está guardado en un
            punto de recuperación de tipo «conflicto».
          </p>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={onUseServer} className={buttonClass}>
              Usar la versión guardada
            </button>
            <button type="button" onClick={onKeepMine} className={buttonClass}>
              Mantener mi texto
            </button>
          </div>
        </div>
      );
  }
}
