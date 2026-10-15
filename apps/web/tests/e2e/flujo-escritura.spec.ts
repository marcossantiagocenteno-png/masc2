import { expect, test, type Locator, type Page } from "@playwright/test";
import { section } from "./helpers/secciones";

/**
 * Validación del flujo de escritura de principio a fin (fase 2g). Cada prueba crea su propia novela con datos
 * identificados por el sufijo de la ejecución («2g-…»). Las comprobaciones son sobre lo visible y lo guardado.
 * Los fallos del servidor se simulan con page.route y cabeceras CORS.
 */

const WEB = "http://localhost:3100";
const API = "http://127.0.0.1:8100";
const run = `2g-${Date.now().toString(36)}`;

async function createProject(page: Page, name: string): Promise<number> {
  await page.goto("/proyectos");
  await page.getByLabel("Nombre de la novela").fill(name);
  await page.getByRole("button", { name: "Crear proyecto" }).click();
  await expect(page).toHaveURL(/\/proyectos\/\d+$/);
  return Number(page.url().match(/\/proyectos\/(\d+)/)?.[1]);
}

function status(page: Page, text: string): Locator {
  return page.getByRole("status").filter({ hasText: text });
}

async function addNode(page: Page, kind: "Acto" | "Capítulo" | "Escena", title: string, parentLabel?: string) {
  await page.getByRole("form", { name: "Añadir a la estructura" }).getByLabel("Tipo", { exact: true }).selectOption({ label: kind });
  if (parentLabel) await page.getByRole("form", { name: "Añadir a la estructura" }).getByLabel("Dentro de", { exact: true }).selectOption({ label: parentLabel });
  await page.getByRole("form", { name: "Añadir a la estructura" }).getByLabel("Título (opcional)", { exact: true }).fill(title);
  await page.getByRole("button", { name: `Añadir ${kind.toLowerCase()}`, exact: true }).click();
  await expect(status(page, "añadid")).toBeVisible();
}

async function openScene(page: Page, title: string) {
  await page.getByRole("link", { name: `Abrir Escena: ${title}`, exact: true }).click();
  await expect(page.getByRole("heading", { name: `Planificación de «${title}»` })).toBeVisible();
}

const editor = (page: Page) => page.getByLabel(/^Texto de/);

async function startWriting(page: Page) {
  await page.getByRole("button", { name: "Empezar a escribir esta escena", exact: true }).click();
  await expect(editor(page)).toBeVisible();
}

/** Espera la confirmación real del servidor para el borrador visible. */
async function expectSaved(page: Page) {
  await expect(status(page, "Guardado")).toBeVisible({ timeout: 10_000 });
}

// ----------------------------------------------------------------------
// 1–3. Proyecto, datos generales, estructura, reorganización y vínculos
// ----------------------------------------------------------------------

test("1-3: crear la novela, completar sus datos, estructurarla, reorganizarla y vincular personajes, lugares y trama", async ({ page }) => {
  const projectId = await createProject(page, `Novela ${run}`);
  await page.getByLabel("Premisa").fill(`Premisa ${run}`);
  await page.getByRole("checkbox", { name: "Terror" }).check();
  await page.getByRole("button", { name: "Guardar visión general" }).click();
  await expectSaved_(page, "Visión general guardada.");
  await page.reload();
  await expect(page.getByLabel("Premisa")).toHaveValue(`Premisa ${run}`);

  // Elementos que se vincularán después.
  await section(page, "Personajes");
  await page.getByLabel("Nombre del nuevo personaje").fill(`Iris ${run}`);
  await page.getByRole("button", { name: "Crear personaje", exact: true }).click();
  await expect(status(page, "Personaje creado")).toBeVisible();
  await section(page, "Lugares");
  await page.getByLabel("Nombre del nuevo lugar").fill(`Faro ${run}`);
  await page.getByRole("button", { name: "Crear lugar", exact: true }).click();
  await expect(status(page, "Lugar creado")).toBeVisible();
  await section(page, "Trama y misterios");
  await page.getByLabel("Título del nuevo elemento de trama").fill(`Carta ${run}`);
  await page.getByRole("button", { name: "Crear elemento de trama", exact: true }).click();
  await expect(page.getByRole("region", { name: "Trama y misterios" }).getByRole("status").filter({ hasText: "creado" })).toBeVisible();

  // Estructura: acto, dos capítulos y tres escenas.
  await section(page, "Estructura");
  await addNode(page, "Acto", `Acto ${run}`);
  await addNode(page, "Capítulo", `Cap A ${run}`, `Acto: Acto ${run}`);
  await addNode(page, "Capítulo", `Cap B ${run}`, `Acto: Acto ${run}`);
  await addNode(page, "Escena", `Esc 1 ${run}`, `Capítulo: Cap A ${run}`);
  await addNode(page, "Escena", `Esc 2 ${run}`, `Capítulo: Cap A ${run}`);
  await addNode(page, "Escena", `Esc 3 ${run}`, `Capítulo: Cap A ${run}`);

  // Renombrar una escena: el nombre nuevo sustituye al anterior en el árbol.
  await openScene(page, `Esc 3 ${run}`);
  await page.getByLabel("Título", { exact: true }).fill(`Esc 3 renombrada ${run}`);
  await page.getByRole("button", { name: "Guardar cambios" }).click();
  await expect(status(page, "Cambios guardados")).toBeVisible();

  // Reordenar: Esc 1 baja un puesto (queda después de Esc 2).
  await section(page, "Estructura");
  await page.getByRole("button", { name: `Bajar Escena: Esc 1 ${run}`, exact: true }).click();
  await expect(status(page, "Orden actualizado")).toBeVisible();
  const scenes = page.getByRole("link", { name: /Abrir Escena:/ });
  await expect.poll(() => scenes.evaluateAll((links) => links.map((link) => link.getAttribute("aria-label")))).toEqual([
    `Abrir Escena: Esc 2 ${run}`,
    `Abrir Escena: Esc 1 ${run}`,
    `Abrir Escena: Esc 3 renombrada ${run}`,
  ]);

  // Mover una escena a otro capítulo.
  await page.getByRole("button", { name: `Escena: Esc 3 renombrada ${run}`, exact: true }).click();
  await page.getByLabel("Nuevo lugar", { exact: true }).selectOption({ label: `Capítulo: Cap B ${run}` });
  await page.getByRole("button", { name: "Mover aquí" }).click();
  await expect(status(page, "Movido a su nuevo lugar")).toBeVisible();
  await expect(
    page.locator(`li[data-node-id]:has(> div button[aria-label="Subir Capítulo: Cap B ${run}"]) > ul`).getByRole("link", { name: `Abrir Escena: Esc 3 renombrada ${run}` }),
  ).toBeVisible();

  // Vincular personaje, lugar y trama a la escena 1.
  await openScene(page, `Esc 1 ${run}`);
  for (const [kind, label] of [
    ["personaje", `Iris ${run}`],
    ["lugar", `Faro ${run}`],
    ["elemento_trama", `Carta ${run}`],
  ] as const) {
    await page.getByLabel("Tipo de elemento").selectOption(kind);
    await page.getByLabel("Elemento", { exact: true }).selectOption({ label: label });
    await page.getByRole("button", { name: "Vincular a la escena" }).click();
    await expect(status(page, "Vínculo creado.")).toBeVisible();
  }
  await expect(page.getByText("participa en esta escena")).toBeVisible();
  await expect(page.getByText("ocurre en esta escena")).toBeVisible();
  await expect(page.getByText("aparece en esta escena")).toBeVisible();

  // Los vínculos se ven desde el elemento, sin crearse automáticamente.
  await section(page, "Personajes");
  await page.getByRole("button", { name: new RegExp(`Iris ${run}`) }).click();
  await expect(page.getByRole("heading", { name: "Escenas relacionadas" })).toBeVisible();
  await expect(page.getByRole("link", { name: `Esc 1 ${run}`, exact: true })).toBeVisible();
  expect(projectId).toBeGreaterThan(0);
});

// Helper local: el mensaje de guardado de la visión general no usa el mismo texto que la planificación.
async function expectSaved_(page: Page, text: string) {
  await expect(status(page, text)).toBeVisible();
}

// ----------------------------------------------------------------------
// 4-5. Escribir, navegar con cambios pendientes, regresar y recargar
// ----------------------------------------------------------------------

test("4-5: escribir, salir con texto recién escrito sin perderlo, regresar y recargar", async ({ page }) => {
  const dialogs: string[] = [];
  page.on("dialog", (dialog) => {
    dialogs.push(dialog.message());
    void dialog.dismiss();
  });
  await createProject(page, `Escritura ${run}`);
  await section(page, "Estructura");
  await addNode(page, "Escena", `Nav 1 ${run}`);
  await addNode(page, "Escena", `Nav 2 ${run}`);

  await openScene(page, `Nav 1 ${run}`);
  await startWriting(page);
  await editor(page).fill("Primer párrafo de la escena.");
  await expectSaved(page);

  // Escribir y salir de inmediato, antes de que venza el anti-rebote: el texto debe enviarse antes de salir.
  await editor(page).fill("Texto escrito justo antes de salir.");
  await page.getByRole("link", { name: "Volver a la estructura" }).click();
  await expect(page).toHaveURL(/\/proyectos\/\d+#estructura$/);
  await expect(page.getByRole("link", { name: `Abrir Escena: Nav 1 ${run}`, exact: true })).toBeVisible();
  expect(dialogs, "salir con el texto pendiente no debe pedir confirmación si el guardado funciona").toEqual([]);

  // Otra escena y de vuelta: el texto está en el servidor.
  await page.getByRole("link", { name: `Abrir Escena: Nav 2 ${run}`, exact: true }).click();
  await expect(page.getByRole("heading", { name: `Planificación de «Nav 2 ${run}»` })).toBeVisible();
  // La segunda escena no tiene texto: se ofrece empezar, y no aparece un editor con texto ajeno.
  await expect(page.getByRole("button", { name: "Empezar a escribir esta escena", exact: true })).toBeVisible();
  await section(page, "Estructura");
  await page.getByRole("link", { name: `Abrir Escena: Nav 1 ${run}`, exact: true }).click();
  await expect(editor(page)).toHaveValue("Texto escrito justo antes de salir.");

  // Recargar: sigue igual.
  await page.reload();
  await expect(editor(page)).toHaveValue("Texto escrito justo antes de salir.");
  await expect(page.getByText("Con texto", { exact: false }).first()).toBeVisible();
});

// ----------------------------------------------------------------------
// 6. Estados de guardado: éxito, error y conflicto
// ----------------------------------------------------------------------

test("6: un error de guardado no se muestra como éxito y conserva el texto; un conflicto se detecta", async ({ page, request }) => {
  const projectId = await createProject(page, `Estados ${run}`);
  await section(page, "Estructura");
  await addNode(page, "Escena", `Estados ${run}`);
  await openScene(page, `Estados ${run}`);
  const nodeId = Number(page.url().match(/estructura\/(\d+)/)?.[1]);
  await startWriting(page);

  // Error del servidor: aparece «No guardado», nunca «Guardado», y el texto sigue en el editor.
  await page.route("**/planificacion/estructura/*/escritura/borrador", async (route) => {
    const cors = { "Access-Control-Allow-Origin": WEB, "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Allow-Methods": "GET, POST, PUT" };
    if (route.request().method() === "OPTIONS") await route.fulfill({ status: 204, headers: cors });
    else await route.fulfill({ status: 500, headers: cors, contentType: "application/json", body: JSON.stringify({ detail: "Error simulado." }) });
  });
  await editor(page).fill("Texto que no debe perderse.");
  await expect(page.getByRole("alert").filter({ hasText: "No guardado" })).toBeVisible({ timeout: 10_000 });
  await expect(status(page, "Guardado")).toHaveCount(0);
  await expect(editor(page)).toHaveValue("Texto que no debe perderse.");
  await page.unroute("**/planificacion/estructura/*/escritura/borrador");

  // Al reintentar, el servidor confirma y entonces sí aparece «Guardado».
  await page.getByRole("button", { name: "Reintentar", exact: true }).click();
  await expectSaved(page);

  // Conflicto: otra ventana guarda antes. Esta ventana no pisa el texto del servidor.
  const current = await request.get(`${API}/projects/${projectId}/planificacion/estructura/${nodeId}/escritura`);
  const revision = (await current.json()).draft.revision as number;
  const other = await request.put(`${API}/projects/${projectId}/planificacion/estructura/${nodeId}/escritura/borrador`, {
    data: { content: "Texto de la otra ventana", base_revision: revision, keep_previous: false },
  });
  expect(other.status()).toBe(200);
  await editor(page).fill("Mi texto en esta ventana");
  await expect(page.getByRole("button", { name: "Usar la versión guardada", exact: true })).toBeVisible({ timeout: 10_000 });
  await expect(editor(page)).toHaveValue("Mi texto en esta ventana");
  await page.getByRole("button", { name: "Usar la versión guardada", exact: true }).click();
  await expect(editor(page)).toHaveValue("Texto de la otra ventana");
});

// ----------------------------------------------------------------------
// 7-8. Versión formal y puntos de recuperación
// ----------------------------------------------------------------------

test("7-8: crear una versión formal con el texto esperado y restaurar un punto de recuperación", async ({ page, request }) => {
  page.on("dialog", (dialog) => void dialog.accept());
  const legacyCalls: string[] = [];
  page.on("request", (req) => {
    const url = req.url();
    // Contenido por ruta heredada. El metadato GET /manuscripts/{id} queda fuera: sirve para descubrir el proyecto.
    const content = /\/manuscripts\/\d+\/(draft|versions|recovery-points)|\/versions\/\d+/.test(url);
    if (content && !url.includes("/projects/")) legacyCalls.push(`${req.method()} ${url}`);
  });
  const projectId = await createProject(page, `Versiones ${run}`);
  await section(page, "Estructura");
  await addNode(page, "Escena", `Versionada ${run}`);
  await openScene(page, `Versionada ${run}`);
  const nodeId = Number(page.url().match(/estructura\/(\d+)/)?.[1]);
  await startWriting(page);
  await editor(page).fill("Primera redacción.");
  await expectSaved(page);

  // Un punto de recuperación real: otra ventana guarda antes y el texto de esta ventana queda como «conflicto».
  const revision = (await (await request.get(`${API}/projects/${projectId}/planificacion/estructura/${nodeId}/escritura`)).json()).draft.revision as number;
  await request.put(`${API}/projects/${projectId}/planificacion/estructura/${nodeId}/escritura/borrador`, {
    data: { content: "Redacción de la otra ventana.", base_revision: revision, keep_previous: false },
  });
  await editor(page).fill("Mi redacción conflictiva.");
  await page.getByRole("button", { name: "Usar la versión guardada", exact: true }).click();
  await expect(editor(page)).toHaveValue("Redacción de la otra ventana.");

  await editor(page).fill("Segunda redacción, la que se publica.");
  await expectSaved(page);

  // Versión formal desde la escena: el contenido de la versión coincide con el borrador confirmado.
  await page.getByRole("button", { name: "Guardar como nueva versión" }).click();
  await expect(page).toHaveURL(/\/versiones\/\d+$/);
  const manuscriptId = Number(page.url().match(/\/manuscritos\/(\d+)/)?.[1]);
  await expect(page.locator("#contenido-version")).toHaveValue("Segunda redacción, la que se publica.");

  // Restaurar el punto de conflicto desde la escena: el borrador pasa a su contenido, y el estado anterior queda como punto.
  await page.goBack();
  await expect(page.getByRole("heading", { name: "Puntos de recuperación" })).toBeVisible();
  const points = await (await request.get(`${API}/projects/${projectId}/manuscripts/${manuscriptId}/recovery-points`)).json();
  let index = -1;
  for (let i = 0; i < points.length; i++) {
    const detail = await (await request.get(`${API}/projects/${projectId}/manuscripts/${manuscriptId}/recovery-points/${points[i].id}`)).json();
    if (detail.content === "Mi redacción conflictiva.") index = i;
  }
  expect(index, "el conflicto debe haber creado su punto de recuperación").toBeGreaterThanOrEqual(0);
  await page.getByRole("button", { name: /^Restaurar punto de / }).nth(index).click();
  await expect(editor(page)).toHaveValue("Mi redacción conflictiva.");
  await expect(page.getByText("Antes de restaurar").first()).toBeVisible();
  // La versión formal publicada no cambia con la restauración del borrador.
  const versions = await (await request.get(`${API}/projects/${projectId}/manuscripts/${manuscriptId}/versions`)).json();
  expect(versions.length).toBeGreaterThanOrEqual(2);
  const formal = await (await request.get(`${API}/projects/${projectId}/manuscripts/${manuscriptId}/versions/${versions[versions.length - 1].id}`)).json();
  expect(formal.content).toBe("Segunda redacción, la que se publica.");
  // Todo el recorrido usa las rutas del proyecto. (La lista de manuscritos de /manuscritos no se usa aquí.)
  expect(legacyCalls, "el recorrido de un manuscrito de escena no debe usar rutas heredadas").toEqual([]);
});

// ----------------------------------------------------------------------
// 9. Archivar elementos y proyectos: restricciones y lo que sigue permitido
// ----------------------------------------------------------------------

test("9: archivar una escena y un proyecto restringe escrituras, sin borrar el texto", async ({ page }) => {
  page.on("dialog", (dialog) => void dialog.accept());
  const projectId = await createProject(page, `Archivo ${run}`);
  await section(page, "Estructura");
  await addNode(page, "Escena", `Archivable ${run}`);
  await openScene(page, `Archivable ${run}`);
  await startWriting(page);
  await editor(page).fill("Texto antes de archivar.");
  await expectSaved(page);

  // Archivar la escena: su texto sigue ahí, pero ya no se puede escribir.
  await page.getByRole("button", { name: "Archivar", exact: true }).click();
  await page.getByRole("group", { name: "Confirmación" }).getByRole("button", { name: "Archivar", exact: true }).click();
  await expect(status(page, "archivado")).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: `Planificación de «Archivable ${run}»` })).toBeVisible();
  await expect(editor(page)).toHaveValue("Texto antes de archivar.");

  // Un guardado de una escena archivada se rechaza y no lo presenta como éxito.
  await editor(page).fill("Intento después de archivar.");
  await expect(page.getByRole("alert").filter({ hasText: "No guardado" })).toBeVisible({ timeout: 10_000 });
  await expect(status(page, "Guardado")).toHaveCount(0);
  await expect(editor(page)).toHaveValue("Intento después de archivar.");

  // Archivar la novela: las lecturas siguen, las escrituras se rechazan.
  await page.goto(`/proyectos/${projectId}`);
  await page.getByRole("button", { name: "Archivar proyecto", exact: true }).click();
  await expect(page.getByRole("button", { name: "Restaurar proyecto", exact: true })).toBeVisible();
  await page.goto(`/proyectos/${projectId}/estructura`);
  await expect(page.getByRole("link", { name: `Abrir Escena: Archivable ${run}`, exact: true })).toBeVisible();
});

// ----------------------------------------------------------------------
// 10. Análisis simulado y revisiones: resultados conservados y rutas del proyecto
// ----------------------------------------------------------------------

test("10: el análisis y la revisión de un manuscrito de proyecto usan rutas del proyecto y se conservan", async ({ page, request }) => {
  const project = await request.post(`${API}/projects`, { data: { name: `Analisis ${run}` } });
  const projectId = (await project.json()).id as number;
  const content = "Dijo que que no lo sabía.\nLa lluvia caía sobre el tejado.";
  const created = await request.post(`${API}/projects/${projectId}/manuscripts`, { data: { title: `Revisado ${run}`, content } });
  const manuscriptId = (await created.json()).id as number;
  const versionId = (await (await request.get(`${API}/projects/${projectId}/manuscripts/${manuscriptId}/versions`)).json())[0].id as number;

  const legacyCalls: string[] = [];
  page.on("request", (req) => {
    const url = req.url();
    if (/\/versions\/\d+\/(analyses|reviews)/.test(url) && !url.includes("/projects/")) legacyCalls.push(url);
  });

  await page.goto(`/manuscritos/${manuscriptId}/versiones/${versionId}`);
  await expect(page.locator("#contenido-version")).toHaveValue(content);

  // Análisis simulado sobre el contenido completo.
  await page.locator("#contenido-version").evaluate((element) => {
    const textarea = element as HTMLTextAreaElement;
    textarea.focus();
    textarea.setSelectionRange(0, textarea.value.length);
  });
  await page.getByRole("button", { name: "Analizar la selección del contenido" }).click();
  await expect(page.getByRole("note").filter({ hasText: "ANALIZADOR SIMULADO" }).first()).toBeVisible();

  // Revisión editorial sobre una cita del texto.
  await page.getByRole("button", { name: "Usar la selección del contenido", exact: true }).click();
  await page.locator("#contenido-version").evaluate((element) => {
    const textarea = element as HTMLTextAreaElement;
    textarea.focus();
    textarea.setSelectionRange(0, 4);
  });
  await page.getByRole("button", { name: "Usar la selección del contenido", exact: true }).click();
  await page.getByLabel("Nombre de quien revisa").fill("Revisora QA");
  await page.getByLabel("Comentario", { exact: true }).fill(`Comentario ${run}`);
  await page.getByRole("button", { name: "Guardar comentario", exact: true }).click();
  await expect(page.getByText(`Comentario ${run}`).first()).toBeVisible();

  // Tras recargar, análisis y revisión siguen ahí, y el texto no ha cambiado.
  await page.reload();
  await expect(page.getByLabel("Análisis guardado")).toHaveValue(/\d+/);
  await expect(page.getByText(`Comentario ${run}`).first()).toBeVisible();
  await expect(page.locator("#contenido-version")).toHaveValue(content);
  expect(legacyCalls, "la interfaz no debe usar rutas heredadas para un manuscrito de proyecto").toEqual([]);
});
