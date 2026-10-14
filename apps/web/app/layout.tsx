import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Novel Engine",
  description: "Entorno privado de escritura y edición literaria asistida por IA.",
};

/** Layout raíz: idioma, estilos globales y la cabecera de navegación principal de toda la aplicación. */
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es">
      <body className="min-h-screen antialiased">
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
        {children}
      </body>
    </html>
  );
}
