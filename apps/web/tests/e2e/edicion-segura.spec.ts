import { expect, test } from "@playwright/test";

/**
 * Regresión: cambiar la versión de partida no debe borrar en silencio un texto
 * escrito y sin guardar. Si el autor cancela, la selección y el texto se conservan.
 */
test("cambiar la versión de partida no sustituye un texto sin guardar sin confirmación", async ({ page }) => {
  const runId = Date.now().toString(36);
  const TEXT_A = `Texto A ${runId}.`;
  const TEXT_B = `Texto B ${runId}.`;
  const UNSAVED = `Escritura sin guardar ${runId}.`;

  await page.goto("/manuscritos");
  await page.getByLabel("Título del manuscrito").fill(`Edición segura ${runId}`);
  await page.getByLabel("Contenido de la versión 1").fill(TEXT_A);
  await page.getByRole("button", { name: "Crear manuscrito" }).click();
  await expect(page).toHaveURL(/\/manuscritos\/\d+$/);
  const manuscriptUrl = page.url();

  // Esperar a que la página esté lista (versión de partida cargada) antes de escribir.
  await expect(page.getByLabel("Contenido de la nueva versión")).toHaveValue(TEXT_A);

  // Versión 2, para que haya dos versiones entre las que elegir.
  await page.getByLabel("Contenido de la nueva versión").fill(TEXT_B);
  await page.getByRole("button", { name: "Guardar como nueva versión" }).click();
  await expect(page).toHaveURL(/\/versiones\/\d+$/);

  // El autor escribe algo sin guardar y cambia la versión de partida a la 1.
  await page.goto(manuscriptUrl);
  const editor = page.getByLabel("Contenido de la nueva versión");
  await expect(editor).toHaveValue(TEXT_B);
  await editor.fill(UNSAVED);

  const base = page.getByLabel("Partir de");
  const dialogs: string[] = [];
  page.on("dialog", (dialog) => {
    dialogs.push(dialog.message());
    void dialog.dismiss();
  });
  await base.selectOption({ label: "Versión 1" });

  // Debe preguntar, y al cancelar debe conservar el texto escrito y la selección anterior.
  await expect.poll(() => dialogs.length).toBe(1);
  await expect(editor).toHaveValue(UNSAVED);
  await expect(base).toHaveValue(await base.locator("option", { hasText: "Versión 2" }).getAttribute("value") ?? "");
});

test("al confirmar el cambio de versión de partida, el contenido se reemplaza", async ({ page }) => {
  const runId = Date.now().toString(36);
  await page.goto("/manuscritos");
  await page.getByLabel("Título del manuscrito").fill(`Edición segura OK ${runId}`);
  await page.getByLabel("Contenido de la versión 1").fill(`Original ${runId}.`);
  await page.getByRole("button", { name: "Crear manuscrito" }).click();
  await expect(page).toHaveURL(/\/manuscritos\/\d+$/);
  const manuscriptUrl = page.url();
  await page.getByLabel("Contenido de la nueva versión").fill(`Segunda ${runId}.`);
  await page.getByRole("button", { name: "Guardar como nueva versión" }).click();
  await expect(page).toHaveURL(/\/versiones\/\d+$/);

  await page.goto(manuscriptUrl);
  const editor = page.getByLabel("Contenido de la nueva versión");
  await editor.fill("Cambio no guardado.");
  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByLabel("Partir de").selectOption({ label: "Versión 1" });
  await expect(editor).toHaveValue(`Original ${runId}.`);
});

/**
 * Regresión de carrera: si el autor escribe mientras llega la versión de partida,
 * la carga asíncrona no debe sustituir lo escrito. La respuesta se retrasa a propósito.
 */
test("un texto escrito mientras carga la versión de partida no se sustituye", async ({ page }) => {
  const runId = Date.now().toString(36);
  await page.goto("/manuscritos");
  await page.getByLabel("Título del manuscrito").fill(`Carrera ${runId}`);
  await page.getByLabel("Contenido de la versión 1").fill(`Base ${runId}.`);
  await page.getByRole("button", { name: "Crear manuscrito" }).click();
  await expect(page).toHaveURL(/\/manuscritos\/\d+$/);
  const manuscriptUrl = page.url();

  // Con la carga retrasada, escribimos antes de que llegue la versión.
  await page.route(/\/versions\/\d+$/, async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1500));
    await route.continue();
  });
  await page.goto(manuscriptUrl);
  // La lista de versiones ya está cargada (el selector tiene su opción); solo la versión de partida se retrasa.
  await expect(page.getByLabel("Partir de").locator("option")).toHaveCount(1);
  const editor = page.getByLabel("Contenido de la nueva versión");
  await editor.fill("Texto escrito durante la carga.");
  await expect(page.getByRole("button", { name: "Guardar como nueva versión" })).toBeEnabled();
  await page.waitForTimeout(2000);
  await expect(editor).toHaveValue("Texto escrito durante la carga.");
});
