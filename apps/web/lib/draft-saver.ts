/**
 * Guardado del borrador en el servidor, sin React.
 *
 * Reglas:
 * - Una sola escritura en vuelo: las demás esperan en cola y leen la revisión que
 *   dejó la anterior. Así una respuesta no puede llegar fuera de orden.
 * - Cada escritura indica la revisión que conoce el cliente. Si el servidor responde
 *   409, el estado pasa a «conflicto» y no se envía nada más hasta resolverlo.
 * - «Guardado» solo se muestra tras una respuesta correcta del servidor.
 * - Si falla, el texto se conserva en el editor y se puede reintentar.
 * - El anti-rebote guarda tras una pausa, y como máximo cada ``MAX_WAIT_MS``.
 */

import { ApiError, type DraftOut, type DraftSaveBody } from "@/lib/api";

export const DEBOUNCE_MS = 1500;
export const MAX_WAIT_MS = 10_000;
/** Límite de tamaño del cuerpo para el guardado con keepalive en pagehide. */
export const KEEPALIVE_LIMIT_BYTES = 64 * 1024;

export type SaveStatus =
  | { kind: "saved"; at: Date | null }
  | { kind: "pending" }
  | { kind: "saving" }
  | { kind: "error"; message: string }
  | { kind: "conflict"; currentRevision: number; currentContent: string };

export type SaveFn = (body: DraftSaveBody) => Promise<DraftOut>;

export type Scheduler = {
  setTimeout: (callback: () => void, ms: number) => unknown;
  clearTimeout: (handle: unknown) => void;
  now: () => number;
};

const browserScheduler: Scheduler = {
  setTimeout: (callback, ms) => window.setTimeout(callback, ms),
  clearTimeout: (handle) => window.clearTimeout(handle as number),
  now: () => Date.now(),
};

const NETWORK_MESSAGE = "No hay conexión con el servidor. El texto sigue en pantalla.";

function messageFor(reason: unknown): string {
  if (reason instanceof ApiError) {
    return reason.status === 0 ? NETWORK_MESSAGE : reason.message;
  }
  return NETWORK_MESSAGE;
}

export class DraftSaver {
  private revision: number;
  private savedContent: string;
  private desired: string;
  private keepPrevious = false;
  private inFlight = false;
  private timer: unknown = null;
  private firstPendingAt: number | null = null;
  private lastSavedAt: Date | null = null;
  // Operaciones de guardado no terminadas. Si es 0, la siguiente arranca en el acto.
  private pending = 0;
  private chain: Promise<boolean> = Promise.resolve(true);
  private status: SaveStatus = { kind: "saved", at: null };
  private readonly save: SaveFn;
  private readonly onStatus: (status: SaveStatus) => void;
  private readonly scheduler: Scheduler;

  constructor(
    draft: Pick<DraftOut, "revision" | "content">,
    save: SaveFn,
    onStatus: (status: SaveStatus) => void,
    scheduler: Scheduler = browserScheduler,
  ) {
    this.revision = draft.revision;
    this.savedContent = draft.content;
    this.desired = draft.content;
    this.save = save;
    this.onStatus = onStatus;
    this.scheduler = scheduler;
  }

  /** Texto que el autor ha escrito, guardado o no. */
  edit(content: string): void {
    this.desired = content;
    if (this.status.kind === "conflict") return; // Nada se envía hasta resolver el conflicto.
    if (content === this.savedContent && !this.keepPrevious) {
      this.firstPendingAt = null;
      this.clearTimer();
      if (!this.inFlight) this.setStatus({ kind: "saved", at: this.lastSavedAt });
      return;
    }
    if (!this.inFlight) this.setStatus({ kind: "pending" });
    this.schedule();
  }

  /** Envía ya lo pendiente. Resuelve ``true`` si el servidor confirma el estado actual. */
  flush(): Promise<boolean> {
    this.clearTimer();
    const run = this.pending === 0 ? this.sendLatest() : this.chain.then(() => this.sendLatest());
    this.pending += 1;
    this.chain = run.finally(() => {
      this.pending -= 1;
    });
    return this.chain;
  }

  /** Reintento tras un error. Usa el texto que sigue en el editor. */
  retry(): Promise<boolean> {
    return this.flush();
  }

  /**
   * Sustituye el texto por otro (por ejemplo, al cambiar la versión de partida).
   * Antes guarda lo pendiente. El texto anterior queda en un punto ``antes_de_sobrescribir``.
   */
  async replace(content: string): Promise<boolean> {
    if (this.desired !== this.savedContent) {
      const saved = await this.flush();
      if (!saved || this.desired !== this.savedContent) return false;
    }
    this.desired = content;
    this.keepPrevious = true;
    return this.flush();
  }

  /** Tras una restauración o una carga nueva: el servidor es la fuente de verdad. */
  reset(draft: Pick<DraftOut, "revision" | "content">): void {
    this.clearTimer();
    this.revision = draft.revision;
    this.savedContent = draft.content;
    this.desired = draft.content;
    this.keepPrevious = false;
    this.firstPendingAt = null;
    this.lastSavedAt = new Date(this.scheduler.now());
    this.setStatus({ kind: "saved", at: this.lastSavedAt });
  }

  /** Conflicto: adopta el borrador guardado por la otra ventana. Devuelve su texto. */
  useServerContent(): string | null {
    if (this.status.kind !== "conflict") return null;
    const { currentRevision, currentContent } = this.status;
    this.revision = currentRevision;
    this.savedContent = currentContent;
    this.desired = currentContent;
    this.keepPrevious = false;
    this.lastSavedAt = new Date(this.scheduler.now());
    this.setStatus({ kind: "saved", at: this.lastSavedAt });
    return currentContent;
  }

  /**
   * Conflicto: el texto del editor sustituye al guardado. Lo guardado antes queda en un
   * punto ``antes_de_sobrescribir``, así que no se pierde.
   */
  keepMine(): Promise<boolean> {
    if (this.status.kind !== "conflict") return Promise.resolve(false);
    this.revision = this.status.currentRevision;
    this.keepPrevious = true;
    this.setStatus({ kind: "pending" });
    return this.flush();
  }

  hasUnsavedChanges(): boolean {
    return this.status.kind !== "saved";
  }

  getRevision(): number {
    return this.revision;
  }

  /** Cuerpo para el guardado de pagehide, o ``null`` si no hay nada que enviar o no cabe. */
  keepaliveRequest(): DraftSaveBody | null {
    if (this.status.kind === "conflict" || this.desired === this.savedContent) return null;
    const body: DraftSaveBody = { content: this.desired, base_revision: this.revision, keep_previous: false };
    return new TextEncoder().encode(JSON.stringify(body)).length <= KEEPALIVE_LIMIT_BYTES ? body : null;
  }

  dispose(): void {
    this.clearTimer();
  }

  private async sendLatest(): Promise<boolean> {
    if (this.status.kind === "conflict") return false;
    if (this.desired === this.savedContent && !this.keepPrevious) {
      this.firstPendingAt = null;
      if (!this.inFlight) this.setStatus({ kind: "saved", at: this.lastSavedAt });
      return true;
    }

    const content = this.desired;
    const keep = this.keepPrevious;
    this.keepPrevious = false;
    this.inFlight = true;
    this.setStatus({ kind: "saving" });
    try {
      const draft = await this.save({ content, base_revision: this.revision, keep_previous: keep });
      this.inFlight = false;
      // Una respuesta que no avanza la revisión es antigua y no cambia el estado guardado.
      if (draft.revision > this.revision) {
        this.revision = draft.revision;
        this.savedContent = content;
        this.lastSavedAt = new Date(this.scheduler.now());
      }
      if (this.desired === this.savedContent) {
        this.firstPendingAt = null;
        this.setStatus({ kind: "saved", at: this.lastSavedAt });
      } else {
        this.setStatus({ kind: "pending" });
        this.schedule();
      }
      return true;
    } catch (reason) {
      this.inFlight = false;
      this.keepPrevious = keep || this.keepPrevious;
      if (reason instanceof ApiError && reason.status === 409 && reason.payload) {
        this.clearTimer();
        this.setStatus({
          kind: "conflict",
          currentRevision: Number(reason.payload.current_revision),
          currentContent: String(reason.payload.current_content ?? ""),
        });
        return false;
      }
      this.clearTimer();
      this.setStatus({ kind: "error", message: messageFor(reason) });
      return false;
    }
  }

  private schedule(): void {
    const now = this.scheduler.now();
    if (this.firstPendingAt === null) this.firstPendingAt = now;
    const elapsed = now - this.firstPendingAt;
    const delay = Math.max(0, Math.min(DEBOUNCE_MS, MAX_WAIT_MS - elapsed));
    this.clearTimer();
    this.timer = this.scheduler.setTimeout(() => {
      this.timer = null;
      void this.flush();
    }, delay);
  }

  private clearTimer(): void {
    if (this.timer !== null) {
      this.scheduler.clearTimeout(this.timer);
      this.timer = null;
    }
  }

  private setStatus(status: SaveStatus): void {
    this.status = status;
    this.onStatus(status);
  }
}
