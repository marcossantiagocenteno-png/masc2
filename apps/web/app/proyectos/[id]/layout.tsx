"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { UnsavedChangesProvider } from "@/components/planning/UnsavedChanges";

const SECTIONS = [
  { segment: "", label: "Visión general" },
  { segment: "personajes", label: "Personajes" },
  { segment: "lugares", label: "Lugares" },
  { segment: "trama", label: "Trama y misterios" },
  { segment: "cronologia", label: "Cronología" },
  { segment: "estructura", label: "Estructura" },
] as const;

/** Espacio de trabajo de una novela: identifica el proyecto y organiza sus secciones. */
export default function ProjectWorkspaceLayout({ children }: { children: ReactNode }) {
  const params = useParams<{ id: string }>();
  const pathname = usePathname();
  const base = `/proyectos/${params.id}`;

  function isActive(segment: string): boolean {
    const href = segment ? `${base}/${segment}` : base;
    if (segment === "") return pathname === base || pathname === `${base}/`;
    return pathname === href || pathname.startsWith(`${href}/`);
  }

  return (
    <UnsavedChangesProvider>
      <div className="mx-auto max-w-5xl px-4 pt-8 sm:px-6">
        <p className="ne-kicker">Espacio de trabajo de la novela</p>
        <nav aria-label="Secciones de la novela" className="mt-3 flex flex-wrap gap-x-6 gap-y-1 border-b border-[var(--color-line)] text-[0.9375rem]">
          {SECTIONS.map((section) => {
            const href = section.segment ? `${base}/${section.segment}` : base;
            const active = isActive(section.segment);
            return (
              <Link
                key={section.label}
                href={href}
                aria-current={active ? "page" : undefined}
                className={`ne-tab hover:text-[var(--color-ink)] ${active ? "font-medium" : ""}`}
              >
                {section.label}
              </Link>
            );
          })}
        </nav>
      </div>
      {children}
    </UnsavedChangesProvider>
  );
}
