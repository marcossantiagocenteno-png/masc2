import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Novel Engine",
  description: "Entorno privado de escritura y edición literaria asistida por IA.",
};

/** Layout raíz: idioma español y estilos globales. */
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
