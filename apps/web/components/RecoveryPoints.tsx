"use client";

import { formatDate, type RecoveryPointReason, type RecoveryPointSummary } from "@/lib/api";

const REASON_LABELS: Record<RecoveryPointReason, string> = {
  periodico: "Automático",
  significativo: "Cambio importante",
  conflicto: "Conflicto con otra ventana",
  antes_de_restaurar: "Antes de restaurar",
  antes_de_sobrescribir: "Antes de sobrescribir",
};

type Props = {
  points: RecoveryPointSummary[] | null;
  error: string | null;
  onRestore: (point: RecoveryPointSummary) => void;
  onRefresh: () => void;
};

/**
 * Puntos de recuperación del borrador. Son copias del texto de trabajo, no versiones:
 * restaurar crea un estado nuevo y no cambia las versiones guardadas.
 */
export default function RecoveryPoints({ points, error, onRestore, onRefresh }: Props) {
  return (
    <section aria-labelledby="recuperacion-titulo" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="recuperacion-titulo" className="text-xl font-medium">
          Puntos de recuperación
        </h2>
        <button
          type="button"
          onClick={onRefresh}
          className="rounded border border-[var(--color-muted)] px-3 py-1 text-sm hover:bg-[var(--color-muted)]/20"
        >
          Actualizar lista
        </button>
      </div>
      <p className="text-sm text-[var(--color-muted)]">
        Copias del borrador hechas automáticamente o en un momento delicado. No son versiones: no se publican ni
        cambian las versiones guardadas. Restaurar guarda antes el texto actual como punto nuevo.
      </p>
      {error ? (
        <p role="alert" className="text-red-700">
          {error}
        </p>
      ) : null}
      {points === null ? <p className="text-[var(--color-muted)]">Cargando…</p> : null}
      {points?.length === 0 ? <p className="text-[var(--color-muted)]">Todavía no hay puntos.</p> : null}
      <ol className="divide-y divide-[var(--color-muted)]/40">
        {points?.map((point) => (
          <li key={point.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
            <div className="flex flex-col gap-1">
              <span className="font-medium">{REASON_LABELS[point.reason]}</span>
              <span className="text-sm text-[var(--color-muted)]">
                {formatDate(point.created_at)} · {point.char_count} caracteres
              </span>
            </div>
            <button
              type="button"
              aria-label={`Restaurar punto de ${formatDate(point.created_at)}`}
              onClick={() => onRestore(point)}
              className="rounded border border-[var(--color-muted)] px-3 py-1 text-sm hover:bg-[var(--color-muted)]/20"
            >
              Restaurar
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}
