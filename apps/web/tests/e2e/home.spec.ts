import { expect, test } from "@playwright/test";

test("la página inicial muestra el título y el estado de la fase 0", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { level: 1, name: "Novel Engine" })).toBeVisible();
  await expect(page.getByText("Fase 0 · Fundamentos")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Pendiente para fases siguientes" })).toBeVisible();
});

test("la página declara idioma español y no provoca desbordamiento horizontal en móvil", async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 800 });
  await page.goto("/");

  await expect(page.locator("html")).toHaveAttribute("lang", "es");
  const overflows = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(overflows).toBe(false);
});
