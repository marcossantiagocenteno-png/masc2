import { expect, test, type Locator, type Page } from "@playwright/test";

/**
 * Espacio de trabajo de planificación: recorridos principales sobre la API real.
 * Cada prueba crea su propia novela. No hay esperas fijas: se usan aserciones con reintento.
 */

const WEB = "http://localhost:3100";
const runId = Date.now().toString(36);

async function createProject(page: Page, name: string) {
  await page.goto("/proyectos");
  await page.getByLabel("Nombre de la novela").fill(name);
  await page.getByRole("button", { name: "Crear proyecto" }).click();
  await expect(page).toHaveURL(/\/proyectos\/\d+$/);
  return page.url();
}

async function section(page: Page, name: string) {
  await page.getByRole("navigation", { name: "Secciones de la novela" }).getByRole("link", { name, exact: true }).click();
}

function status(page: Page, text: string): Locator {
  return page.getByRole("status").filter({ hasText: text });
}

async function createCharacter(page: Page, name: string) {
  await section(page, "Personajes");
  await page.getByLabel("Nombre del nuevo personaje").fill(name);
  await page.getByRole("button", { name: "Crear personaje" }).click();
  await expect(status(page, "Personaje creado")).toBeVisible();
}

async function createPlace(page: Page, name: string) {
  await section(page, "Lugares");
  await page.getByLabel("Nombre del nuevo lugar").fill(name);
  await page.getByRole("button", { name: "Crear lugar" }).click();
  await expect(status(page, "Lugar creado")).toBeVisible();
}

async function addNode(page: Page, kind: "Acto" | "Capítulo" | "Escena", title: string, parentLabel?: string) {
  await page.getByLabel("Tipo", { exact: true }).selectOption({ label: kind });
  if (parentLabel) await page.getByLabel("Dentro de", { exact: true }).selectOption({ label: parentLabel });
  await page.getByLabel("Título (opcional)", { exact: true }).fill(title);
  await page.getByRole("button", { name: `Añadir ${kind.toLowerCase()}`, exact: true }).click();
  await expect(status(page, "añadid")).toBeVisible();
}

/** Simula un fallo del servidor en las escrituras de un personaje, con cabeceras CORS. */
async function failCharacterWrites(page: Page, detail: string) {
  await page.route("**/planificacion/personajes/*", async (route) => {
    const cors = { "Access-Control-Allow-Origin": WEB, "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH" };
    if (route.request().method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers: cors });
    } else if (route.request().method() === "PATCH") {
      await route.fulfill({ status: 500, headers: cors, contentType: "application/json", body: JSON.stringify({ detail }) });
    } else {
      await route.continue();
    }
  });
}

test("abrir una novela, ver su espacio de trabajo y editar su visión general", async ({ page }) => {
  await createProject(page, `Visión ${runId}`);
  await expect(page.getByText("Espacio de trabajo de la novela")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Secciones de la novela" }).getByRole("link", { name: "Trama y misterios" })).toBeVisible();

  // Advertencia honesta: estos campos no tienen protección de canon.
  await expect(page.getByText(/Todavía no tienen las protecciones de canon/)).toBeVisible();

  // Campos vacíos son válidos: guardar sin rellenar nada no está bloqueado.
  await page.getByLabel("Premisa").fill("Una casa que recuerda a quienes la habitan.");
  await page.getByLabel("Género").fill("Gótico");
  await page.getByLabel("Estado de desarrollo").selectOption("idea");
  await page.getByRole("button", { name: "Guardar visión general" }).click();
  await expect(status(page, "Visión general guardada.")).toBeVisible();

  await page.reload();
  await expect(page.getByLabel("Premisa")).toHaveValue("Una casa que recuerda a quienes la habitan.");
  await expect(page.getByLabel("Género")).toHaveValue("Gótico");
});

test("crear con solo un nombre, editar y archivar un personaje", async ({ page }) => {
  await createProject(page, `Personajes ${runId}`);
  const name = `Ana ${runId}`;
  await createCharacter(page, name);
  await expect(page.getByRole("button", { name: new RegExp(name) })).toBeVisible();

  // Completar el resto más adelante.
  await page.getByLabel("Objetivos").fill("Recuperar la casa de su madre.");
  await page.getByRole("button", { name: "Guardar cambios" }).click();
  await expect(status(page, "Cambios guardados.")).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: new RegExp(name) }).click();
  await expect(page.getByLabel("Objetivos")).toHaveValue("Recuperar la casa de su madre.");

  // Archivar: confirmación explícita, y el elemento sale de la lista activa.
  await page.getByRole("button", { name: "Archivar", exact: true }).click();
  const confirm = page.getByRole("group", { name: "Confirmación" });
  await expect(confirm).toContainText("No se borra");
  await confirm.getByRole("button", { name: "Archivar", exact: true }).click();
  await expect(status(page, "archivado")).toBeVisible();
  await expect(page.getByRole("button", { name: new RegExp(name) })).toHaveCount(0);

  await page.getByLabel("Mostrar archivados").check();
  await expect(page.getByRole("button", { name: new RegExp(name) })).toBeVisible();
  await expect(page.getByText("Archivado", { exact: true }).first()).toBeVisible();
});

test("construir actos, capítulos y escenas, reordenar sin cambiar su identidad", async ({ page }) => {
  await createProject(page, `Estructura ${runId}`);
  await section(page, "Estructura");
  await addNode(page, "Acto", `Acto ${runId}`);
  await addNode(page, "Capítulo", `Capítulo ${runId}`, `Acto: Acto ${runId}`);
  await addNode(page, "Escena", `Escena A ${runId}`, `Capítulo: Capítulo ${runId}`);
  await addNode(page, "Escena", `Escena B ${runId}`, `Capítulo: Capítulo ${runId}`);
  await addNode(page, "Escena", `Escena C ${runId}`, `Capítulo: Capítulo ${runId}`);

  const scenes = page.getByRole("link", { name: /Abrir Escena:/ });
  const order = () => scenes.evaluateAll((links) => links.map((link) => link.getAttribute("aria-label") ?? ""));
  expect(await order()).toEqual([
    `Abrir Escena: Escena A ${runId}`,
    `Abrir Escena: Escena B ${runId}`,
    `Abrir Escena: Escena C ${runId}`,
  ]);

  // Identidad antes de reordenar.
  const hrefB = await page.getByRole("link", { name: `Abrir Escena: Escena B ${runId}` }).getAttribute("href");

  // Subir la escena B: queda antes que la A. El id no cambia.
  await page.getByRole("button", { name: `Subir Escena: Escena B ${runId}` }).click();
  await expect(status(page, "Orden actualizado")).toBeVisible();
  await expect.poll(order).toEqual([
    `Abrir Escena: Escena B ${runId}`,
    `Abrir Escena: Escena A ${runId}`,
    `Abrir Escena: Escena C ${runId}`,
  ]);
  await page.reload();
  await expect(page.getByRole("link", { name: `Abrir Escena: Escena B ${runId}` })).toHaveAttribute("href", hrefB as string);
});

test("relacionar una escena con personajes y lugares, y retirar un vínculo", async ({ page }) => {
  await createProject(page, `Vínculos ${runId}`);
  await createCharacter(page, `Lucía ${runId}`);
  await createPlace(page, `Casa ${runId}`);
  await section(page, "Estructura");
  await addNode(page, "Escena", `Llegada ${runId}`);
  await page.getByRole("link", { name: `Abrir Escena: Llegada ${runId}` }).click();

  // Personaje → participa en la escena.
  await page.getByLabel("Tipo de elemento").selectOption("personaje");
  await page.getByLabel("Elemento", { exact: true }).selectOption({ label: `Lucía ${runId}` });
  await page.getByRole("button", { name: "Vincular a la escena" }).click();
  await expect(status(page, "Vínculo creado.")).toBeVisible();
  await expect(page.getByText(`Lucía ${runId}`, { exact: false }).first()).toBeVisible();
  await expect(page.getByText("participa en esta escena")).toBeVisible();

  // Lugar → ocurre en la escena.
  await page.getByLabel("Tipo de elemento").selectOption("lugar");
  await page.getByLabel("Elemento", { exact: true }).selectOption({ label: `Casa ${runId}` });
  await page.getByRole("button", { name: "Vincular a la escena" }).click();
  await expect(page.getByText("ocurre en esta escena")).toBeVisible();

  // Retirar el lugar: confirmación y el vínculo queda archivado.
  await page.getByRole("button", { name: `Quitar Casa ${runId} de esta escena` }).click();
  await page.getByRole("group", { name: "Confirmación" }).getByRole("button", { name: "Quitar vínculo" }).click();
  await expect(status(page, "Vínculo retirado")).toBeVisible();
  await expect(page.getByText("ocurre en esta escena")).toHaveCount(0);
});

test("aprobar como canon exige confirmación y editar un canónico también", async ({ page }) => {
  await createProject(page, `Canon ${runId}`);
  const name = `Canónica ${runId}`;
  await createCharacter(page, name);

  await page.getByRole("button", { name: "Aprobar como canon", exact: true }).click();
  const confirm = page.getByRole("group", { name: "Confirmación" });
  await expect(confirm.getByRole("button", { name: "Aprobar como canon" })).toBeDisabled();
  await confirm.getByLabel("Confirmo que este dato es canónico").check();
  await confirm.getByRole("button", { name: "Aprobar como canon" }).click();
  await expect(status(page, "Aprobado como canon.")).toBeVisible();
  await expect(page.getByText("Aprobado como canon", { exact: false }).first()).toBeVisible();

  // Editar un canónico: el guardado queda bloqueado hasta confirmar, y el cambio se registra.
  await page.getByLabel("Objetivos").fill("Un objetivo distinto");
  await expect(page.getByRole("button", { name: "Guardar cambios" })).toBeDisabled();
  await expect(page.getByText("Confirma el cambio al canon para poder guardar.")).toBeVisible();
  await page.getByRole("checkbox", { name: "Confirmo el cambio al canon" }).check();
  await page.getByRole("button", { name: "Guardar cambios" }).click();
  await expect(status(page, "vuelve a provisional")).toBeVisible();
  await expect(page.getByText("Cambiado tras la aprobación", { exact: false })).toBeVisible();
  await expect(page.getByText("Provisional", { exact: true }).first()).toBeVisible();
});

test("un error del servidor no pierde el texto escrito", async ({ page }) => {
  await createProject(page, `Errores ${runId}`);
  await createCharacter(page, `Error ${runId}`);
  await failCharacterWrites(page, "Error simulado del servidor.");

  await page.getByLabel("Objetivos").fill("Texto que no debe perderse.");
  await page.getByRole("button", { name: "Guardar cambios" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Error simulado del servidor." })).toBeVisible();
  await expect(status(page, "Cambios guardados.")).toHaveCount(0);
  await expect(page.getByLabel("Objetivos")).toHaveValue("Texto que no debe perderse.");

  await page.unroute("**/planificacion/personajes/*");
  await page.getByRole("button", { name: "Guardar cambios" }).click();
  await expect(status(page, "Cambios guardados.")).toBeVisible();
});

test("los datos de una novela no aparecen en otra", async ({ page }) => {
  await createProject(page, `Aislada A ${runId}`);
  await createCharacter(page, `Solo de A ${runId}`);
  await section(page, "Estructura");
  await addNode(page, "Escena", `Escena de A ${runId}`);
  const sceneHref = await page.getByRole("link", { name: /Abrir Escena:/ }).getAttribute("href");
  const projectA = page.url().split("/estructura")[0].replace(/\/$/, "");

  await createProject(page, `Aislada B ${runId}`);
  const projectB = page.url().replace(/\/$/, "");
  await section(page, "Personajes");
  await expect(page.getByRole("button", { name: new RegExp(`Solo de A ${runId}`) })).toHaveCount(0);

  // Una escena de A no se abre desde B.
  await page.goto(`${projectB}/estructura${sceneHref?.replace(/^.*\/estructura/, "") ?? ""}`);
  await expect(page.getByText("Esta escena no existe en esta novela.")).toBeVisible();

  // Desde A, el personaje sigue ahí.
  await page.goto(`${projectA}/personajes`);
  await expect(page.getByRole("button", { name: new RegExp(`Solo de A ${runId}`) })).toBeVisible();
});

test("cambiar de elemento o de sección no descarta cambios sin preguntar", async ({ page }) => {
  await createProject(page, `Aviso ${runId}`);
  await createCharacter(page, `Pendiente ${runId}`);
  await page.getByLabel("Objetivos").fill("Cambio sin guardar");

  // Cambiar de sección: el aviso permite quedarse.
  page.once("dialog", (dialog) => void dialog.dismiss());
  await section(page, "Lugares");
  await expect(page.getByLabel("Objetivos")).toHaveValue("Cambio sin guardar");

  // Aceptar el aviso: sí se sale.
  page.once("dialog", (dialog) => void dialog.accept());
  await section(page, "Lugares");
  await expect(page).toHaveURL(/\/lugares$/);
});

/** Fila (li) de un nodo del árbol, identificada por su botón «Subir» (nombre exacto y único en cada prueba). */
function rowOf(page: Page, label: string): Locator {
  return page.locator(`li[data-node-id]:has(> div button[aria-label="Subir ${label}"])`);
}

async function linkCharacterToScene(page: Page, character: string, scene: string) {
  await page.getByRole("link", { name: `Abrir Escena: ${scene}` }).click();
  await page.getByLabel("Tipo de elemento").selectOption("personaje");
  await page.getByLabel("Elemento", { exact: true }).selectOption({ label: character });
  await page.getByRole("button", { name: "Vincular a la escena" }).click();
  await expect(status(page, "Vínculo creado.")).toBeVisible();
}

test("mover una escena a otro capítulo conserva su identidad, sus vínculos y persiste al recargar", async ({ page }) => {
  await createProject(page, `Mover ${runId}`);
  const character = `Mara ${runId}`;
  await createCharacter(page, character);
  await section(page, "Estructura");
  await addNode(page, "Acto", `Acto M ${runId}`);
  await addNode(page, "Capítulo", `Cap 1 ${runId}`, `Acto: Acto M ${runId}`);
  await addNode(page, "Capítulo", `Cap 2 ${runId}`, `Acto: Acto M ${runId}`);
  await addNode(page, "Escena", `Escena M ${runId}`, `Capítulo: Cap 1 ${runId}`);
  const hrefBefore = await page.getByRole("link", { name: `Abrir Escena: Escena M ${runId}` }).getAttribute("href");
  await linkCharacterToScene(page, character, `Escena M ${runId}`);

  // Mover: la escena se selecciona, se elige el nuevo capítulo y se confirma con el botón.
  await section(page, "Estructura");
  await page.getByRole("button", { name: `Escena: Escena M ${runId}`, exact: true }).click();
  await page.getByLabel("Nuevo lugar", { exact: true }).selectOption({ label: `Capítulo: Cap 2 ${runId}` });
  await page.getByRole("button", { name: "Mover aquí" }).click();
  await expect(status(page, "Movido a su nuevo lugar")).toBeVisible();
  await expect(rowOf(page, `Capítulo: Cap 2 ${runId}`).locator(":scope > ul").getByRole("link", { name: `Abrir Escena: Escena M ${runId}` })).toBeVisible();
  await expect(rowOf(page, `Capítulo: Cap 1 ${runId}`).locator(":scope > ul")).toHaveCount(0);

  // Identidad: misma dirección de la escena, y el vínculo con el personaje sigue.
  await page.reload();
  await expect(rowOf(page, `Capítulo: Cap 2 ${runId}`).locator(":scope > ul").getByRole("link", { name: `Abrir Escena: Escena M ${runId}` })).toBeVisible();
  await expect(page.getByRole("link", { name: `Abrir Escena: Escena M ${runId}` })).toHaveAttribute("href", hrefBefore as string);
  await page.getByRole("link", { name: `Abrir Escena: Escena M ${runId}` }).click();
  await expect(page.getByText(`${character}`, { exact: false }).first()).toBeVisible();
  await expect(page.getByText("participa en esta escena")).toBeVisible();
});

test("un elemento canónico pide confirmación antes de moverse; cancelar devuelve el foco y no envía nada", async ({ page }) => {
  await createProject(page, `Canon mover ${runId}`);
  await section(page, "Estructura");
  await addNode(page, "Capítulo", `Cap X ${runId}`);
  await addNode(page, "Capítulo", `Cap Y ${runId}`);
  await addNode(page, "Escena", `Escena C ${runId}`, `Capítulo: Cap X ${runId}`);
  await page.getByRole("button", { name: `Escena: Escena C ${runId}`, exact: true }).click();
  await page.getByRole("button", { name: "Aprobar como canon", exact: true }).click();
  await page.getByRole("group", { name: "Confirmación" }).getByLabel("Confirmo que este dato es canónico").check();
  await page.getByRole("group", { name: "Confirmación" }).getByRole("button", { name: "Aprobar como canon" }).click();
  await expect(status(page, "Aprobado como canon.")).toBeVisible();

  let moveRequests = 0;
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().includes("/mover")) moveRequests += 1;
  });

  await page.getByLabel("Nuevo lugar", { exact: true }).selectOption({ label: `Capítulo: Cap Y ${runId}` });
  await page.getByRole("button", { name: "Mover aquí" }).click();
  const confirm = page.getByRole("group", { name: "Confirmación" });
  await expect(confirm).toContainText("canónico");
  await expect(confirm).toContainText(`«Escena C ${runId}»`);
  expect(moveRequests).toBe(0);

  await confirm.getByRole("button", { name: "Cancelar" }).click();
  await expect(page.getByRole("group", { name: "Confirmación" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Mover aquí" })).toBeFocused();
  expect(moveRequests).toBe(0);
  await expect(rowOf(page, `Capítulo: Cap X ${runId}`).locator(":scope > ul").getByRole("link", { name: `Abrir Escena: Escena C ${runId}` })).toBeVisible();

  await page.getByRole("button", { name: "Mover aquí" }).click();
  await page.getByRole("group", { name: "Confirmación" }).getByRole("checkbox").check();
  await page.getByRole("group", { name: "Confirmación" }).getByRole("button", { name: "Confirmar y continuar" }).click();
  await expect(status(page, "Movido a su nuevo lugar")).toBeVisible();
  expect(moveRequests).toBe(1);
  await expect(rowOf(page, `Capítulo: Cap Y ${runId}`).locator(":scope > ul").getByRole("link", { name: `Abrir Escena: Escena C ${runId}` })).toBeVisible();
});

test("un movimiento rechazado por el servidor no simula éxito y conserva la vista", async ({ page }) => {
  await createProject(page, `Rechazo ${runId}`);
  await section(page, "Estructura");
  await addNode(page, "Capítulo", `Cap R1 ${runId}`);
  await addNode(page, "Capítulo", `Cap R2 ${runId}`);
  await addNode(page, "Escena", `Escena R ${runId}`, `Capítulo: Cap R1 ${runId}`);
  await page.getByRole("button", { name: `Escena: Escena R ${runId}`, exact: true }).click();

  await page.route("**/planificacion/estructura/*/mover", async (route) => {
    const cors = { "Access-Control-Allow-Origin": WEB, "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Allow-Methods": "POST" };
    if (route.request().method() === "OPTIONS") await route.fulfill({ status: 204, headers: cors });
    else await route.fulfill({ status: 422, headers: cors, contentType: "application/json", body: JSON.stringify({ detail: "Error simulado: el destino no admite este movimiento." }) });
  });
  await page.getByLabel("Nuevo lugar", { exact: true }).selectOption({ label: `Capítulo: Cap R2 ${runId}` });
  await page.getByRole("button", { name: "Mover aquí" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Error simulado" })).toBeVisible();
  await expect(status(page, "Movido")).toHaveCount(0);
  await expect(rowOf(page, `Capítulo: Cap R1 ${runId}`).locator(":scope > ul").getByRole("link", { name: `Abrir Escena: Escena R ${runId}` })).toBeVisible();
  await expect(page.getByLabel("Nuevo lugar", { exact: true })).toHaveValue(/\d+/);
  await page.unroute("**/planificacion/estructura/*/mover");
});

test("una vista desactualizada se explica y se puede actualizar", async ({ page, request }) => {
  await createProject(page, `Vista ${runId}`);
  await section(page, "Estructura");
  await addNode(page, "Capítulo", `Cap V1 ${runId}`);
  await addNode(page, "Capítulo", `Cap V2 ${runId}`);
  const projectId = page.url().match(/proyectos\/(\d+)/)?.[1] as string;

  // Otra pestaña añade un capítulo: la vista de esta todavía no lo conoce.
  const apiBase = "http://127.0.0.1:8100";
  const created = await request.post(`${apiBase}/projects/${projectId}/planificacion/estructura`, {
    data: { kind: "capitulo", parent_id: null, title: `Cap nuevo ${runId}` },
  });
  expect(created.status()).toBe(201);

  await page.getByRole("button", { name: `Bajar Capítulo: Cap V1 ${runId}`, exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "No se ha cambiado nada" })).toBeVisible();
  await page.getByRole("button", { name: "Actualizar la estructura" }).click();
  await expect(page.getByRole("button", { name: `Subir Capítulo: Cap nuevo ${runId}`, exact: true })).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "No se ha cambiado nada" })).toHaveCount(0);
});

test("contraer y expandir ramas, y añadir el siguiente elemento desde su fila", async ({ page }) => {
  await createProject(page, `Ramas ${runId}`);
  await section(page, "Estructura");
  await addNode(page, "Acto", `Acto R ${runId}`);
  await addNode(page, "Capítulo", `Cap RR ${runId}`, `Acto: Acto R ${runId}`);
  const toggle = page.getByRole("button", { name: `Contraer Acto: Acto R ${runId}`, exact: true });
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await toggle.click();
  await expect(page.getByRole("button", { name: `Expandir Acto: Acto R ${runId}`, exact: true })).toHaveAttribute("aria-expanded", "false");
  await expect(page.getByRole("button", { name: `Subir Capítulo: Cap RR ${runId}`, exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: `Expandir Acto: Acto R ${runId}`, exact: true }).click();
  await expect(page.getByRole("button", { name: `Subir Capítulo: Cap RR ${runId}`, exact: true })).toBeVisible();

  // Añadir una escena desde la fila del capítulo: el padre queda elegido y el título enfocado.
  await page.getByRole("button", { name: `Añadir escena dentro de Capítulo: Cap RR ${runId}`, exact: true }).click();
  await expect(page.getByLabel("Dentro de", { exact: true })).toHaveValue(/\d+/);
  await expect(page.getByLabel("Título (opcional)", { exact: true })).toBeFocused();
  await page.getByLabel("Título (opcional)", { exact: true }).fill(`Escena rápida ${runId}`);
  await page.getByRole("button", { name: "Añadir escena", exact: true }).click();
  await expect(status(page, "Escena añadida")).toBeVisible();
  await expect(page.getByRole("link", { name: `Abrir Escena: Escena rápida ${runId}` })).toBeVisible();
});

test("desde una escena se abre su personaje y desde el personaje se llega a la escena", async ({ page }) => {
  await createProject(page, `Navegar ${runId}`);
  const character = `Nora ${runId}`;
  await createCharacter(page, character);
  await section(page, "Estructura");
  await addNode(page, "Escena", `Llegada N ${runId}`);
  await linkCharacterToScene(page, character, `Llegada N ${runId}`);

  await page.getByRole("link", { name: character, exact: true }).click();
  await expect(page).toHaveURL(/\/personajes\?seleccionado=\d+$/);
  await expect(page.getByLabel("Nombre", { exact: true })).toHaveValue(character);
  await expect(page.getByRole("heading", { name: "Escenas relacionadas" })).toBeVisible();
  await page.getByRole("link", { name: `Llegada N ${runId}`, exact: true }).click();
  await expect(page.getByRole("heading", { name: `Planificación de «Llegada N ${runId}»` })).toBeVisible();
});

test("la estructura y las fichas caben en una pantalla de 360 px sin desbordamiento horizontal", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 740 });
  await createProject(page, `Movil ${runId}`);
  await createCharacter(page, `Móvil ${runId}`);
  await section(page, "Estructura");
  await addNode(page, "Acto", `Acto con un nombre bastante largo para comprobar el ajuste ${runId}`);
  await addNode(page, "Escena", `Escena móvil ${runId}`, `Acto: Acto con un nombre bastante largo para comprobar el ajuste ${runId}`);
  const overflows = () => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(await overflows()).toBeLessThanOrEqual(0);
  await page.getByRole("button", { name: `Escena: Escena móvil ${runId}`, exact: true }).click();
  expect(await overflows()).toBeLessThanOrEqual(0);
  await section(page, "Personajes");
  await page.getByRole("button", { name: new RegExp(`Móvil ${runId}`) }).click();
  expect(await overflows()).toBeLessThanOrEqual(0);
});
