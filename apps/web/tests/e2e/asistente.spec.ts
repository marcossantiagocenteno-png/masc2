import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/**
 * Asistente (chat de la novela): el chat propone, nada cambia sin aprobación y rechazar no toca datos.
 * Usa el proveedor simulado (por defecto). Cada prueba crea su propia novela.
 */

const API = "http://127.0.0.1:8100";
const runId = `asis-${Date.now().toString(36)}`;

async function createProject(page: Page, name: string): Promise<number> {
  await page.goto("/proyectos");
  await page.getByLabel("Nombre de la novela").fill(name);
  await page.getByRole("button", { name: "Crear proyecto" }).click();
  await expect(page).toHaveURL(/\/proyectos\/\d+$/);
  return Number(page.url().match(/\/proyectos\/(\d+)/)?.[1]);
}

async function personajes(request: APIRequestContext, projectId: number): Promise<string[]> {
  const respuesta = await request.get(`${API}/projects/${projectId}/planificacion/personajes`);
  expect(respuesta.status()).toBe(200);
  return (await respuesta.json()).map((personaje: { name: string }) => personaje.name);
}

test("el chat propone un personaje; no existe hasta aprobarlo y al aprobarlo aparece en la novela", async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const projectId = await createProject(page, `Asistente aprobar ${runId}`);
  await page.goto(`/proyectos/${projectId}/asistente`);
  await expect(page.getByText("Respuestas simuladas, sin IA")).toBeVisible();

  await page.getByLabel("Mensaje al asistente").fill("crea un personaje llamado Lucía");
  await page.getByRole("button", { name: "Enviar" }).click();

  await expect(page.getByText("He preparado una propuesta para crear «Lucía»")).toBeVisible();
  await expect(page.getByText("Motivo: Pedido en el chat")).toBeVisible();
  expect(await personajes(request, projectId)).toEqual([]);

  await page.getByRole("button", { name: "Aprobar y aplicar" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Propuesta aplicada." })).toBeVisible();
  expect(await personajes(request, projectId)).toEqual(["Lucía"]);
  await expect(page.getByRole("button", { name: "Aprobar y aplicar" })).toHaveCount(0);
});

test("rechazar una propuesta la deja en el historial y no crea ningún personaje", async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const projectId = await createProject(page, `Asistente rechazar ${runId}`);
  await page.goto(`/proyectos/${projectId}/asistente`);

  await page.getByLabel("Mensaje al asistente").fill("crea un lugar llamado Faro");
  await page.getByRole("button", { name: "Enviar" }).click();
  await expect(page.getByRole("button", { name: "Rechazar" })).toBeVisible();

  await page.getByRole("button", { name: "Rechazar" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Propuesta rechazada." })).toBeVisible();
  const lugares = await (await request.get(`${API}/projects/${projectId}/planificacion/lugares`)).json();
  expect(lugares).toEqual([]);
  await expect(page.getByRole("heading", { name: "Memoria narrativa" })).toBeVisible();
});
