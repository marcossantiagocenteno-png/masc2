import { expect, test } from "@playwright/test";
import { ApiError, api } from "../../lib/api";

/**
 * Un fallo de red o de CORS debe decir qué comprobar, y un error HTTP del servidor debe conservar su mensaje.
 * Antes, cualquier fallo mostraba solo «No se pudo conectar», sin pista sobre la base de datos.
 */

test("un fallo de red indica dónde comprobar el backend y su esquema", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => {
    throw new TypeError("Failed to fetch");
  };
  try {
    const error = await api.getProject(1).catch((reason: unknown) => reason);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(0);
    expect((error as ApiError).message).toContain("/health");
    expect((error as ApiError).message).toContain("base de datos");
  } finally {
    globalThis.fetch = original;
  }
});

test("un error HTTP del servidor conserva su detalle y no se confunde con un fallo de conexión", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ detail: "Error interno del servidor. Revisa el registro del backend." }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  try {
    const error = await api.getProject(1).catch((reason: unknown) => reason);
    expect((error as ApiError).status).toBe(500);
    expect((error as ApiError).message).toBe("Error interno del servidor. Revisa el registro del backend.");
  } finally {
    globalThis.fetch = original;
  }
});
