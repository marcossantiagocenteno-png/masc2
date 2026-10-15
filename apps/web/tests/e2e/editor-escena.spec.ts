import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/**
 * Editor único de escena (E3): desde la escena se escribe, se crean versiones formales y se restauran puntos de
 * recuperación. Cada prueba crea su propia novela y su propia escena con la API.
 */

const API = "http://127.0.0.1:8100";
const runId = `esc-${Date.now().toString(36)}`;

async function createProject(page: Page, name: string): Promise<number> {
  await page.goto("/proyectos");
  await page.getByLabel("Nombre de la novela").fill(name);
  await page.getByRole("button", { name: "Crear proyecto" }).click();
  await expect(page).toHaveURL(/\/proyectos\/\d+$/);
  return Number(page.url().match(/\/proyectos\/(\d+)/)?.[1]);
}

async function crearEscena(request: APIRequestContext, projectId: number, title: string): Promise<number> {
  const response = await request.post(`${API}/projects/${projectId}/planificacion/estructura`, {
    data: { kind: "escena", parent_id: null, title },
  });
  expect(response.status()).toBe(201);
  return (await response.json()).id;
}

function estado(page: Page, texto: string) {
  return page.getByRole("status").filter({ hasText: texto });
}

test("desde la escena se crea una versión formal del texto actual", async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const projectId = await createProject(page, `Versión ${runId}`);
  const nodeId = await crearEscena(request, projectId, `Escena V ${runId}`);
  await page.goto(`/proyectos/${projectId}/estructura/${nodeId}`);

  await page.getByRole("button", { name: "Empezar a escribir esta escena" }).click();
  await page.getByLabel(`Texto de «Escena V ${runId}»`).fill(`Texto de la versión ${runId}.`);
  await expect(estado(page, "Borrador guardado")).toBeVisible();

  await page.getByRole("button", { name: "Guardar como nueva versión" }).click();
  await expect(page).toHaveURL(/\/proyectos\/\d+\/manuscritos\/\d+\/versiones\/\d+$/);
  await page.goBack();
  await expect(page.getByRole("link", { name: "Versión 1", exact: true })).toBeVisible();
});

test("desde la escena se restaura un punto de recuperación y el texto vuelve a ese estado", async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const projectId = await createProject(page, `Restaurar ${runId}`);
  const nodeId = await crearEscena(request, projectId, `Escena R ${runId}`);
  await page.goto(`/proyectos/${projectId}/estructura/${nodeId}`);

  await page.getByRole("button", { name: "Empezar a escribir esta escena" }).click();
  const texto = page.getByLabel(`Texto de «Escena R ${runId}»`);
  await texto.fill(`Primera redacción ${runId}.`);
  await expect(estado(page, "Borrador guardado")).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "Automático" })).toHaveCount(1);

  await texto.fill(`Segunda redacción ${runId}.`);
  await expect(estado(page, "Borrador guardado")).toBeVisible();

  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: /^Restaurar punto de/ }).click();
  await expect(texto).toHaveValue(`Primera redacción ${runId}.`);
  await expect(page.getByRole("listitem").filter({ hasText: "Antes de restaurar" })).toBeVisible();
});

test("el historial de la escena empieza con la versión 1 que crea su manuscrito", async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const projectId = await createProject(page, `Historial ${runId}`);
  const nodeId = await crearEscena(request, projectId, `Escena H ${runId}`);
  await page.goto(`/proyectos/${projectId}/estructura/${nodeId}`);
  await page.getByRole("button", { name: "Empezar a escribir esta escena" }).click();

  const historial = page.getByRole("region", { name: "Versiones de la escena" });
  await expect(historial.getByRole("link", { name: "Versión 1", exact: true })).toBeVisible();
});
