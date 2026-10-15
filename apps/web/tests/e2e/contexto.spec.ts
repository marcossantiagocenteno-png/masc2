import { expect, test, type Locator, type Page } from "@playwright/test";

/**
 * Columna de contexto de la novela (fase 3b, etapa 4). Cada prueba crea sus propios datos identificados por la ejecución.
 * Las cifras se comprueban contra lo guardado: nada se calcula ni se estima.
 */

const runId = `ctx-${Date.now().toString(36)}`;

async function createProject(page: Page, name: string): Promise<number> {
  await page.goto("/proyectos");
  await page.getByLabel("Nombre de la novela").fill(name);
  await page.getByRole("button", { name: "Crear proyecto" }).click();
  await expect(page).toHaveURL(/\/proyectos\/\d+$/);
  return Number(page.url().match(/\/proyectos\/(\d+)/)?.[1]);
}

function contexto(page: Page): Locator {
  return page.getByRole("region", { name: "Contexto de la novela" });
}

/** Valor de una fila de la lista de datos (dt → dd) dentro del contexto. */
function valorDe(page: Page, nombre: string): Locator {
  return contexto(page).locator("dt", { hasText: nombre }).locator("xpath=following-sibling::dd[1]");
}

test("dentro de una novela, el contexto muestra sus datos guardados y se actualiza al crear un personaje", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const projectId = await createProject(page, `Contexto ${runId}`);
  await expect(contexto(page)).toBeVisible();
  await expect(valorDe(page, "Personajes")).toHaveText("0");

  await page.getByRole("navigation", { name: "Secciones de la novela" }).getByRole("link", { name: "Personajes", exact: true }).click();
  await page.getByLabel("Nombre del nuevo personaje").fill(`Personaje ${runId}`);
  await page.getByRole("button", { name: "Crear personaje" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Personaje creado" })).toBeVisible();

  await page.goto(`/proyectos/${projectId}`);
  await expect(valorDe(page, "Personajes")).toHaveText("1");
  await expect(valorDe(page, "Escenas con texto")).toHaveText("Ninguna escena todavía");
});

test("por debajo de 1280 px el contexto queda plegado y se despliega con su botón", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 900 });
  await createProject(page, `Plegado ${runId}`);
  const toggle = page.getByRole("button", { name: "Mostrar contexto de la novela" });
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expect(valorDe(page, "Personajes")).toBeHidden();

  await toggle.click();
  await expect(page.getByRole("button", { name: "Ocultar contexto de la novela" })).toHaveAttribute("aria-expanded", "true");
  await expect(valorDe(page, "Personajes")).toBeVisible();
});

test("en la biblioteca de proyectos no hay columna de contexto", async ({ page }) => {
  await page.goto("/proyectos");
  await expect(page.getByRole("heading", { level: 1, name: "Proyectos" })).toBeVisible();
  await expect(contexto(page)).toHaveCount(0);
});
