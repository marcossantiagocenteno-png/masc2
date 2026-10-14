import type { CanonState, ElementOrigin } from "@/lib/api";
import { CANON_HELP, CANON_LABELS } from "@/lib/planning";

const STYLE: Record<CanonState, string> = {
  provisional: "",
  propuesta_ia: "ne-badge--warn",
  canonico: "ne-badge--ok",
};

/** Estado de canon visible. El texto lleva el significado; el color solo lo refuerza. */
export function CanonBadge({ state, origin }: { state: CanonState; origin?: ElementOrigin }) {
  return (
    <span title={CANON_HELP[state]} className={`ne-badge ${STYLE[state]}`.trim()}>
      {CANON_LABELS[state]}
      {origin === "ia" ? <span className="font-normal">· origen: IA</span> : null}
    </span>
  );
}
