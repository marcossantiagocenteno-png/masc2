import { expect, test } from "@playwright/test";
import { ApiError, type DraftOut, type DraftSaveBody } from "../../lib/api";
import { DraftSaver, DEBOUNCE_MS, KEEPALIVE_LIMIT_BYTES, MAX_WAIT_MS, type SaveStatus } from "../../lib/draft-saver";

/**
 * Pruebas deterministas del guardado: sin navegador, sin esperas reales.
 * El reloj y los temporizadores se controlan a mano; las respuestas del servidor
 * se resuelven en el orden que cada prueba necesita.
 */

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function fakeScheduler() {
  let now = 0;
  let nextId = 1;
  const timers = new Map<number, { callback: () => void; due: number; ms: number }>();
  return {
    scheduler: {
      setTimeout(callback: () => void, ms: number) {
        const id = nextId++;
        timers.set(id, { callback, due: now + ms, ms });
        return id;
      },
      clearTimeout(handle: unknown) {
        timers.delete(handle as number);
      },
      now: () => now,
    },
    advance(ms: number) {
      now += ms;
      for (const [id, timer] of [...timers.entries()].sort((a, b) => a[1].due - b[1].due)) {
        if (timer.due <= now && timers.has(id)) {
          timers.delete(id);
          timer.callback();
        }
      }
    },
    lastDelay(): number | undefined {
      return [...timers.values()].at(-1)?.ms;
    },
    pending(): number {
      return timers.size;
    },
  };
}

function draftOut(revision: number, content: string): DraftOut {
  return {
    manuscript_id: 1,
    revision,
    content,
    char_count: content.length,
    sha256: "x",
    base_version_id: null,
    created_at: "2026-01-01T00:00:00",
    updated_at: "2026-01-01T00:00:00",
  };
}

function conflict(currentRevision: number, currentContent: string): ApiError {
  return new ApiError("conflicto", 409, { current_revision: currentRevision, current_content: currentContent });
}

function setup(initialContent = "A", revision = 1) {
  const calls: DraftSaveBody[] = [];
  const replies: Array<ReturnType<typeof deferred<DraftOut>>> = [];
  const statuses: SaveStatus[] = [];
  const clock = fakeScheduler();
  const save = (body: DraftSaveBody) => {
    calls.push(body);
    const reply = deferred<DraftOut>();
    replies.push(reply);
    return reply.promise;
  };
  const saver = new DraftSaver({ revision, content: initialContent }, save, (s) => statuses.push(s), clock.scheduler);
  return { saver, calls, replies, statuses, clock };
}

test("un guardado no se envía en paralelo: el siguiente parte de la revisión que devolvió el anterior", async () => {
  const { saver, calls, replies } = setup("A", 1);
  saver.edit("B");
  const primero = saver.flush();
  saver.edit("C");
  const segundo = saver.flush();

  expect(calls).toHaveLength(1);
  expect(calls[0]).toEqual({ content: "B", base_revision: 1, keep_previous: false });

  replies[0].resolve(draftOut(2, "B"));
  await primero;
  expect(calls).toHaveLength(2);
  expect(calls[1]).toEqual({ content: "C", base_revision: 2, keep_previous: false });

  replies[1].resolve(draftOut(3, "C"));
  expect(await segundo).toBe(true);
  expect(saver.getRevision()).toBe(3);
  expect(saver.hasUnsavedChanges()).toBe(false);
});

test("«guardado» solo aparece tras la respuesta del servidor, nunca antes", async () => {
  const { saver, statuses, replies } = setup("A", 1);
  saver.edit("B");
  const guardado = saver.flush();
  expect(statuses.at(-1)).toEqual({ kind: "saving" });
  expect(saver.hasUnsavedChanges()).toBe(true);

  replies[0].resolve(draftOut(2, "B"));
  await guardado;
  expect(statuses.at(-1)?.kind).toBe("saved");
});

test("un 409 pasa a conflicto, conserva el texto y no envía nada más hasta resolverlo", async () => {
  const { saver, calls, replies, statuses } = setup("A", 1);
  saver.edit("Mío");
  const intento = saver.flush();
  replies[0].reject(conflict(2, "Servidor"));
  expect(await intento).toBe(false);

  expect(statuses.at(-1)).toEqual({ kind: "conflict", currentRevision: 2, currentContent: "Servidor" });
  saver.edit("Mío, más");
  await saver.flush();
  expect(calls).toHaveLength(1);
});

test("resolver con «Mantener mi texto» envía la revisión actual con keep_previous", async () => {
  const { saver, calls, replies } = setup("A", 1);
  saver.edit("Mío");
  const intento = saver.flush();
  replies[0].reject(conflict(2, "Servidor"));
  await intento;

  const resolucion = saver.keepMine();
  expect(calls[1]).toEqual({ content: "Mío", base_revision: 2, keep_previous: true });
  replies[1].resolve(draftOut(3, "Mío"));
  expect(await resolucion).toBe(true);
  expect(saver.hasUnsavedChanges()).toBe(false);
});

test("resolver con «Usar la versión guardada» adopta el servidor y no envía nada", async () => {
  const { saver, calls, replies } = setup("A", 1);
  saver.edit("Mío");
  const intento = saver.flush();
  replies[0].reject(conflict(2, "Servidor"));
  await intento;

  expect(saver.useServerContent()).toBe("Servidor");
  expect(saver.hasUnsavedChanges()).toBe(false);
  expect(calls).toHaveLength(1);
});

test("un error de red conserva el texto y el reintento lo envía de nuevo", async () => {
  const { saver, calls, replies, statuses } = setup("A", 1);
  saver.edit("Texto que no debe perderse");
  const intento = saver.flush();
  replies[0].reject(new ApiError("No se pudo conectar", 0));
  expect(await intento).toBe(false);

  const error = statuses.at(-1);
  expect(error?.kind).toBe("error");
  expect(saver.hasUnsavedChanges()).toBe(true);

  const reintento = saver.retry();
  expect(calls[1]).toEqual({ content: "Texto que no debe perderse", base_revision: 1, keep_previous: false });
  replies[1].resolve(draftOut(2, "Texto que no debe perderse"));
  expect(await reintento).toBe(true);
  expect(saver.hasUnsavedChanges()).toBe(false);
});

test("el anti-rebote agrupa las pulsaciones en un solo guardado", async () => {
  const { saver, calls, replies, clock } = setup("A", 1);
  saver.edit("B");
  clock.advance(500);
  saver.edit("BC");
  clock.advance(500);
  saver.edit("BCD");
  expect(calls).toHaveLength(0);

  clock.advance(DEBOUNCE_MS);
  const control = saver.flush();
  replies[0].resolve(draftOut(2, "BCD"));
  await control;
  expect(calls).toHaveLength(1);
  expect(calls[0].content).toBe("BCD");
});

test("sin pausas, el guardado llega antes de MAX_WAIT_MS desde el primer cambio pendiente", async () => {
  const { saver, clock } = setup("A", 1);
  for (let elapsed = 0; elapsed < MAX_WAIT_MS; elapsed += 1000) {
    saver.edit(`A${elapsed}`);
    clock.advance(1000);
  }
  // Tras 10 s de escritura continua, el siguiente temporizador vence de inmediato.
  saver.edit("A-final");
  expect(clock.lastDelay()).toBe(0);
});

test("reset tras restaurar adopta la revisión del servidor y deja de estar pendiente", async () => {
  const { saver, statuses } = setup("A", 1);
  saver.edit("B");
  saver.reset(draftOut(7, "Restaurado"));
  expect(saver.getRevision()).toBe(7);
  expect(saver.hasUnsavedChanges()).toBe(false);
  expect(statuses.at(-1)?.kind).toBe("saved");
});

test("replace guarda lo pendiente antes de sustituir y marca el texto anterior para conservarlo", async () => {
  const { saver, calls, replies } = setup("A", 1);
  saver.edit("B, sin guardar");
  const reemplazo = saver.replace("Texto de la versión 1");

  replies[0].resolve(draftOut(2, "B, sin guardar"));
  // La escritura de reemplazo sale cuando termina la anterior: basta con ceder turnos de cola,
  // con un límite fijo para que un fallo no se quede colgado.
  for (let turn = 0; turn < 20 && calls.length < 2; turn++) await Promise.resolve();
  expect(calls[0]).toEqual({ content: "B, sin guardar", base_revision: 1, keep_previous: false });
  expect(calls[1]).toEqual({ content: "Texto de la versión 1", base_revision: 2, keep_previous: true });

  replies[1].resolve(draftOut(3, "Texto de la versión 1"));
  expect(await reemplazo).toBe(true);
});

test("replace no sustituye nada si no pudo guardar lo pendiente", async () => {
  const { saver, calls, replies, statuses } = setup("A", 1);
  saver.edit("B, sin guardar");
  const reemplazo = saver.replace("Versión 1");
  replies[0].reject(new ApiError("Error del servidor", 500));
  expect(await reemplazo).toBe(false);
  expect(calls).toHaveLength(1);
  expect(statuses.at(-1)?.kind).toBe("error");
});

test("keepaliveRequest no envía nada sin cambios y descarta cuerpos por encima de 64 KB", async () => {
  const { saver } = setup("A", 1);
  expect(saver.keepaliveRequest()).toBeNull();
  saver.edit("x".repeat(KEEPALIVE_LIMIT_BYTES + 1));
  expect(saver.keepaliveRequest()).toBeNull();
  saver.edit("corto");
  expect(saver.keepaliveRequest()).toEqual({ content: "corto", base_revision: 1, keep_previous: false });
});
