import { expect, test } from "@playwright/test";

const runId = Date.now().toString(36);
const CONTENT = "Dijo que que no lo sabía.\nLa lluvia caía sobre el tejado. Nadie se movió.";

test("analizar un fragmento muestra diagnósticos separados sin modificar el texto", async ({ page }) => {
  // Crear manuscrito y abrir la versión 1.
  await page.goto("/manuscritos");
  await page.getByLabel("Título del manuscrito").fill(`Análisis E2E ${runId}`);
  await page.getByLabel("Contenido de la versión 1").fill(CONTENT);
  await page.getByRole("button", { name: "Crear manuscrito" }).click();
  await expect(page).toHaveURL(/\/manuscritos\/\d+$/);
  await page.getByRole("link", { name: "Versión 1" }).click();
  await expect(page.locator("#contenido-version")).toHaveValue(CONTENT);

  // Sin selección, el análisis no se lanza.
  await page.getByRole("button", { name: "Analizar la selección del contenido" }).click();
  await expect(page.getByText("Selecciona un fragmento en el contenido de la versión")).toBeVisible();

  // Analizar el contenido completo seleccionado.
  await page.locator("#contenido-version").evaluate((element) => {
    const textarea = element as HTMLTextAreaElement;
    textarea.focus();
    textarea.setSelectionRange(0, textarea.value.length);
  });
  await page.getByRole("button", { name: "Analizar la selección del contenido" }).click();

  // El proveedor por defecto es el simulado, y así se indica.
  await expect(page.getByRole("note").filter({ hasText: "ANALIZADOR SIMULADO" })).toBeVisible();

  // Problemas verificables: la repetición «que que», y nada más.
  const verifiable = page.getByRole("region", { name: /Problemas verificables/ });
  await expect(verifiable.getByText("«que que»")).toBeVisible();
  await expect(verifiable).toContainText("Verificación determinista");

  // Observaciones literarias del simulador: siempre marcadas como simuladas.
  const observations = page.getByRole("region", { name: /Observaciones literarias/ });
  await expect(observations).toContainText("[Simulado]");
  await expect(observations).toContainText("SIMULADO");

  // Preferencias de gusto, en su propia sección.
  await expect(page.getByRole("region", { name: /Preferencias de gusto \(no son errores\)/ })).toBeVisible();

  // El texto de la versión no ha cambiado.
  await expect(page.locator("#contenido-version")).toHaveValue(CONTENT);

  // El análisis persiste: tras recargar sigue guardado con esta versión.
  await page.reload();
  await expect(page.getByLabel("Análisis guardado")).toHaveValue(/\d+/);
  await expect(page.getByRole("note").filter({ hasText: "ANALIZADOR SIMULADO" })).toBeVisible();
  await expect(page.locator("#contenido-version")).toHaveValue(CONTENT);
});
