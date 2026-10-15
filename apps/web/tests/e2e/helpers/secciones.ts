import { expect, type Page } from "@playwright/test";

/**
 * Personajes, lugares, trama, cronología y estructura viven en la visión general de la novela, cada una en su ancla.
 * Las pruebas llegan a ellas por el ancla, igual que el índice de la visión general.
 */
const ANCLA: Record<string, string> = {
  Personajes: "personajes",
  Lugares: "lugares",
  "Trama y misterios": "trama",
  Cronología: "cronologia",
  Estructura: "estructura",
};

/** Lleva a una sección de la novela. «Manuscrito» sigue siendo una pestaña; el resto son anclas de la visión general. */
export async function section(page: Page, name: string): Promise<void> {
  const ancla = ANCLA[name];
  if (!ancla) {
    await page.getByRole("navigation", { name: "Secciones de la novela" }).getByRole("link", { name, exact: true }).click();
    return;
  }
  const base = page.url().match(/\/proyectos\/\d+/)?.[0];
  if (!base) throw new Error(`no hay novela en la URL: ${page.url()}`);
  await page.goto(`${base}#${ancla}`);
  await expect(page.locator(`#${ancla}`)).toBeVisible();
}
