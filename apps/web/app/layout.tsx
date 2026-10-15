import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { UnsavedChangesProvider } from "@/components/planning/UnsavedChanges";
import { ProjectsSidebar } from "@/components/workspace/ProjectsSidebar";
import { WorkspaceShell } from "@/components/workspace/WorkspaceShell";
import "./globals.css";

export const metadata: Metadata = {
  title: "Novel Engine",
  description: "Entorno privado de escritura y edición literaria asistida por IA.",
};

/**
 * Layout raíz: idioma, estilos globales, cabecera de navegación principal y espacio de trabajo con la lista de novelas.
 * La protección ante cambios sin guardar está aquí para cubrir también la lista y la cabecera, no solo las secciones de proyecto.
 */
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es">
      <body className="min-h-screen antialiased">
        <UnsavedChangesProvider>
          <header className="ne-app-header">
            <div className="mx-auto flex max-w-5xl flex-wrap items-baseline justify-between gap-x-8 gap-y-2 px-4 py-4 sm:px-6">
              <Link href="/" className="ne-brand">
                Novel Engine
              </Link>
              <nav aria-label="Principal" className="flex gap-6 text-[0.9375rem]">
                <Link href="/proyectos" className="ne-tab">
                  Proyectos
                </Link>
                <Link href="/manuscritos" className="ne-tab">
                  Manuscritos
                </Link>
              </nav>
            </div>
          </header>
          <WorkspaceShell sidebar={<ProjectsSidebar />}>{children}</WorkspaceShell>
        </UnsavedChangesProvider>
      </body>
    </html>
  );
}
