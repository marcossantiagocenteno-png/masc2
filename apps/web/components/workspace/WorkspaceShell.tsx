"use client";

import { usePathname } from "next/navigation";
import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

/**
 * Espacio de trabajo: lista de novelas a la izquierda y contenido a la derecha de la lista.
 * Desde 1280 px la lista está siempre visible. Por debajo se pliega en un botón que la despliega bajo la cabecera,
 * cerrada por defecto para no ocupar la escritura. Escape la cierra y devuelve el foco al botón.
 * Dentro de una novela hay además una zona de contexto: columna derecha desde 1280 px, bajo el contenido por debajo.
 */
export function WorkspaceShell({
  sidebar,
  children,
  context,
}: {
  sidebar: ReactNode;
  children: ReactNode;
  context?: ReactNode;
}) {
  const pathname = usePathname();
  const inProject = /^\/proyectos\/\d+/.test(pathname);
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const toggleRef = useRef<HTMLButtonElement>(null);

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape" && open) {
      setOpen(false);
      toggleRef.current?.focus();
    }
  }

  return (
    <div className={`ne-workspace ${inProject ? "ne-workspace--contexto" : ""}`.trim()} onKeyDown={handleKeyDown}>
      <aside aria-label="Lista de novelas" className="ne-workspace__sidebar">
        <button
          ref={toggleRef}
          type="button"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((value) => !value)}
          className="ne-button ne-button--small ne-workspace__toggle"
        >
          {open ? "Ocultar lista de proyectos" : "Mostrar lista de proyectos"}
        </button>
        <div
          id={panelId}
          onClick={(event) => {
            // Elegir una novela abre su espacio de trabajo: el panel se pliega para no tapar el contenido.
            if ((event.target as HTMLElement).closest("a")) setOpen(false);
          }}
          className={`ne-workspace__panel ${open ? "ne-workspace__panel--open" : ""}`}
        >
          {sidebar}
        </div>
      </aside>
      <div className="ne-workspace__main">{children}</div>
      {inProject ? context : null}
    </div>
  );
}
