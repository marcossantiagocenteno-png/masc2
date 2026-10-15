import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/**
 * Estructura como lista jerárquica (E2): renombrar desde la propia fila, cancelar con Escape y persistir tras recargar.
 * Cada prueba crea su propia novela con la API para no depender de la interfaz de creación.
 */

const API = "http://127.0.0.1:8100";
const runId = `arbol-${Date.now().toString(36)}`;

async function createProject(page: Page, name: string): Promise<number> {
  await page.goto("/proyectos");
  await page.getByLabel("Nombre de la novela").fill(name);
  await page.getByRole("button", { name: "Crear proyecto" }).click();
  await expect(page).toHaveURL(/\/proyectos\/\d+$/);
  return Number(page.url().match(/\/proyectos\/(\d+)/)?.[1]);
}

async function crearActo(request: APIRequestContext, projectId: number, title: string): Promise<void> {
  const response = await request.post(`${API}/projects/${projectId}/planificacion/estructura`, {
    data: { kind: "acto", parent_id: null, title },
  });
  expect(response.status()).toBe(201);
}

test("renombrar un acto desde su fila guarda el título y sigue tras recargar", async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const projectId = await createProject(page, `Renombrar ${runId}`);
  await crearActo(request, projectId, `Acto viejo ${runId}`);
  await page.goto(`/proyectos/${projectId}`);
  // Espera a que la visión general monte la sección antes de interactuar: navegar a la ancla durante el montaje lo interrumpe.
  await expect(page.locator("#estructura")).toBeVisible();

  await page.getByRole("button", { name: `Renombrar Acto: Acto viejo ${runId}`, exact: true }).click();
  const formulario = page.getByRole("form", { name: `Renombrar Acto: Acto viejo ${runId}` });
  await formulario.getByLabel("Nuevo título", { exact: true }).fill(`Acto nuevo ${runId}`);
  await formulario.getByRole("button", { name: "Guardar título", exact: true }).click();

  await expect(page.getByRole("status").filter({ hasText: "Título guardado." })).toBeVisible();
  await expect(page.getByRole("button", { name: `Renombrar Acto: Acto nuevo ${runId}`, exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("button", { name: `Renombrar Acto: Acto nuevo ${runId}`, exact: true })).toBeVisible();
});

test("Escape cancela el renombrado y el título no cambia", async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const projectId = await createProject(page, `Cancelar ${runId}`);
  const titulo = `Capítulo fijo ${runId}`;
  await request.post(`${API}/projects/${projectId}/planificacion/estructura`, {
    data: { kind: "acto", parent_id: null, title: `Acto base ${runId}` },
  });
  const acto = await (
    await request.get(`${API}/projects/${projectId}/planificacion/estructura`)
  ).json();
  await request.post(`${API}/projects/${projectId}/planificacion/estructura`, {
    data: { kind: "capitulo", parent_id: acto[0].id, title: titulo },
  });
  await page.goto(`/proyectos/${projectId}`);
  // Espera a que la visión general monte la sección antes de interactuar: navegar a la ancla durante el montaje lo interrumpe.
  await expect(page.locator("#estructura")).toBeVisible();

  await page.getByRole("button", { name: `Renombrar Capítulo: ${titulo}`, exact: true }).click();
  const campo = page.getByRole("form", { name: `Renombrar Capítulo: ${titulo}` }).getByLabel("Nuevo título", { exact: true });
  await campo.fill("Cambio que no debe guardarse");
  await campo.press("Escape");

  await expect(page.getByRole("form", { name: `Renombrar Capítulo: ${titulo}` })).toHaveCount(0);
  await expect(page.getByRole("button", { name: `Renombrar Capítulo: ${titulo}`, exact: true })).toBeVisible();
});

test("el árbol va antes que los modelos de estructura, que quedan plegados", async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const projectId = await createProject(page, `Orden ${runId}`);
  await crearActo(request, projectId, `Acto orden ${runId}`);
  await page.goto(`/proyectos/${projectId}`);
  // Espera a que la visión general monte la sección antes de interactuar: navegar a la ancla durante el montaje lo interrumpe.
  await expect(page.locator("#estructura")).toBeVisible();

  const arbol = page.getByRole("list", { name: "Árbol de la estructura" });
  const modelos = page.locator("details", { hasText: "Modelos de estructura y propuestas de actos" });
  await expect(arbol).toBeVisible();
  await expect(modelos).toBeVisible();
  await expect(modelos).not.toHaveAttribute("open", "");
  const yArbol = (await arbol.boundingBox())?.y ?? 0;
  const yModelos = (await modelos.boundingBox())?.y ?? 0;
  expect(yArbol).toBeLessThan(yModelos);
});
