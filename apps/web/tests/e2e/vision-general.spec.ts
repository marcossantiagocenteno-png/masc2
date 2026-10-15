import { expect, test, type Page } from "@playwright/test";

/**
 * Visión general de la novela (F1): la premisa es el punto de partida, la sinopsis ya no se muestra, los géneros
 * se eligen de un catálogo con «Otro», y las directrices guardan solo lo que el autor decide.
 * Cada prueba crea su propia novela.
 */

const runId = `vg-${Date.now().toString(36)}`;

async function createProject(page: Page, name: string): Promise<number> {
  await page.goto("/proyectos");
  await page.getByLabel("Nombre de la novela").fill(name);
  await page.getByRole("button", { name: "Crear proyecto" }).click();
  await expect(page).toHaveURL(/\/proyectos\/\d+$/);
  return Number(page.url().match(/\/proyectos\/(\d+)/)?.[1]);
}

test("la premisa es el primer campo y la sinopsis de trabajo no se muestra", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await createProject(page, `Premisa ${runId}`);
  await expect(page.getByLabel("Sinopsis de trabajo")).toHaveCount(0);

  const premisa = await page.getByLabel("Premisa", { exact: true }).boundingBox();
  const generos = await page.getByRole("group", { name: "Géneros" }).boundingBox();
  expect(premisa && generos && premisa.y < generos.y).toBeTruthy();
});

test("los géneros se eligen en varias casillas y «Otro» conserva su texto aunque se deseleccione otro género", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await createProject(page, `Géneros ${runId}`);

  await page.getByRole("checkbox", { name: "Misterio e investigación" }).check();
  await page.getByRole("checkbox", { name: "Otro", exact: true }).check();
  // Sin nombre, «Otro» no se guarda y el aviso lo explica antes de tocar el servidor.
  await page.getByRole("button", { name: "Guardar visión general" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Escribe el nombre del género" })).toBeVisible();

  await page.getByLabel("Nombre del género").fill("Gótico costumbrista");
  await page.getByRole("button", { name: "Guardar visión general" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Visión general guardada." })).toBeVisible();

  await page.reload();
  await expect(page.getByRole("checkbox", { name: "Misterio e investigación" })).toBeChecked();
  await expect(page.getByRole("checkbox", { name: "Otro", exact: true })).toBeChecked();
  await expect(page.getByLabel("Nombre del género")).toHaveValue("Gótico costumbrista");

  await page.getByRole("checkbox", { name: "Misterio e investigación" }).uncheck();
  await page.getByRole("button", { name: "Guardar visión general" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Visión general guardada." })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("checkbox", { name: "Misterio e investigación" })).not.toBeChecked();
  await expect(page.getByLabel("Nombre del género")).toHaveValue("Gótico costumbrista");
});

test("las directrices solo guardan lo que el autor decide: «Sin decidir» no impone ningún valor", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await createProject(page, `Directrices ${runId}`);

  await page.getByLabel("Persona gramatical").selectOption("primera");
  await page.getByLabel("Tiempo verbal").selectOption("pasado");
  await page.getByLabel("Voz narrativa").fill("Seca, con frases cortas.");
  await page.getByRole("button", { name: "Guardar directrices" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Directrices guardadas." })).toBeVisible();

  await page.reload();
  await expect(page.getByLabel("Persona gramatical")).toHaveValue("primera");
  await expect(page.getByLabel("Tiempo verbal")).toHaveValue("pasado");
  await expect(page.getByLabel("Voz narrativa")).toHaveValue("Seca, con frases cortas.");
  await expect(page.getByLabel("Focalización")).toHaveValue("");
  await expect(page.getByLabel("Punto de vista")).toHaveValue("");
});

test("guardar directrices no cambia la premisa ni los géneros", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await createProject(page, `Independencia ${runId}`);
  await page.getByLabel("Premisa", { exact: true }).fill(`Una premisa estable ${runId}.`);
  await page.getByRole("checkbox", { name: "Terror" }).check();
  await page.getByRole("button", { name: "Guardar visión general" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Visión general guardada." })).toBeVisible();

  await page.getByLabel("Voz narrativa").fill("Una voz nueva.");
  await page.getByRole("button", { name: "Guardar directrices" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Directrices guardadas." })).toBeVisible();

  await page.reload();
  await expect(page.getByLabel("Premisa", { exact: true })).toHaveValue(`Una premisa estable ${runId}.`);
  await expect(page.getByRole("checkbox", { name: "Terror" })).toBeChecked();
});
