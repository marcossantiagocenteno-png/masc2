"use client";

import { useState, type ReactNode } from "react";

type Props = {
  message: ReactNode;
  confirmLabel: string;
  /** Si se indica, la acción exige marcar esta casilla antes de confirmar. */
  checkboxLabel?: string;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

/** Confirmación explícita y en línea: explica qué cambia y no se acepta por defecto. */
export function ConfirmPanel({ message, confirmLabel, checkboxLabel, busy = false, onConfirm, onCancel }: Props) {
  const [checked, setChecked] = useState(false);
  const blocked = busy || (checkboxLabel !== undefined && !checked);
  return (
    <div role="group" aria-label="Confirmación" className="flex flex-col gap-3 rounded border border-[var(--color-ink)] p-4">
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
          className="rounded bg-[var(--color-ink)] px-3 py-1.5 text-sm text-[var(--color-paper)] disabled:opacity-50"
        >
          {busy ? "Guardando…" : confirmLabel}
        </button>
        <button type="button" onClick={onCancel} disabled={busy} className="rounded border border-[var(--color-muted)] px-3 py-1.5 text-sm">
          Cancelar
        </button>
      </div>
    </div>
  );
}
