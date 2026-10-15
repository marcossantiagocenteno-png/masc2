"use client";

import { RedirigirASeccion } from "@/components/navegacion/RedirigirASeccion";

/** Esta sección ahora vive en la visión general de la novela. Ruta antigua, conservada por compatibilidad. */
export default function Page() {
  return <RedirigirASeccion ancla="cronologia" />;
}
