import { expect, test, type Locator, type Page } from "@playwright/test";
import { section } from "./helpers/secciones";

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

  await section(page, "Personajes");
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

test("en una versión, el bloque Ejecutado cuenta los análisis realmente guardados", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const projectId = await createProject(page, `Ejecutado ${runId}`);
  const title = `Versión ${runId}`;
  await page.getByLabel("Título", { exact: true }).fill(title);
  await page.getByLabel("Texto de la versión 1").fill("Frase breve para analizar. Otra frase de prueba.");
  await page.getByRole("button", { name: "Crear manuscrito", exact: true }).click();
  // La visión general no lista los manuscritos: el último trabajo del proyecto lleva al recién creado.
  await page.getByRole("link", { name: `Abrir «${title}» para escribir o revisar`, exact: true }).click();
  await page.getByRole("link", { name: "Versión 1", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/proyectos/${projectId}/manuscritos/\\d+/versiones/\\d+$`));

  await expect(contexto(page).getByText("Esta versión no tiene análisis ejecutados.")).toBeVisible();

  // Un análisis real del analizador simulado, sobre la selección del contenido.
  // El texto llega del servidor después de la navegación: marcar antes lo perdería, porque el campo se rellena luego.
  await expect(page.locator("#contenido-version")).toHaveValue("Frase breve para analizar. Otra frase de prueba.");
  await page.evaluate(() => {
    const el = document.getElementById("contenido-version") as HTMLTextAreaElement;
    el.focus();
    el.setSelectionRange(0, 17);
  });
  await page.getByRole("button", { name: "Usar la selección del contenido" }).click();
  await page.getByRole("button", { name: "Analizar la selección del contenido" }).click();
  await expect(page.getByLabel("Análisis guardado")).toBeVisible();

  await expect(valorDe(page, "Análisis")).toHaveText("1 en total · 1 simulados · 0 con proveedor real");
  await expect(valorDe(page, "Último")).toContainText("analizador simulado, no es una IA");
  await expect(valorDe(page, "Fragmento")).toHaveText("caracteres 0–17");
});

async function addNode(page: Page, kind: "Acto" | "Capítulo" | "Escena", title: string, parentLabel?: string) {
  await page.getByRole("form", { name: "Añadir a la estructura" }).getByLabel("Tipo", { exact: true }).selectOption({ label: kind });
  if (parentLabel) await page.getByRole("form", { name: "Añadir a la estructura" }).getByLabel("Dentro de", { exact: true }).selectOption({ label: parentLabel });
  await page.getByRole("form", { name: "Añadir a la estructura" }).getByLabel("Título (opcional)", { exact: true }).fill(title);
  await page.getByRole("button", { name: `Añadir ${kind.toLowerCase()}`, exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "añadid" })).toBeVisible();
}

test("las advertencias salen de lo guardado y lo que no existe aparece como no disponible", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const projectId = await createProject(page, `Avisos ${runId}`);
  await page.goto(`/proyectos/${projectId}/estructura`);
  await addNode(page, "Acto", `Acto ${runId}`);
  await addNode(page, "Capítulo", `Cap ${runId}`, `Acto: Acto ${runId}`);
  await addNode(page, "Escena", `Escena sin texto ${runId}`, `Capítulo: Cap ${runId}`);

  await page.goto(`/proyectos/${projectId}`);
  await expect(contexto(page).getByText("1 escena sin texto.")).toBeVisible();
  await expect(valorDe(page, "Escenas con texto")).toHaveText("0 de 1");

  // Lo que el modelo no comprueba se nombra, sin cifras.
  await expect(contexto(page).getByText("Continuidad entre escenas")).toBeVisible();
  await expect(contexto(page).getByText("Función de cada capítulo")).toBeVisible();
});
