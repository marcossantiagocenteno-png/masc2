import { expect, test } from "@playwright/test";

/**
 * Análisis de una versión de un manuscrito con proyecto: el panel usa las rutas acotadas al proyecto.
 * Se crean la novela y el manuscrito por la API; el recorrido de análisis es el de la interfaz.
 */

const API = "http://127.0.0.1:8100";
const runId = Date.now().toString(36);
const CONTENT = "Dijo que que no lo sabía.\nLa lluvia caía sobre el tejado. Nadie se movió.";

test("el análisis de una versión de proyecto se lanza y persiste por la ruta acotada", async ({ page, request }) => {
  const project = await request.post(`${API}/projects`, { data: { name: `Analisis proyecto ${runId}` } });
  expect(project.status()).toBe(201);
  const projectId = (await project.json()).id as number;
  const created = await request.post(`${API}/projects/${projectId}/manuscripts`, {
    data: { title: `Analizado en proyecto ${runId}`, content: CONTENT },
  });
  expect(created.status()).toBe(201);
  const manuscriptId = (await created.json()).id as number;
  const versions = await request.get(`${API}/projects/${projectId}/manuscripts/${manuscriptId}/versions`);
  const versionId = (await versions.json())[0].id as number;

  await page.goto(`/manuscritos/${manuscriptId}/versiones/${versionId}`);
  await expect(page.locator("#contenido-version")).toHaveValue(CONTENT);

  await page.locator("#contenido-version").evaluate((element) => {
    const textarea = element as HTMLTextAreaElement;
    textarea.focus();
    textarea.setSelectionRange(0, textarea.value.length);
  });
  await page.getByRole("button", { name: "Analizar la selección del contenido" }).click();
  await expect(page.getByRole("note").filter({ hasText: "ANALIZADOR SIMULADO: no es una evaluación" })).toBeVisible();
  await expect(page.getByRole("region", { name: /Problemas verificables/ }).getByText("«que que»")).toBeVisible();
  await expect(page.locator("#contenido-version")).toHaveValue(CONTENT);

  await page.reload();
  await expect(page.getByLabel("Análisis guardado")).toHaveValue(/\d+/);

  // La misma versión, leída por la ruta acotada, sigue con su análisis.
  const runs = await request.get(`${API}/projects/${projectId}/manuscripts/${manuscriptId}/versions/${versionId}/analyses`);
  expect((await runs.json()).length).toBeGreaterThan(0);
  // Una novela distinta no ve esa versión, aunque el id sea el mismo.
  const other = await request.post(`${API}/projects`, { data: { name: `Otra novela ${runId}` } });
  const otherId = (await other.json()).id as number;
  const foreign = await request.get(`${API}/projects/${otherId}/manuscripts/${manuscriptId}/versions/${versionId}/analyses`);
  expect(foreign.status()).toBe(404);
});
