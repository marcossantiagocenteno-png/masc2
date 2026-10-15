import { expect, test, type Locator, type Page } from "@playwright/test";

/**
 * Escritura de escenas: cada escena escribe en su propio manuscrito, desde la estructura.
 * Cada prueba crea su novela. Sin esperas fijas: aserciones con reintento sobre el estado visible.
 */

const WEB = "http://localhost:3100";
const API = "http://127.0.0.1:8100";
const runId = Date.now().toString(36);

async function createProject(page: Page, name: string) {
  await page.goto("/proyectos");
  await page.getByLabel("Nombre de la novela").fill(name);
  await page.getByRole("button", { name: "Crear proyecto" }).click();
  await expect(page).toHaveURL(/\/proyectos\/\d+$/);
  return Number(page.url().match(/\/proyectos\/(\d+)/)?.[1]);
}

async function section(page: Page, name: string) {
  await page.getByRole("navigation", { name: "Secciones de la novela" }).getByRole("link", { name, exact: true }).click();
}

function status(page: Page, text: string): Locator {
  return page.getByRole("status").filter({ hasText: text });
}

async function addScene(page: Page, title: string, parentLabel?: string) {
  await page.getByLabel("Tipo", { exact: true }).selectOption({ label: "Escena" });
  if (parentLabel) await page.getByLabel("Dentro de", { exact: true }).selectOption({ label: parentLabel });
  await page.getByLabel("Título (opcional)", { exact: true }).fill(title);
  await page.getByRole("button", { name: "Añadir escena", exact: true }).click();
  await expect(status(page, "añadid")).toBeVisible();
}

async function addChapter(page: Page, title: string, parentLabel: string) {
  await page.getByLabel("Tipo", { exact: true }).selectOption({ label: "Capítulo" });
  await page.getByLabel("Dentro de", { exact: true }).selectOption({ label: parentLabel });
  await page.getByLabel("Título (opcional)", { exact: true }).fill(title);
  await page.getByRole("button", { name: "Añadir capítulo", exact: true }).click();
  await expect(status(page, "añadid")).toBeVisible();
}

/** Abre la escena desde la estructura y devuelve la URL de su página. */
async function openScene(page: Page, title: string) {
  await page.getByRole("link", { name: `Abrir Escena: ${title}`, exact: true }).click();
  await expect(page.getByRole("heading", { name: `Planificación de «${title}»` })).toBeVisible();
}

function editor(page: Page): Locator {
  return page.getByLabel(/^Texto de/);
}

async function startWriting(page: Page) {
  await page.getByRole("button", { name: "Empezar a escribir esta escena", exact: true }).click();
  await expect(editor(page)).toBeVisible();
}

test("empezar a escribir una escena, guardar, recargar y ver su estado en la estructura", async ({ page }) => {
  await createProject(page, `Escritura ${runId}`);
  await section(page, "Estructura");
  const title = `Llegada ${runId}`;
  await addScene(page, title);
  await expect(page.getByText("Sin escritura", { exact: true })).toBeVisible();

  await openScene(page, title);
  await startWriting(page);
  await editor(page).fill("Llegó tarde a la estación.");
  await expect(status(page, "Guardado")).toBeVisible();

  await page.reload();
  await expect(editor(page)).toHaveValue("Llegó tarde a la estación.");
  await expect(page.getByText("Con texto", { exact: false }).first()).toBeVisible();

  await section(page, "Estructura");
  await expect(page.getByText("Con texto", { exact: true })).toBeVisible();
});

test("mover una escena a otro capítulo conserva su texto", async ({ page }) => {
  await createProject(page, `Mover texto ${runId}`);
  await section(page, "Estructura");
  await addChapter(page, `Cap A ${runId}`, "Raíz de la novela");
  await addChapter(page, `Cap B ${runId}`, "Raíz de la novela");
  await addScene(page, `Escena móvil ${runId}`, `Capítulo: Cap A ${runId}`);
  await openScene(page, `Escena móvil ${runId}`);
  await startWriting(page);
  await editor(page).fill("Texto que sobrevive al movimiento.");
  await expect(status(page, "Guardado")).toBeVisible();

  await section(page, "Estructura");
  await page.getByRole("button", { name: `Escena: Escena móvil ${runId}`, exact: true }).click();
  await page.getByLabel("Nuevo lugar", { exact: true }).selectOption({ label: `Capítulo: Cap B ${runId}` });
  await page.getByRole("button", { name: "Mover aquí" }).click();
  await expect(status(page, "Movido a su nuevo lugar")).toBeVisible();

  await openScene(page, `Escena móvil ${runId}`);
  await expect(editor(page)).toHaveValue("Texto que sobrevive al movimiento.");
});

test("renombrar una escena conserva su texto y el nombre del manuscrito se actualiza", async ({ page }) => {
  await createProject(page, `Renombrar ${runId}`);
  await section(page, "Estructura");
  await addScene(page, `Nombre viejo ${runId}`);
  await openScene(page, `Nombre viejo ${runId}`);
  await startWriting(page);
  await editor(page).fill("Texto bajo otro nombre.");
  await expect(status(page, "Guardado")).toBeVisible();

  await page.getByLabel("Título", { exact: true }).fill(`Nombre nuevo ${runId}`);
  await page.getByRole("button", { name: "Guardar cambios" }).click();
  await expect(status(page, "Cambios guardados")).toBeVisible();

  await page.reload();
  await expect(page.getByRole("heading", { name: `Planificación de «Nombre nuevo ${runId}»` })).toBeVisible();
  await expect(editor(page)).toHaveValue("Texto bajo otro nombre.");

  // El manuscrito de la escena no aparece en el listado global: su título se comprueba en su propia página.
  await page.getByRole("link", { name: "Versiones y puntos de recuperación" }).click();
  await expect(page.getByRole("heading", { level: 1, name: `Nombre nuevo ${runId}` })).toBeVisible();
});

test("un fallo al guardar mantiene el texto en pantalla y se puede reintentar", async ({ page }) => {
  await createProject(page, `Fallo guardado ${runId}`);
  await section(page, "Estructura");
  await addScene(page, `Fallo ${runId}`);
  await openScene(page, `Fallo ${runId}`);
  await startWriting(page);

  await page.route("**/planificacion/estructura/*/escritura/borrador", async (route) => {
    const cors = { "Access-Control-Allow-Origin": WEB, "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Allow-Methods": "GET, POST, PUT" };
    if (route.request().method() === "OPTIONS") await route.fulfill({ status: 204, headers: cors });
    else await route.fulfill({ status: 500, headers: cors, contentType: "application/json", body: JSON.stringify({ detail: "Error simulado del servidor." }) });
  });
  await editor(page).fill("Texto que no debe perderse.");
  await expect(page.getByRole("alert").filter({ hasText: "Error simulado del servidor." })).toBeVisible();
  await expect(status(page, "Guardado")).toHaveCount(0);
  await expect(editor(page)).toHaveValue("Texto que no debe perderse.");

  await page.unroute("**/planificacion/estructura/*/escritura/borrador");
  await page.getByRole("button", { name: "Reintentar", exact: true }).click();
  await expect(status(page, "Guardado")).toBeVisible();
  await page.reload();
  await expect(editor(page)).toHaveValue("Texto que no debe perderse.");
});

test("un cambio hecho en otra ventana se detecta como conflicto y no se pisa el texto", async ({ page, request }) => {
  const projectId = await createProject(page, `Conflicto ${runId}`);
  await section(page, "Estructura");
  await addScene(page, `Conflicto ${runId}`);
  await openScene(page, `Conflicto ${runId}`);
  await startWriting(page);
  const nodeId = Number(page.url().match(/estructura\/(\d+)/)?.[1]);

  // Otra ventana escribe primero: la revisión que tiene esta página ya no es la actual.
  const other = await request.put(`${API}/projects/${projectId}/planificacion/estructura/${nodeId}/escritura/borrador`, {
    data: { content: "Texto de la otra ventana", base_revision: 1, keep_previous: false },
  });
  expect(other.status()).toBe(200);

  await editor(page).fill("Mi texto de esta ventana");
  await expect(page.getByRole("button", { name: "Usar la versión guardada", exact: true })).toBeVisible({ timeout: 10_000 });
  await expect(editor(page)).toHaveValue("Mi texto de esta ventana");
  await expect(status(page, "Guardado")).toHaveCount(0);
});

test("empezar la escritura dos veces no crea nada nuevo", async ({ page, request }) => {
  const projectId = await createProject(page, `Doble inicio ${runId}`);
  await section(page, "Estructura");
  await addScene(page, `Doble ${runId}`);
  await openScene(page, `Doble ${runId}`);
  const nodeId = Number(page.url().match(/estructura\/(\d+)/)?.[1]);
  await startWriting(page);

  // Otra ventana intenta empezar la misma escena: recibe la escritura existente.
  const again = await request.post(`${API}/projects/${projectId}/planificacion/estructura/${nodeId}/escritura`);
  expect(again.status()).toBe(200);
  await page.reload();
  await expect(page.getByRole("button", { name: "Empezar a escribir esta escena", exact: true })).toHaveCount(0);
  await expect(editor(page)).toBeVisible();
});

test("las versiones siguen en la página del manuscrito, y la escena no aparece como manuscrito del proyecto", async ({ page, request }) => {
  const projectId = await createProject(page, `Versiones escena ${runId}`);
  await section(page, "Estructura");
  await addScene(page, `Versionada ${runId}`);
  await openScene(page, `Versionada ${runId}`);
  await startWriting(page);
  await editor(page).fill("Primera versión de la escena.");
  await expect(status(page, "Guardado")).toBeVisible();

  await page.getByRole("link", { name: "Versiones y puntos de recuperación" }).click();
  await expect(page).toHaveURL(/\/manuscritos\/\d+$/);
  await expect(page.getByRole("heading", { name: "Versiones", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Guardar como nueva versión" }).click();
  await expect(page).toHaveURL(/\/manuscritos\/\d+\/versiones\/\d+$/);

  // La versión formal no cambia el borrador: al volver, el texto sigue igual.
  await page.goBack();
  await page.goBack();
  await expect(editor(page)).toHaveValue("Primera versión de la escena.");

  // Control positivo: un manuscrito ordinario de la novela sí figura entre los manuscritos del proyecto.
  const ordinary = `Capítulo suelto ${runId}`;
  const created = await request.post(`${API}/projects/${projectId}/manuscripts`, { data: { title: ordinary, content: "Texto" } });
  expect(created.status()).toBe(201);
  // La visión general ya no lista manuscritos: la pertenencia se comprueba en la lista de la API.
  const lista = await (await request.get(`${API}/projects/${projectId}/manuscripts`)).json();
  const titulos = lista.map((item: { title: string }) => item.title);
  expect(titulos).toContain(ordinary);
  expect(titulos).not.toContain(`Versionada ${runId}`);
});

test("la escena escrita se ve bien en 360 px sin desbordamiento horizontal", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 740 });
  await createProject(page, `Movil escritura ${runId}`);
  await section(page, "Estructura");
  await addScene(page, `Móvil ${runId}`);
  await openScene(page, `Móvil ${runId}`);
  await startWriting(page);
  const overflows = () => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(await overflows()).toBeLessThanOrEqual(0);
  await expect(page.getByText("Versiones y puntos de recuperación")).toBeVisible();
});

test("el manuscrito de una escena indica que su título se cambia en la escena, y el enlace lleva allí", async ({ page }) => {
  await createProject(page, `Titulo derivado ${runId}`);
  await section(page, "Estructura");
  const title = `Titulo escena ${runId}`;
  await addScene(page, title);
  await openScene(page, title);
  await startWriting(page);
  await page.getByRole("link", { name: "Versiones y puntos de recuperación" }).click();
  await expect(page).toHaveURL(/\/manuscritos\/\d+$/);
  await expect(page.getByText("Es el texto de una escena. Su título es el de la escena y se cambia allí:")).toBeVisible();
  await page.getByRole("link", { name: "editar la escena" }).click();
  await expect(page.getByRole("heading", { name: `Planificación de «${title}»` })).toBeVisible();
});
