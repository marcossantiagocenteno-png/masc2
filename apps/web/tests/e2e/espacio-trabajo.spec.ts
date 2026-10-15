import { expect, test, type Page } from "@playwright/test";
import { section } from "./helpers/secciones";

/**
 * Espacio de trabajo (fase 3b, etapa 1): lista de novelas persistente, plegado en pantallas estrechas
 * y protección ante cambios sin guardar también desde la lista y la cabecera.
 * Cada prueba crea sus propias novelas. No hay esperas fijas.
 */

const runId = Date.now().toString(36);

async function createProject(page: Page, name: string) {
  await page.goto("/proyectos");
  await page.getByLabel("Nombre de la novela").fill(name);
  await page.getByRole("button", { name: "Crear proyecto" }).click();
  await expect(page).toHaveURL(/\/proyectos\/\d+$/);
  return page.url();
}

function novelList(page: Page) {
  return page.getByRole("complementary", { name: "Lista de novelas" });
}

test("la lista muestra la novela creada y marca la que está abierta", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const name = `Lista ${runId}`;
  await createProject(page, name);
  const link = novelList(page).getByRole("link", { name, exact: true });
  await expect(link).toBeVisible();
  await expect(link).toHaveAttribute("aria-current", "page");
});

test("en pantalla estrecha la lista se despliega, se cierra con Escape y devuelve el foco al botón", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 900 });
  const name = `Plegado ${runId}`;
  await createProject(page, name);

  const toggle = page.getByRole("button", { name: "Mostrar lista de proyectos" });
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expect(novelList(page).getByRole("link", { name, exact: true })).toBeHidden();

  await toggle.click();
  await expect(page.getByRole("button", { name: "Ocultar lista de proyectos" })).toHaveAttribute("aria-expanded", "true");
  await expect(novelList(page).getByRole("link", { name, exact: true })).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expect(toggle).toBeFocused();
});

test("cambiar de novela desde la lista o la cabecera con cambios sin guardar pide confirmación", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const otherName = `Destino ${runId}`;
  const currentName = `Origen ${runId}`;
  await createProject(page, otherName);
  await createProject(page, currentName);

  // Un personaje con texto sin guardar en la novela actual.
  await section(page, "Personajes");
  await page.getByLabel("Nombre del nuevo personaje").fill(`Pendiente ${runId}`);
  await page.getByRole("button", { name: "Crear personaje" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Personaje creado" })).toBeVisible();
  await page.getByLabel("Objetivos").fill("Cambio sin guardar");

  // Desde la lista: el aviso permite quedarse.
  page.once("dialog", (dialog) => void dialog.dismiss());
  await novelList(page).getByRole("link", { name: otherName, exact: true }).click();
  await expect(page.getByLabel("Objetivos")).toHaveValue("Cambio sin guardar");
  // Al quedarse, sigue en la misma novela, en la sección de personajes de la visión general.
  await expect(page).toHaveURL(/\/proyectos\/\d+#personajes$/);

  // Desde la cabecera: el mismo aviso protege el cambio.
  page.once("dialog", (dialog) => void dialog.dismiss());
  await page.getByRole("navigation", { name: "Principal" }).getByRole("link", { name: "Manuscritos", exact: true }).click();
  await expect(page.getByLabel("Objetivos")).toHaveValue("Cambio sin guardar");
  // Al quedarse, sigue en la misma novela, en la sección de personajes de la visión general.
  await expect(page).toHaveURL(/\/proyectos\/\d+#personajes$/);

  // Aceptar desde la lista: sí se sale a la otra novela.
  page.once("dialog", (dialog) => void dialog.accept());
  await novelList(page).getByRole("link", { name: otherName, exact: true }).click();
  await expect(page).toHaveURL(/\/proyectos\/\d+$/);
  await expect(page.getByRole("heading", { name: otherName })).toBeVisible();
});

test("en pantalla estrecha, elegir una novela de la lista pliega el panel", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 900 });
  const otherName = `Elegida ${runId}`;
  const currentName = `Abierta ${runId}`;
  await createProject(page, otherName);
  await createProject(page, currentName);

  // El nombre del botón cambia al abrirse («Ocultar…»): se localiza por la parte común.
  const toggle = page.getByRole("button", { name: /lista de proyectos/ });
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-expanded", "true");

  await novelList(page).getByRole("link", { name: otherName, exact: true }).click();
  await expect(page).toHaveURL(/\/proyectos\/\d+$/);
  await expect(page.getByRole("heading", { level: 1, name: otherName })).toBeVisible();
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
});
