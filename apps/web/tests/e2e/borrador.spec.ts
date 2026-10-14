import { expect, test, type Page } from "@playwright/test";

/**
 * Borrador persistente en el editor: autoguardado, recuperación, errores, conflictos,
 * restauración y cambio de página con cambios pendientes.
 *
 * Los fallos del servidor se simulan con page.route. No hay esperas fijas: se usan
 * aserciones con reintento sobre el estado visible.
 */

const WEB = "http://localhost:3100";
const runId = Date.now().toString(36);

async function crearManuscrito(page: Page, texto: string): Promise<string> {
  await page.goto("/manuscritos");
  await page.getByLabel("Título del manuscrito").fill(`Borrador ${runId}`);
  await page.getByLabel("Contenido de la versión 1").fill(texto);
  await page.getByRole("button", { name: "Crear manuscrito" }).click();
  await expect(page).toHaveURL(/\/manuscritos\/\d+$/);
  await expect(page.getByLabel("Contenido de la nueva versión")).toHaveValue(texto);
  return page.url();
}

function indicador(page: Page, texto: string) {
  return page.getByRole("status").filter({ hasText: texto });
}

/** Simula un fallo del servidor en las escrituras del borrador, con cabeceras CORS para que el navegador lo lea. */
async function fallarEscriturasDelBorrador(page: Page, detail: string) {
  await page.route("**/manuscripts/*/draft", async (route) => {
    const request = route.request();
    const cors = { "Access-Control-Allow-Origin": WEB, "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Allow-Methods": "GET, POST, PUT" };
    if (request.method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers: cors });
    } else if (request.method() === "PUT") {
      await route.fulfill({ status: 500, headers: cors, contentType: "application/json", body: JSON.stringify({ detail }) });
    } else {
      await route.continue();
    }
  });
}

test("el texto se guarda solo y el indicador no muestra «guardado» antes de tiempo", async ({ page }) => {
  await crearManuscrito(page, `Inicio ${runId}.`);
  const editor = page.getByLabel("Contenido de la nueva versión");

  await editor.fill(`Escritura automática ${runId}.`);
  await expect(indicador(page, "Cambios sin guardar")).toBeVisible();
  await expect(indicador(page, "Borrador guardado")).toBeVisible();
});

test("al volver a abrir la página se recupera el último borrador guardado", async ({ page }) => {
  const url = await crearManuscrito(page, `Inicio recarga ${runId}.`);
  const editor = page.getByLabel("Contenido de la nueva versión");
  await editor.fill(`Texto para recuperar ${runId}.`);
  await expect(indicador(page, "Borrador guardado")).toBeVisible();

  await page.goto(url);
  await expect(page.getByLabel("Contenido de la nueva versión")).toHaveValue(`Texto para recuperar ${runId}.`);
});

test("un error del servidor conserva el texto, no muestra éxito y permite reintentar", async ({ page }) => {
  await crearManuscrito(page, `Error inicial ${runId}.`);
  const editor = page.getByLabel("Contenido de la nueva versión");
  const escrito = `Texto que no debe perderse ${runId}.`;

  await fallarEscriturasDelBorrador(page, "Error simulado del servidor.");
  await editor.fill(escrito);
  await expect(page.getByRole("alert").filter({ hasText: "No guardado" })).toBeVisible();
  await expect(indicador(page, "Borrador guardado")).toHaveCount(0);
  await expect(editor).toHaveValue(escrito);

  await page.unroute("**/manuscripts/*/draft");
  await page.getByRole("button", { name: "Reintentar" }).click();
  await expect(indicador(page, "Borrador guardado")).toBeVisible();
  await expect(editor).toHaveValue(escrito);
});

test("un guardado desde otra ventana produce un conflicto y «Mantener mi texto» conserva ambos", async ({ page }) => {
  await crearManuscrito(page, `Conflicto ${runId}.`);
  const editorA = page.getByLabel("Contenido de la nueva versión");
  await editorA.fill(`Ventana A, primera ${runId}.`);
  await expect(indicador(page, "Borrador guardado")).toBeVisible();

  const otra = await page.context().newPage();
  await otra.goto(page.url());
  const editorB = otra.getByLabel("Contenido de la nueva versión");
  await expect(editorB).toHaveValue(`Ventana A, primera ${runId}.`);

  // La ventana A guarda otra revisión; la ventana B sigue con la anterior.
  await editorA.fill(`Ventana A, segunda ${runId}.`);
  await expect(indicador(page, "Borrador guardado")).toBeVisible();

  await editorB.fill(`Ventana B, tardía ${runId}.`);
  await expect(otra.getByRole("alert").filter({ hasText: "Conflicto" })).toBeVisible();

  await otra.getByRole("button", { name: "Mantener mi texto" }).click();
  await expect(otra.getByRole("status").filter({ hasText: "Borrador guardado" })).toBeVisible();

  await page.reload();
  await expect(page.getByLabel("Contenido de la nueva versión")).toHaveValue(`Ventana B, tardía ${runId}.`);
  await expect(page.getByRole("listitem").filter({ hasText: "Antes de sobrescribir" })).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "Conflicto con otra ventana" })).toBeVisible();
  await otra.close();
});

test("restaurar un punto deja el estado anterior como punto y no cambia las versiones", async ({ page }) => {
  const url = await crearManuscrito(page, `Versión formal ${runId}.`);
  const editor = page.getByLabel("Contenido de la nueva versión");
  await editor.fill(`Primera redacción ${runId}.`);
  await expect(indicador(page, "Borrador guardado")).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "Automático" })).toHaveCount(1);

  await editor.fill(`Segunda redacción ${runId}.`);
  await expect(indicador(page, "Borrador guardado")).toBeVisible();

  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: /^Restaurar punto de/ }).click();
  await expect(editor).toHaveValue(`Primera redacción ${runId}.`);
  await expect(page.getByRole("listitem").filter({ hasText: "Antes de restaurar" })).toBeVisible();

  await page.goto(url);
  await expect(page.getByRole("link", { name: "Versión 1", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Versión 2", exact: true })).toHaveCount(0);
});

test("salir con cambios pendientes guarda antes de cambiar de página", async ({ page }) => {
  const url = await crearManuscrito(page, `Salida ${runId}.`);
  const editor = page.getByLabel("Contenido de la nueva versión");
  await editor.fill(`Texto al salir ${runId}.`);

  await page.getByRole("main").getByRole("link", { name: "Manuscritos", exact: true }).click();
  await expect(page).toHaveURL(/\/manuscritos$/);

  await page.goto(url);
  await expect(page.getByLabel("Contenido de la nueva versión")).toHaveValue(`Texto al salir ${runId}.`);
});

test("si no se puede guardar al salir, el aviso permite quedarse en la página", async ({ page }) => {
  const url = await crearManuscrito(page, `Salida con error ${runId}.`);
  const editor = page.getByLabel("Contenido de la nueva versión");
  await fallarEscriturasDelBorrador(page, "Error simulado del servidor.");
  await editor.fill(`Texto sin guardar ${runId}.`);
  await expect(page.getByRole("alert").filter({ hasText: "No guardado" })).toBeVisible();

  page.once("dialog", (dialog) => void dialog.dismiss());
  await page.getByRole("main").getByRole("link", { name: "Manuscritos", exact: true }).click();
  await expect(page).toHaveURL(url);
  await expect(editor).toHaveValue(`Texto sin guardar ${runId}.`);

  await page.unroute("**/manuscripts/*/draft");
});
