import { expect, test, type Locator, type Page } from "@playwright/test";

/**
 * Vista de libro (fase 3b, E1): índice derivado de la estructura, capítulos vacíos sin manuscrito, editor que solo crea
 * algo al pulsar «Empezar a escribir», y el control persistente «Manuscrito». Cada prueba crea sus propios datos.
 */

const runId = `libro-${Date.now().toString(36)}`;

async function createProject(page: Page, name: string): Promise<number> {
  await page.goto("/proyectos");
  await page.getByLabel("Nombre de la novela").fill(name);
  await page.getByRole("button", { name: "Crear proyecto" }).click();
  await expect(page).toHaveURL(/\/proyectos\/\d+$/);
  return Number(page.url().match(/\/proyectos\/(\d+)/)?.[1]);
}

async function addNode(page: Page, kind: "Acto" | "Capítulo" | "Escena", title: string, parentLabel?: string) {
  await page.getByLabel("Tipo", { exact: true }).selectOption({ label: kind });
  if (parentLabel) await page.getByLabel("Dentro de", { exact: true }).selectOption({ label: parentLabel });
  await page.getByLabel("Título (opcional)", { exact: true }).fill(title);
  await page.getByRole("button", { name: `Añadir ${kind.toLowerCase()}`, exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "añadid" })).toBeVisible();
}

/** Fila del propio elemento del índice: el <li> más cercano a su enlace (no el del acto que lo contiene). */
function fila(page: Page, nombre: string): Locator {
  return page
    .getByRole("navigation", { name: "Índice de la novela" })
    .getByRole("link", { name: nombre, exact: true })
    .locator("xpath=ancestor::li[1]");
}

test("un capítulo vacío aparece en el índice como vacío y abrirlo no crea ningún manuscrito", async ({ page }) => {
  const projectId = await createProject(page, `Vacío ${runId}`);
  const capitulo = `Capítulo vacío ${runId}`;
  await page.goto(`/proyectos/${projectId}/estructura`);
  await addNode(page, "Acto", `Acto ${runId}`);
  await addNode(page, "Capítulo", capitulo, `Acto: Acto ${runId}`);

  await page.goto(`/proyectos/${projectId}/libro`);
  await expect(fila(page, capitulo).getByText("Vacío", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: capitulo, exact: true }).click();
  await expect(page).toHaveURL(/\/libro\/\d+$/);
  await expect(page.getByLabel("Texto del capítulo")).toBeVisible();

  await page.goto(`/proyectos/${projectId}`);
  await expect(page.getByText("Este proyecto todavía no tiene manuscritos.")).toBeVisible();
});

test("«Empezar a escribir» crea la escena y su manuscrito con el texto escrito, y el índice lo refleja", async ({ page }) => {
  const projectId = await createProject(page, `Escribir ${runId}`);
  const capitulo = `Capítulo ${runId}`;
  await page.goto(`/proyectos/${projectId}/estructura`);
  await addNode(page, "Capítulo", capitulo);

  await page.goto(`/proyectos/${projectId}/libro`);
  await page.getByRole("link", { name: capitulo, exact: true }).click();
  const texto = `Primera frase del capítulo ${runId}.`;
  await page.getByLabel("Texto del capítulo").fill(texto);
  await page.getByRole("button", { name: "Empezar a escribir", exact: true }).click();

  // El capítulo pasa de vacío a con su escena, y la escena ya tiene texto.
  const escena = page.getByRole("link", { name: "Escena sin título", exact: true });
  await expect(escena).toBeVisible();
  await expect(page.getByText("Con texto", { exact: true })).toBeVisible();
  await expect(page.getByText("Terminado", { exact: true })).toBeVisible();

  await escena.click();
  await expect(page).toHaveURL(/\/estructura\/\d+$/);
  await expect(page.getByLabel(/^Texto de/)).toHaveValue(texto);
});

test("el control «Manuscrito» vuelve al índice desde cualquier apartado de la novela", async ({ page }) => {
  const projectId = await createProject(page, `Control ${runId}`);
  await page.goto(`/proyectos/${projectId}/estructura`);
  await page.getByRole("navigation", { name: "Secciones de la novela" }).getByRole("link", { name: "Personajes", exact: true }).click();
  await page.getByRole("navigation", { name: "Secciones de la novela" }).getByRole("link", { name: "Manuscrito", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/proyectos/${projectId}/libro$`));
  await expect(page.getByRole("heading", { level: 1, name: `Control ${runId}` })).toBeVisible();
});

test("un capítulo con texto sin guardar pide confirmación antes de salir por la cabecera", async ({ page }) => {
  const projectId = await createProject(page, `Aviso ${runId}`);
  const capitulo = `Capítulo aviso ${runId}`;
  await page.goto(`/proyectos/${projectId}/estructura`);
  await addNode(page, "Capítulo", capitulo);
  await page.goto(`/proyectos/${projectId}/libro`);
  await page.getByRole("link", { name: capitulo, exact: true }).click();
  await page.getByLabel("Texto del capítulo").fill("Texto que no debe perderse.");

  page.once("dialog", (dialog) => void dialog.dismiss());
  await page.getByRole("navigation", { name: "Principal" }).getByRole("link", { name: "Manuscritos", exact: true }).click();
  await expect(page.getByLabel("Texto del capítulo")).toHaveValue("Texto que no debe perderse.");
  await expect(page).toHaveURL(/\/libro\/\d+$/);
});
