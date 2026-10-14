"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, type MouseEvent, type ReactNode } from "react";

type UnsavedApi = {
  setDirty: (key: string, dirty: boolean) => void;
  isDirty: (key: string) => boolean;
};

const UnsavedContext = createContext<UnsavedApi>({ setDirty: () => undefined, isDirty: () => false });

/**
 * Registro de formularios con cambios sin guardar dentro de un espacio de trabajo.
 * Sirve para avisar antes de navegar (enlaces internos, cierre de la pestaña) y antes de
 * cambiar de elemento en una lista.
 */
export function UnsavedChangesProvider({ children }: { children: ReactNode }) {
  const dirtyKeys = useRef(new Set<string>());

  const setDirty = useCallback((key: string, dirty: boolean) => {
    if (dirty) dirtyKeys.current.add(key);
    else dirtyKeys.current.delete(key);
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

  function guardNavigation(event: MouseEvent<HTMLDivElement>) {
    if (dirtyKeys.current.size === 0) return;
    const anchor = (event.target as HTMLElement).closest("a");
    const href = anchor?.getAttribute("href");
    if (!anchor || !href || !href.startsWith("/")) return;
    if (!window.confirm("Hay cambios sin guardar. Si sales ahora, se perderán. ¿Salir de todos modos?")) {
      event.preventDefault();
      return;
    }
    // Al salir, los formularios se desmontan y dejan de estar registrados como pendientes.
    dirtyKeys.current.clear();
  }

  const value = useMemo(() => ({ setDirty, isDirty }), [setDirty, isDirty]);
  return (
    <UnsavedContext.Provider value={value}>
      <div onClickCapture={guardNavigation}>{children}</div>
    </UnsavedContext.Provider>
  );
}

/** Marca un formulario como pendiente mientras ``dirty`` sea verdadero. */
export function useDirty(key: string, dirty: boolean) {
  const { setDirty } = useContext(UnsavedContext);
  useEffect(() => {
    setDirty(key, dirty);
    return () => setDirty(key, false);
  }, [key, dirty, setDirty]);
}

export function useUnsavedChanges() {
  return useContext(UnsavedContext);
}
