import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * Modo proveedor real, con la API del proveedor simulada en el navegador.
 *
 * Solo se interceptan dos respuestas de la API local: el estado del proveedor
 * y el análisis. Ninguna petición sale del equipo hacia Anthropic. El resto del
 * flujo (manuscrito, versión y contenido) usa el backend real.
 */
const CONTENT = "La lluvia caía sobre el tejado. Nadie se movió.\n\nOtro párrafo que no debe enviarse.";
const FIRST_SENTENCE = "La lluvia caía sobre el tejado.";
const CORS = {
  "access-control-allow-origin": "http://localhost:3100",
  "access-control-allow-methods": "GET,POST,OPTIONS",
  "access-control-allow-headers": "content-type",
};

async function fulfillJson(route: Route, status: number, body: unknown) {
  if (route.request().method() === "OPTIONS") {
    await route.fulfill({ status: 204, headers: CORS });
    return;
  }
  await route.fulfill({ status, headers: CORS, contentType: "application/json", body: JSON.stringify(body) });
}

async function mockExternalProvider(page: Page): Promise<{ analysisBodies: unknown[] }> {
  const analysisBodies: unknown[] = [];
  const stored: unknown[] = [];

  await page.route("**/analysis/provider", (route) =>
    fulfillJson(route, 200, {
      configured: true,
      name: "anthropic",
      label: "Claude (Anthropic) · PROVEEDOR REAL",
      is_simulated: false,
      is_external: true,
      model_name: "modelo-de-prueba",
      reason: null,
    }),
  );

  await page.route(/\/versions\/\d+\/analyses$/, async (route) => {
    if (route.request().method() === "GET") {
      await fulfillJson(route, 200, stored);
      return;
    }
    analysisBodies.push(route.request().postDataJSON());
    const run = {
      id: 901,
      version_id: 1,
      fragment_start: 0,
      fragment_end: FIRST_SENTENCE.length,
      fragment_text: FIRST_SENTENCE,
      provider_name: "anthropic",
      provider_label: "Claude (Anthropic) · PROVEEDOR REAL",
      provider_simulated: false,
      model_name: "modelo-de-prueba",
      sent_external: true,
      created_at: "2026-10-14T10:00:00",
      findings: [
        {
          id: 1,
          category: "observacion_literaria",
          provenance: "proveedor",
          source_name: "anthropic",
          quote: "La lluvia caía",
          start_offset: 0,
          end_offset: 14,
          line_number: 1,
          explanation: "La imagen abre la escena con un fenómeno exterior.",
          effect: "Sitúa al lector antes de cualquier personaje.",
          certainty: "media",
          justification: "La cita contiene el sintagma que sostiene la observación.",
        },
      ],
    };
    stored.push(run);
    await fulfillJson(route, 201, run);
  });

  return { analysisBodies };
}

async function selectFirstSentence(page: Page) {
  await page.locator("#contenido-version").evaluate((element, length) => {
    const textarea = element as HTMLTextAreaElement;
    textarea.focus();
    textarea.setSelectionRange(0, length);
  }, FIRST_SENTENCE.length);
}

test("el proveedor real exige confirmar el fragmento exacto antes de enviarlo", async ({ page }) => {
  const runId = Date.now().toString(36);
  await page.goto("/manuscritos");
  await page.getByLabel("Título del manuscrito").fill(`Externo E2E ${runId}`);
  await page.getByLabel("Contenido de la versión 1").fill(CONTENT);
  await page.getByRole("button", { name: "Crear manuscrito" }).click();
  await expect(page).toHaveURL(/\/manuscritos\/\d+$/);
  await page.getByRole("link", { name: "Versión 1" }).click();
  await expect(page.locator("#contenido-version")).toHaveValue(CONTENT);

  const { analysisBodies } = await mockExternalProvider(page);
  await page.reload();
  await expect(page.locator("#contenido-version")).toHaveValue(CONTENT);

  // El aviso de proveedor externo aparece antes de cualquier análisis.
  await expect(page.getByRole("note").filter({ hasText: "Proveedor externo configurado: Anthropic" })).toBeVisible();

  // Sin selección: no se abre ninguna confirmación.
  await page.getByRole("button", { name: "Revisar envío a Anthropic del fragmento seleccionado" }).click();
  await expect(page.getByText("Selecciona un fragmento en el contenido de la versión")).toBeVisible();

  // Con selección: se muestra exactamente el fragmento, antes de enviar.
  await selectFirstSentence(page);
  await page.getByRole("button", { name: "Revisar envío a Anthropic del fragmento seleccionado" }).click();
  const dialog = page.getByRole("dialog", { name: "Confirmar envío a Anthropic" });
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText("Se envía únicamente este fragmento");
  await expect(dialog).toContainText("No se envían el manuscrito completo, otras versiones ni los comentarios.");
  await expect(dialog.locator("blockquote")).toHaveText(FIRST_SENTENCE);
  await expect(dialog.getByText("Otro párrafo que no debe enviarse.")).toHaveCount(0);

  // Sin marcar la casilla, no se puede enviar y no sale ninguna petición.
  const send = dialog.getByRole("button", { name: "Enviar a Anthropic y analizar" });
  await expect(send).toBeDisabled();
  expect(analysisBodies).toHaveLength(0);

  // Marcada la casilla, el envío lleva la autorización de esta petición.
  await dialog.getByRole("checkbox").check();
  await send.click();
  await expect.poll(() => analysisBodies.length).toBe(1);
  expect(analysisBodies[0]).toEqual({
    start_offset: 0,
    end_offset: FIRST_SENTENCE.length,
    external_authorization: { provider: "anthropic", scope: "fragmento_seleccionado", acknowledged: true },
  });

  // El resultado se identifica como proveedor real, no como simulado.
  await expect(page.getByRole("note").filter({ hasText: "ANÁLISIS CON PROVEEDOR REAL" })).toBeVisible();
  await expect(page.getByText("ANALIZADOR SIMULADO")).toHaveCount(0);
  await expect(page.getByText("Justificación:")).toBeVisible();

  // La autorización no se conserva: el paso de confirmación se cierra y la casilla vuelve a estar vacía.
  await expect(page.getByRole("dialog", { name: "Confirmar envío a Anthropic" })).toHaveCount(0);
  await selectFirstSentence(page);
  await page.getByRole("button", { name: "Revisar envío a Anthropic del fragmento seleccionado" }).click();
  await expect(page.getByRole("dialog").getByRole("checkbox")).not.toBeChecked();
  await page.getByRole("button", { name: "Cancelar" }).click();

  // El texto de la versión no ha cambiado.
  await expect(page.locator("#contenido-version")).toHaveValue(CONTENT);
});
