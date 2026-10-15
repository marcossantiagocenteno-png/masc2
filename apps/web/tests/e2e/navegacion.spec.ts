import { expect, test, type Page } from "@playwright/test";

/**
 * Navegación de la novela (E1): la visión general reúne las secciones, las rutas antiguas redirigen a su ancla y los
 * enlaces profundos con ?seleccionado= llegan a su colección. Cada prueba crea su propia novela.
 */

const API = "http://127.0.0.1:8100";
const runId = `nav-${Date.now().toString(36)}`;

async function createProject(page: Page, name: string): Promise<number> {
  await page.goto("/proyectos");
  await page.getByLabel("Nombre de la novela").fill(name);
  await page.getByRole("button", { name: "Crear proyecto" }).click();
  await expect(page).toHaveURL(/\/proyectos\/\d+$/);
  return Number(page.url().match(/\/proyectos\/(\d+)/)?.[1]);
}

// «titulo» es el encabezado de la sección; «etiqueta» es el texto del índice de la visión general.
const SECCIONES = [
  { segmento: "personajes", ancla: "personajes", titulo: "Personajes", etiqueta: "Personajes" },
  { segmento: "lugares", ancla: "lugares", titulo: "Lugares", etiqueta: "Lugares" },
  { segmento: "trama", ancla: "trama", titulo: "Trama y misterios", etiqueta: "Trama" },
  { segmento: "cronologia", ancla: "cronologia", titulo: "Cronología", etiqueta: "Cronología" },
  { segmento: "estructura", ancla: "estructura", titulo: "Estructura", etiqueta: "Estructura" },
] as const;

test("la navegación de la novela tiene solo Manuscrito y Visión general", async ({ page }) => {
  const projectId = await createProject(page, `Pestañas ${runId}`);
  await page.goto(`/proyectos/${projectId}`);
  const nav = page.getByRole("navigation", { name: "Secciones de la novela" });
  await expect(nav.getByRole("link")).toHaveCount(2);
  await expect(nav.getByRole("link", { name: "Manuscrito", exact: true })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Visión general", exact: true })).toBeVisible();
});

test("la visión general tiene un índice que lleva a cada sección", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const projectId = await createProject(page, `Indice ${runId}`);
  await page.goto(`/proyectos/${projectId}`);
  const indice = page.getByRole("navigation", { name: "Secciones de la visión general" });
  for (const { ancla, etiqueta } of SECCIONES) {
    await expect(page.locator(`#${ancla}`)).toBeVisible();
    await expect(indice.getByRole("link", { name: etiqueta, exact: true })).toBeVisible();
  }
  await indice.getByRole("link", { name: "Manuscrito", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/proyectos/${projectId}/libro$`));
});

for (const { segmento, ancla, titulo } of SECCIONES) {
  test(`la ruta antigua /${segmento} redirige a la sección «${titulo}» de la visión general`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    const projectId = await createProject(page, `Redirige ${segmento} ${runId}`);
    await page.goto(`/proyectos/${projectId}/${segmento}`);
    await expect(page).toHaveURL(new RegExp(`/proyectos/${projectId}#${ancla}$`));
    await expect(page.locator(`#${ancla}`)).toBeVisible();
  });
}

test("un enlace antiguo con ?seleccionado= abre el personaje en su colección", async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const projectId = await createProject(page, `Profundo ${runId}`);
  const nombre = `Elegida ${runId}`;
  const creado = await request.post(`${API}/projects/${projectId}/planificacion/personajes`, { data: { name: nombre } });
  expect(creado.status()).toBe(201);
  const { id } = await creado.json();

  await page.goto(`/proyectos/${projectId}/personajes?seleccionado=${id}`);
  await expect(page).toHaveURL(new RegExp(`/proyectos/${projectId}\\?coleccion=personajes&seleccionado=${id}#personajes$`));
  await expect(page.getByRole("region", { name: "Personajes" }).getByLabel("Nombre", { exact: true })).toHaveValue(nombre);
});

test("el enlace de una escena a su personaje selecciona el personaje y no otro del mismo número", async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const projectId = await createProject(page, `Coleccion ${runId}`);
  const lugar = await request.post(`${API}/projects/${projectId}/planificacion/lugares`, { data: { name: `Lugar ${runId}` } });
  const personaje = await request.post(`${API}/projects/${projectId}/planificacion/personajes`, { data: { name: `Persona ${runId}` } });
  expect(lugar.status()).toBe(201);
  expect(personaje.status()).toBe(201);
  const idPersonaje: number = (await personaje.json()).id;

  // Un enlace que pide la colección de personajes con ese id no debe tocar la colección de lugares.
  await page.goto(`/proyectos/${projectId}?coleccion=personajes&seleccionado=${idPersonaje}#personajes`);
  await expect(page.getByRole("region", { name: "Personajes" }).getByLabel("Nombre", { exact: true })).toHaveValue(`Persona ${runId}`);
  await expect(page.getByRole("region", { name: "Lugares" }).getByText(`Persona ${runId}`)).toHaveCount(0);
});
