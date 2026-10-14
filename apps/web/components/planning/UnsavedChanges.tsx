"use client";

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, type MouseEvent, type ReactNode } from "react";

/** Envía los cambios pendientes al servidor. Resuelve ``true`` solo si el servidor los ha confirmado. */
export type FlushFn = () => Promise<boolean>;

type UnsavedApi = {
  setDirty: (key: string, dirty: boolean, flush?: FlushFn) => void;
  isDirty: (key: string) => boolean;
};

const UnsavedContext = createContext<UnsavedApi>({ setDirty: () => undefined, isDirty: () => false });

/**
 * Registro de formularios con cambios sin guardar dentro de un espacio de trabajo.
 * Sirve para avisar antes de navegar (enlaces internos, cierre de la pestaña) y antes de
 * cambiar de elemento en una lista.
 */
export function UnsavedChangesProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const dirtyKeys = useRef(new Set<string>());
  const flushers = useRef(new Map<string, FlushFn>());

  const setDirty = useCallback((key: string, dirty: boolean, flush?: FlushFn) => {
    if (dirty) {
      dirtyKeys.current.add(key);
      if (flush) flushers.current.set(key, flush);
    } else {
      dirtyKeys.current.delete(key);
      flushers.current.delete(key);
    }
  }, []);
  const isDirty = useCallback((key: string) => dirtyKeys.current.has(key), []);

  useEffect(() => {
    function onBeforeUnload(event: BeforeUnloadEvent) {
      if (dirtyKeys.current.size > 0) {
        event.preventDefault();
        event.returnValue = "";
      }
    }
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, []);

  /**
   * Antes de salir, los cambios que saben guardarse se envían primero. Solo si el servidor no los confirma
   * se pregunta, y el texto no se descarta en silencio. Los formularios sin envío previo siguen avisando.
   */
  async function flushPending(): Promise<boolean> {
    for (const key of dirtyKeys.current) {
      const flush = flushers.current.get(key);
      if (!flush || !(await flush())) return false;
    }
    return true;
  }

  async function guardNavigation(event: MouseEvent<HTMLDivElement>) {
    if (dirtyKeys.current.size === 0) return;
    // Un clic con modificador abre otra pestaña: no sale de la página, así que no hay nada que proteger.
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
    const anchor = (event.target as HTMLElement).closest("a");
    const href = anchor?.getAttribute("href");
    if (!anchor || !href || !href.startsWith("/")) return;
    event.preventDefault();
    const sent = await flushPending();
    if (!sent && !window.confirm("Hay cambios sin guardar. Si sales ahora, se perderán. ¿Salir de todos modos?")) {
      return;
    }
    // Al salir, los formularios se desmontan y dejan de estar registrados como pendientes.
    dirtyKeys.current.clear();
    flushers.current.clear();
    router.push(href);
  }

  const value = useMemo(() => ({ setDirty, isDirty }), [setDirty, isDirty]);
  return (
    <UnsavedContext.Provider value={value}>
      <div onClickCapture={guardNavigation}>{children}</div>
    </UnsavedContext.Provider>
  );
}

/**
 * Marca un formulario como pendiente mientras ``dirty`` sea verdadero. Si se indica ``flush``, al salir de la
 * página se intenta guardar antes de avisar. Debe ser estable (useCallback) para no re-registrarse en cada render.
 */
export function useDirty(key: string, dirty: boolean, flush?: FlushFn) {
  const { setDirty } = useContext(UnsavedContext);
  useEffect(() => {
    setDirty(key, dirty, flush);
    return () => setDirty(key, false);
  }, [key, dirty, flush, setDirty]);
}

export function useUnsavedChanges() {
  return useContext(UnsavedContext);
}
