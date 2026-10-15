import { expect, test } from "@playwright/test";

const runId = Date.now().toString(36);

async function createProject(page: import("@playwright/test").Page, name: string) {
  await page.goto("/proyectos");
  await page.getByLabel("Nombre de la novela").fill(name);
  await page.getByRole("button", { name: "Crear proyecto" }).click();
  await expect(page).toHaveURL(/\/proyectos\/\d+$/);
}

test("dos proyectos son independientes y el archivado no borra nada", async ({ page }) => {
  const nameA = `Novela A ${runId}`;
  const nameB = `Novela B ${runId}`;

  // Proyecto A con un manuscrito propio.
  await createProject(page, nameA);
  await page.getByRole("region", { name: "Nuevo manuscrito en este proyecto" }).getByLabel("Título", { exact: true }).fill(`Manuscrito de A ${runId}`);
  await page.getByLabel("Texto de la versión 1").fill("Texto exclusivo de la novela A.");
  await page.getByRole("button", { name: "Crear manuscrito" }).click();
  // La visión general no lista los manuscritos: el último trabajo enlaza con el recién creado.
  await expect(page.getByRole("link", { name: `Abrir «Manuscrito de A ${runId}» para escribir o revisar`, exact: true })).toBeVisible();
  const projectAUrl = page.url();

  // Proyecto B: no debe mostrar nada de A.
  await createProject(page, nameB);
  await expect(page.getByRole("heading", { level: 1, name: nameB })).toBeVisible();
  await expect(page.getByText(`Manuscrito de A ${runId}`)).toHaveCount(0);
  await page.getByRole("region", { name: "Nuevo manuscrito en este proyecto" }).getByLabel("Título", { exact: true }).fill(`Manuscrito de B ${runId}`);
  await page.getByLabel("Texto de la versión 1").fill("Texto exclusivo de la novela B.");
  await page.getByRole("button", { name: "Crear manuscrito" }).click();
  await expect(page.getByRole("link", { name: `Abrir «Manuscrito de B ${runId}» para escribir o revisar`, exact: true })).toBeVisible();

  // La biblioteca lista ambos proyectos.
  await page.goto("/proyectos");
  await page.setViewportSize({ width: 1440, height: 900 });
  const lista = page.getByRole("complementary", { name: "Lista de novelas" });
  await expect(lista.getByRole("link", { name: nameA, exact: true })).toBeVisible();
  await expect(lista.getByRole("link", { name: nameB, exact: true })).toBeVisible();
  // La biblioteca no repite las novelas activas: se abren desde la lista lateral.
  await expect(page.getByRole("main").getByRole("link", { name: nameA })).toHaveCount(0);

  // Archivar A: confirmación, y sus textos siguen legibles.
  await page.goto(projectAUrl);
  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: "Archivar proyecto" }).click();
  await expect(page.getByRole("status")).toHaveText(/Proyecto archivado/);
  await expect(page.getByText("El proyecto está archivado. Restáuralo para añadir manuscritos.")).toBeVisible();
  await expect(page.getByRole("link", { name: `Abrir «Manuscrito de A ${runId}» para escribir o revisar`, exact: true })).toBeVisible();

  // Aparece en el filtro de archivados y no en los activos.
  await page.goto("/proyectos");
  await expect(page.getByRole("main").getByRole("link", { name: nameA })).toHaveCount(0);
  await page.getByRole("button", { name: "Archivados" }).click();
  await expect(page.getByRole("main").getByRole("link", { name: nameA })).toBeVisible();

  // Restaurar: vuelve a estar activo.
  await page.getByRole("main").getByRole("link", { name: nameA }).click();
  await page.getByRole("button", { name: "Restaurar proyecto" }).click();
  await expect(page.getByText("Proyecto restaurado.")).toBeVisible();
  await expect(page.getByRole("region", { name: "Nuevo manuscrito en este proyecto" }).getByLabel("Título", { exact: true })).toBeVisible();
});
