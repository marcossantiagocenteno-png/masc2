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
  await page.getByLabel("Título").fill(`Manuscrito de A ${runId}`);
  await page.getByLabel("Texto de la versión 1").fill("Texto exclusivo de la novela A.");
  await page.getByRole("button", { name: "Crear manuscrito" }).click();
  await expect(page.getByRole("link", { name: `Manuscrito de A ${runId}`, exact: true })).toBeVisible();
  const projectAUrl = page.url();

  // Proyecto B: no debe mostrar nada de A.
  await createProject(page, nameB);
  await expect(page.getByRole("heading", { level: 1, name: nameB })).toBeVisible();
  await expect(page.getByText(`Manuscrito de A ${runId}`)).toHaveCount(0);
  await page.getByLabel("Título").fill(`Manuscrito de B ${runId}`);
  await page.getByLabel("Texto de la versión 1").fill("Texto exclusivo de la novela B.");
  await page.getByRole("button", { name: "Crear manuscrito" }).click();
  await expect(page.getByRole("link", { name: `Manuscrito de B ${runId}`, exact: true })).toBeVisible();

  // La biblioteca lista ambos proyectos.
  await page.goto("/proyectos");
  await expect(page.getByRole("link", { name: nameA })).toBeVisible();
  await expect(page.getByRole("link", { name: nameB })).toBeVisible();

  // Archivar A: confirmación, y sus textos siguen legibles.
  await page.goto(projectAUrl);
  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: "Archivar proyecto" }).click();
  await expect(page.getByRole("status")).toHaveText(/Proyecto archivado/);
  await expect(page.getByText("El proyecto está archivado. Restáuralo para añadir manuscritos.")).toBeVisible();
  await expect(page.getByRole("link", { name: `Manuscrito de A ${runId}`, exact: true })).toBeVisible();

  // Aparece en el filtro de archivados y no en los activos.
  await page.goto("/proyectos");
  await expect(page.getByRole("link", { name: nameA })).toHaveCount(0);
  await page.getByRole("button", { name: "Archivados" }).click();
  await expect(page.getByRole("link", { name: nameA })).toBeVisible();

  // Restaurar: vuelve a estar activo.
  await page.getByRole("link", { name: nameA }).click();
  await page.getByRole("button", { name: "Restaurar proyecto" }).click();
  await expect(page.getByText("Proyecto restaurado.")).toBeVisible();
  await expect(page.getByLabel("Título")).toBeVisible();
});
