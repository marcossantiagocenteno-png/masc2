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
  await page.getByRole("button", { name: `Añadir ${kind.toLowerCase()}` }).click();
  await expect(status(page, "añadido")).toBeVisible();
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
