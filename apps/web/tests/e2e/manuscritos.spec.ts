import { expect, test, type Page } from "@playwright/test";

// Cada ejecución usa títulos únicos: la base de datos E2E conserva datos entre ejecuciones.
const runId = Date.now().toString(36);
const ORIGINAL = "Primera línea del texto.\nLa lluvia caía sobre el tejado.";
const REVISED = "Primera línea del texto revisada.\nLa lluvia caía sobre el tejado.";

/** Sitúa la selección del navegador sobre un fragmento del contenido (textarea de solo lectura). */
async function selectInContent(page: Page, fragment: string) {
  const content = page.locator("#contenido-version");
  await expect(content).not.toHaveValue("");
  await content.evaluate((element, target) => {
    const textarea = element as HTMLTextAreaElement;
    const start = textarea.value.indexOf(target);
    if (start < 0) throw new Error(`fragmento no encontrado: ${target}`);
    textarea.focus();
    textarea.setSelectionRange(start, start + target.length);
  }, fragment);
}

test("flujo principal: crear, versionar sin sobrescribir y comentar una versión concreta", async ({
  page,
}) => {
  const title = `Novela E2E ${runId}`;

  // 1. Crear el manuscrito con su versión 1.
  await page.goto("/manuscritos");
  await page.getByLabel("Título del manuscrito").fill(title);
  await page.getByLabel("Contenido de la versión 1").fill(ORIGINAL);
  await page.getByRole("button", { name: "Crear manuscrito" }).click();

  await expect(page).toHaveURL(/\/manuscritos\/\d+$/);
  await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
  await expect(page.getByRole("link", { name: "Versión 1" })).toBeVisible();

  // 2. Crear la versión 2 a partir de la 1. El contenido inicial es el de la versión 1.
  await expect(page.getByLabel("Contenido de la nueva versión")).toHaveValue(ORIGINAL);
  await page.getByLabel("Contenido de la nueva versión").fill(REVISED);
  await page.getByLabel("Nota (opcional)").fill("primera revisión");
  await page.getByRole("button", { name: "Guardar como nueva versión" }).click();

  await expect(page).toHaveURL(/\/versiones\/\d+$/);
  await expect(page.getByRole("heading", { level: 1, name: /Versión 2/ })).toBeVisible();
  await expect(page.locator("#contenido-version")).toHaveValue(REVISED);
  const versionTwoUrl = page.url();

  // 3. La versión 1 conserva su contenido original.
  await page.goto("/manuscritos");
  await page.getByRole("link", { name: title }).click();
  await page.getByRole("link", { name: "Versión 1" }).click();
  await expect(page.getByRole("heading", { level: 1, name: /Versión 1/ })).toBeVisible();
  await expect(page.locator("#contenido-version")).toHaveValue(ORIGINAL);

  // 4. Comentar una cita de la versión 1 con selección real.
  await page.getByRole("button", { name: "Usar la selección del contenido" }).click();
  await expect(page.getByText("Selecciona un fragmento del contenido")).toBeVisible();

  await selectInContent(page, "lluvia");
  await page.getByRole("button", { name: "Usar la selección del contenido" }).click();
  await expect(page.getByText("«lluvia»")).toBeVisible();

  await page.getByLabel("Nombre de quien revisa").fill("Editora de prueba");
  await page.getByLabel("Comentario", { exact: true }).fill("La imagen de la lluvia abre la escena.");
  await page.getByRole("button", { name: "Guardar comentario" }).click();

  await expect(page.getByRole("status")).toHaveText(/Comentario guardado en la versión 1/);
  const commentBlock = page.locator("article").filter({ hasText: "La imagen de la lluvia abre la escena." });
  await expect(commentBlock.locator("blockquote")).toHaveText("lluvia");
  await expect(commentBlock).toContainText("Línea 2");
  await expect(commentBlock).toContainText("Intención del autor: no declarada");

  // 5. El comentario no aparece en la versión 2, y la versión 2 sigue igual.
  await page.goto(versionTwoUrl);
  await expect(page.getByText("Esta versión no tiene comentarios.")).toBeVisible();
  await expect(page.getByText("La imagen de la lluvia abre la escena.")).toHaveCount(0);
  await expect(page.locator("#contenido-version")).toHaveValue(REVISED);
});

test("una inferencia no se guarda sin su cadena de inferencia", async ({ page }) => {
  await page.goto("/manuscritos");
  await page.getByLabel("Título del manuscrito").fill(`Inferencia E2E ${runId}`);
  await page.getByLabel("Contenido de la versión 1").fill(ORIGINAL);
  await page.getByRole("button", { name: "Crear manuscrito" }).click();
  await expect(page).toHaveURL(/\/manuscritos\/\d+$/);
  await page.getByRole("link", { name: "Versión 1" }).click();

  await selectInContent(page, "tejado");
  await page.getByRole("button", { name: "Usar la selección del contenido" }).click();
  await page.getByLabel("Nombre de quien revisa").fill("Editor de prueba");
  await page.getByLabel("Tipo de comentario").selectOption("inferencia");
  await page.getByLabel("Comentario", { exact: true }).fill("El tejado sugiere refugio.");

  // El campo de cadena de inferencia es obligatorio: la validación del navegador impide enviar.
  const basis = page.getByLabel("Cadena de inferencia (obligatoria)");
  await expect(basis).toHaveAttribute("required", "");
  await page.getByRole("button", { name: "Guardar comentario" }).click();
  expect(await basis.evaluate((element) => (element as HTMLTextAreaElement).validity.valueMissing)).toBe(true);
  await expect(page.getByRole("status")).toHaveCount(0);
  // Ningún comentario llegó al servidor: la versión sigue sin comentarios.
  await expect(page.getByText("Esta versión no tiene comentarios.")).toBeVisible();
});
