"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

type Props = {
  message: ReactNode;
  confirmLabel: string;
  /** Si se indica, la acción exige marcar esta casilla antes de confirmar. */
  checkboxLabel?: string;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

/**
 * Confirmación explícita y en línea: explica qué cambia y no se acepta por defecto.
 * Al abrirse enfoca su primer control; al cerrarse (cancelar o confirmar) devuelve el foco al elemento
 * que la abrió, si sigue en la página.
 */
export function ConfirmPanel({ message, confirmLabel, checkboxLabel, busy = false, onConfirm, onCancel }: Props) {
  const [checked, setChecked] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const blocked = busy || (checkboxLabel !== undefined && !checked);

  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    panelRef.current?.querySelector<HTMLElement>("input, button:not([disabled])")?.focus();
    return () => {
      if (opener && opener.isConnected) opener.focus();
    };
  }, []);

  return (
    <div ref={panelRef} role="group" aria-label="Confirmación" className="ne-panel flex flex-col gap-3">
      <div className="text-sm">{message}</div>
      {checkboxLabel ? (
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" checked={checked} onChange={(event) => setChecked(event.target.checked)} />
          <span>{checkboxLabel}</span>
        </label>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onConfirm}
          disabled={blocked}
          className="ne-button ne-button--primary ne-button--small"
        >
          {busy ? "Guardando…" : confirmLabel}
        </button>
        <button type="button" onClick={onCancel} disabled={busy} className="ne-button ne-button--small">
          Cancelar
        </button>
      </div>
    </div>
  );
}
