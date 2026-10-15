import { expect, test, type APIRequestContext, type Locator, type Page } from "@playwright/test";

/**
 * Recomendación de estructura (F2): ranking con motivos, elección de modelo, etapas propuestas que se editan,
 * aceptan o rechazan. Aceptar crea un acto provisional de origen IA; nunca cambia el canon.
 * Cada prueba crea su propia novela.
 */

const API = "http://127.0.0.1:8100";
const runId = `rec-${Date.now().toString(36)}`;
const PREMISA = `Premisa ${runId}: una archivista descubre registros alterados.`;

async function createProject(page: Page, name: string): Promise<number> {
  await page.goto("/proyectos");
  await page.getByLabel("Nombre de la novela").fill(name);
  await page.getByRole("button", { name: "Crear proyecto" }).click();
  await expect(page).toHaveURL(/\/proyectos\/\d+$/);
  return Number(page.url().match(/\/proyectos\/(\d+)/)?.[1]);
}

/** Datos del autor para el ranking, preparados por API para que la prueba no dependa del orden de la interfaz. */
async function prepararDatos(request: APIRequestContext, projectId: number, puntoDeVista?: string) {
  const base = `${API}/projects/${projectId}/planificacion`;
  const premise = await request.patch(`${base}/narrativa`, { data: { premise: PREMISA } });
  expect(premise.status()).toBe(200);
  const directrices = await request.put(`${base}/directrices`, {
    data: {
      voz: null, persona: null, tiempo_verbal: null, tipo_narrador: null,
      punto_de_vista: puntoDeVista ?? null, focalizacion: null,
      estilo: null, intencion: null, limites: null, instrucciones: null,
    },
  });
  expect(directrices.status()).toBe(200);
}

function modelo(page: Page, nombre: string): Locator {
  return page.getByRole("article").filter({ hasText: nombre });
}

function lote(page: Page, numero: number): Locator {
  return page.locator("h4", { hasText: new RegExp(`^Lote ${numero}:`) }).locator("xpath=following-sibling::ol[1]");
}

test("el ranking muestra motivos, y un punto de vista de un personaje pone Siete puntos primero", async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const projectId = await createProject(page, `Ranking ${runId}`);
  await prepararDatos(request, projectId, "un_personaje");

  await page.goto(`/proyectos/${projectId}/estructura`);
  await expect(page.getByRole("heading", { name: "Modelos, del más al menos pertinente" })).toBeVisible();

  await expect(page.getByRole("article").first()).toContainText("1. Siete puntos (Dan Wells)");
  await expect(page.getByRole("article").first()).toContainText("Tu punto de vista es un solo personaje");
  await expect(page.getByRole("article").first()).toContainText("Inferencia de una regla");
  // Cada modelo explica su pertinencia, lo que favorece y sus límites.
  await expect(modelo(page, "Pirámide de Freytag")).toContainText("Limitaciones.");
  await expect(modelo(page, "Save the Cat!")).toContainText("Está pensado para guion de cine");
  // Los datos usados se ven tal cual se guardaron.
  await expect(page.getByRole("blockquote").filter({ hasText: PREMISA })).toBeVisible();
  await expect(page.locator("dd").filter({ hasText: /^Un personaje$/ })).toBeVisible();
});

test("sin datos, los modelos empiezan por el orden de referencia y lo dice", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const projectId = await createProject(page, `Sin datos ${runId}`);
  await page.goto(`/proyectos/${projectId}/estructura`);
  await expect(modelo(page, "Pirámide de Freytag").first()).toContainText("1. Pirámide de Freytag");
  await expect(page.getByText("Sin datos que lo distingan").first()).toBeVisible();
  await expect(page.getByText("Escribe la premisa", { exact: false })).toBeVisible();
});

test("elegir, generar, editar y aceptar crea un acto provisional de origen IA y no toca el canon", async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const projectId = await createProject(page, `Propuestas ${runId}`);
  await prepararDatos(request, projectId, "varios_personajes");
  const base = `${API}/projects/${projectId}/planificacion`;
  const narrativaAntes = await (await request.get(`${base}/narrativa`)).json();
  const directricesAntes = await (await request.get(`${base}/directrices`)).json();

  await page.goto(`/proyectos/${projectId}/estructura`);
  await modelo(page, "Pirámide de Freytag").getByRole("button", { name: "Elegir este modelo" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Modelo elegido: Pirámide de Freytag" })).toBeVisible();

  await page.getByRole("button", { name: "Generar etapas de «Pirámide de Freytag (cinco actos)»" }).click();
  await expect(page.getByRole("heading", { name: /Lote 1: Pirámide de Freytag/ })).toBeVisible();
  const etapas = lote(page, 1).locator("li");
  await expect(etapas).toHaveCount(5);
  await expect(etapas.nth(0)).toContainText("Pendiente");
  // La generación no crea actos: la estructura del servidor sigue vacía.
  expect(await (await request.get(`${base}/estructura`)).json()).toEqual([]);
  // Mientras haya etapas pendientes del modelo, no se genera otro lote.
  await expect(page.getByRole("button", { name: /Generar etapas de/ })).toBeDisabled();

  // Editable: el título y el resumen los escribe el autor.
  await etapas.nth(0).getByRole("button", { name: "Editar" }).click();
  await etapas.nth(0).getByLabel("Título del acto").fill("Planteamiento de la archivista");
  await etapas.nth(0).getByLabel("Resumen (opcional, lo escribes tú)").fill("Lo que el autor decide.");
  await etapas.nth(0).getByRole("button", { name: "Guardar cambios" }).click();
  await expect(etapas.nth(0)).toContainText("1. Planteamiento de la archivista");

  // Aceptable: el acto aparece como provisional de origen IA, no como canon.
  await etapas.nth(0).getByRole("button", { name: "Aceptar como acto provisional" }).click();
  await expect(page.getByRole("status").filter({ hasText: "No es canon" })).toBeVisible();
  await expect(etapas.nth(0)).toContainText("Aceptada");
  const nodos = await (await request.get(`${base}/estructura`)).json();
  expect(nodos).toHaveLength(1);
  expect(nodos[0]).toMatchObject({ title: "Planteamiento de la archivista", kind: "acto", estado: "provisional", origen: "ia", approved_decision_id: null });

  // La segunda etapa ya se puede aceptar: la anterior está decidida.
  await expect(etapas.nth(1).getByRole("button", { name: "Aceptar como acto provisional" })).toBeEnabled();

  // Rechazable: se rechaza sin borrar la fila.
  await etapas.nth(1).getByRole("button", { name: "Rechazar" }).click();
  await expect(etapas.nth(1)).toContainText("Rechazada");
  await expect(etapas).toHaveCount(5);

  // El canon no cambió: premisa, directrices y personajes siguen igual.
  expect(await (await request.get(`${base}/narrativa`)).json()).toEqual(narrativaAntes);
  expect(await (await request.get(`${base}/directrices`)).json()).toEqual(directricesAntes);
});

test("en 360 px la recomendación se lee sin desbordamiento horizontal", async ({ page, request }) => {
  await page.setViewportSize({ width: 360, height: 740 });
  const projectId = await createProject(page, `Movil ${runId}`);
  await prepararDatos(request, projectId, "un_personaje");
  await page.goto(`/proyectos/${projectId}/estructura`);
  await expect(page.getByRole("heading", { name: "Modelos, del más al menos pertinente" })).toBeVisible();
  const desbordamiento = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(desbordamiento, "desbordamiento horizontal a 360 px").toBeLessThanOrEqual(0);
});

test("cambiar la premisa cambia las pistas que se muestran, y la recomendación sigue siendo provisional", async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const projectId = await createProject(page, `Premisa viva ${runId}`);
  await prepararDatos(request, projectId);
  await page.goto(`/proyectos/${projectId}/estructura`);
  await expect(page.getByText("Lo que escribiste")).toBeVisible();
  await expect(page.getByText("Pistas que sugiere la premisa")).toBeVisible();
  await expect(page.getByText("Posible presión de tiempo o plazo")).toHaveCount(0);
  await expect(page.getByRole("note")).toContainText("Recomendación provisional");

  const cambio = await request.patch(`${API}/projects/${projectId}/planificacion/narrativa`, {
    data: { premise: "Una ciudad sitiada tiene quince días antes de que el agua se agote, y un traidor oculta las reservas." },
  });
  expect(cambio.status()).toBe(200);
  await page.reload();
  await expect(page.getByText("Posible presión de tiempo o plazo")).toBeVisible();
  await expect(page.getByText("Pistas que sugiere la premisa")).toBeVisible();
  // Las inferencias se muestran como hipótesis con confianza baja, nunca como canon.
  await expect(page.getByText("Inferencia · confianza baja").first()).toBeVisible();
  await expect(page.getByRole("note")).toContainText("Recomendación provisional");
});
