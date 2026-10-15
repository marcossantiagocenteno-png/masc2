import { expect, test, type Locator, type Page } from "@playwright/test";

/**
 * Manuscritos dentro del espacio de trabajo (fase 3b, etapa 3): acceso desde la novela, redirecciones de las rutas
 * antiguas, sección «Sin proyecto», exclusión de los manuscritos de escena del listado global y aviso ante una ruta
 * de otra novela. Cada prueba crea sus propios datos identificados por la ejecución.
 */

const runId = `m3-${Date.now().toString(36)}`;

async function createProject(page: Page, name: string): Promise<number> {
  await page.goto("/proyectos");
  await page.getByLabel("Nombre de la novela").fill(name);
  await page.getByRole("button", { name: "Crear proyecto" }).click();
  await expect(page).toHaveURL(/\/proyectos\/\d+$/);
  return Number(page.url().match(/\/proyectos\/(\d+)/)?.[1]);
}

/** Crea un manuscrito desde el resumen de la novela. */
async function createManuscriptInProject(page: Page, projectId: number, title: string) {
  await page.goto(`/proyectos/${projectId}`);
  await page.getByLabel("Título", { exact: true }).fill(title);
  await page.getByLabel("Texto de la versión 1").fill(`Texto de ${title}.`);
  await page.getByRole("button", { name: "Crear manuscrito", exact: true }).click();
  // La visión general no lista los manuscritos: el último trabajo del proyecto enlaza con el recién creado.
  await expect(abrirUltimo(page, title)).toBeVisible();
}

function abrirUltimo(page: Page, title: string): Locator {
  return page.getByRole("link", { name: `Abrir «${title}» para escribir o revisar`, exact: true });
}

function manuscriptIdFrom(url: string): number {
  return Number(url.match(/\/manuscritos\/(\d+)/)?.[1]);
}

async function addNode(page: Page, kind: "Acto" | "Capítulo" | "Escena", title: string, parentLabel?: string) {
  await page.getByRole("form", { name: "Añadir a la estructura" }).getByLabel("Tipo", { exact: true }).selectOption({ label: kind });
  if (parentLabel) await page.getByRole("form", { name: "Añadir a la estructura" }).getByLabel("Dentro de", { exact: true }).selectOption({ label: parentLabel });
  await page.getByRole("form", { name: "Añadir a la estructura" }).getByLabel("Título (opcional)", { exact: true }).fill(title);
  await page.getByRole("button", { name: `Añadir ${kind.toLowerCase()}`, exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "añadid" })).toBeVisible();
}

function region(page: Page, name: string): Locator {
  return page.getByRole("region", { name, exact: true });
}

test("la novela da acceso a sus manuscritos y su ruta antigua redirige a la ruta de la novela", async ({ page }) => {
  const projectId = await createProject(page, `Acceso ${runId}`);
  const title = `Borrador ${runId}`;
  await createManuscriptInProject(page, projectId, title);

  // Desde el espacio de trabajo: el manuscrito se abre dentro de la novela.
  await abrirUltimo(page, title).click();
  await expect(page).toHaveURL(new RegExp(`/proyectos/${projectId}/manuscritos/\\d+$`));
  await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
  const manuscriptId = manuscriptIdFrom(page.url());

  await page.goto(`/proyectos/${projectId}`);
  // El bloque «Manuscritos del proyecto» ya no está en la navegación de la novela (F1): el acceso es «Manuscrito».
  await expect(
    page.getByRole("navigation", { name: "Secciones de la novela" }).getByRole("link", { name: "Manuscritos del proyecto", exact: true }),
  ).toHaveCount(0);
  // La visión general tampoco muestra la lista; el manuscrito sigue accesible desde «Manuscrito».
  await expect(page.getByRole("heading", { name: "Manuscritos del proyecto", exact: true })).toHaveCount(0);
  await expect(page.getByRole("navigation", { name: "Secciones de la novela" }).getByRole("link", { name: "Manuscrito", exact: true })).toBeVisible();

  // La ruta antigua no pierde el manuscrito: redirige a su ruta dentro de la novela.
  await page.goto(`/manuscritos/${manuscriptId}`);
  await expect(page).toHaveURL(`/proyectos/${projectId}/manuscritos/${manuscriptId}`);
  await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
});

test("un manuscrito sin proyecto sigue en su ruta y aparece solo en «Sin proyecto»", async ({ page }) => {
  const title = `Suelto ${runId}`;
  await page.goto("/manuscritos");
  await page.getByLabel("Título del manuscrito").fill(title);
  await page.getByLabel("Contenido de la versión 1").fill(`Texto suelto ${runId}.`);
  await page.getByRole("button", { name: "Crear manuscrito", exact: true }).click();
  await expect(page).toHaveURL(/\/manuscritos\/\d+$/);
  await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();

  await page.goto("/manuscritos");
  await expect(region(page, "Sin proyecto").getByRole("link", { name: title, exact: true })).toBeVisible();
  await expect(region(page, "Manuscritos de las novelas").getByRole("link", { name: title, exact: true })).toHaveCount(0);
});

test("los manuscritos de escena no aparecen en el listado global", async ({ page }) => {
  const projectId = await createProject(page, `Escena ${runId}`);
  const sceneTitle = `Escena oculta ${runId}`;
  await page.goto(`/proyectos/${projectId}/estructura`);
  await addNode(page, "Acto", `Acto ${runId}`);
  await addNode(page, "Capítulo", `Cap ${runId}`, `Acto: Acto ${runId}`);
  await addNode(page, "Escena", sceneTitle, `Capítulo: Cap ${runId}`);

  // Empezar a escribir la escena crea su manuscrito, que es el texto de la escena.
  await page.getByRole("link", { name: `Abrir Escena: ${sceneTitle}`, exact: true }).click();
  await page.getByRole("button", { name: "Empezar a escribir esta escena", exact: true }).click();
  await expect(page.getByLabel(/^Texto de/)).toBeVisible();

  await page.goto("/manuscritos");
  await expect(page.getByRole("heading", { name: "Sin proyecto" })).toBeVisible();
  await expect(page.getByRole("main").getByRole("link", { name: sceneTitle, exact: true })).toHaveCount(0);
});

test("una ruta de otra novela no muestra el contenido del manuscrito", async ({ page }) => {
  const ownerId = await createProject(page, `Dueña ${runId}`);
  const title = `Ajeno ${runId}`;
  await createManuscriptInProject(page, ownerId, title);
  await abrirUltimo(page, title).click();
  await expect(page).toHaveURL(new RegExp(`/proyectos/${ownerId}/manuscritos/\\d+$`));
  const manuscriptId = manuscriptIdFrom(page.url());

  const otherId = await createProject(page, `Otra ${runId}`);
  await page.goto(`/proyectos/${otherId}/manuscritos/${manuscriptId}`);
  await expect(page.getByRole("alert").filter({ hasText: "pertenece a otra novela" })).toBeVisible();
  await expect(page.getByLabel("Contenido de la nueva versión")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Abrir el manuscrito en su ubicación" })).toHaveAttribute(
    "href",
    `/proyectos/${ownerId}/manuscritos/${manuscriptId}`,
  );
});
