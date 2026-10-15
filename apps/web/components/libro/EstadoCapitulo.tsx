import { BOOK_STATE_LABELS, type BookState } from "@/lib/book";

const CLASES: Record<BookState, string> = {
  vacio: "ne-badge",
  en_desarrollo: "ne-badge ne-badge--warn",
  terminado: "ne-badge ne-badge--ok",
};

/** Estado con su texto: el color solo lo refuerza. */
export function EstadoCapitulo({ state }: { state: BookState }) {
  return <span className={CLASES[state]}>{BOOK_STATE_LABELS[state]}</span>;
}
