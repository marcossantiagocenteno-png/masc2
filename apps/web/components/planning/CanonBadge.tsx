import type { CanonState, ElementOrigin } from "@/lib/api";
import { CANON_HELP, CANON_LABELS } from "@/lib/planning";

const STYLE: Record<CanonState, string> = {
  provisional: "border-[var(--color-muted)] text-[var(--color-muted)]",
  propuesta_ia: "border-dashed border-amber-700 text-amber-800",
  canonico: "border-emerald-800 bg-emerald-50 text-emerald-900 font-medium",
};

/** Estado de canon visible. El texto lleva el significado; el color solo lo refuerza. */
export function CanonBadge({ state, origin }: { state: CanonState; origin?: ElementOrigin }) {
  return (
    <span
      title={CANON_HELP[state]}
      className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs ${STYLE[state]}`}
    >
      {CANON_LABELS[state]}
      {origin === "ia" ? <span className="text-[var(--color-muted)]">· origen: IA</span> : null}
    </span>
  );
}
