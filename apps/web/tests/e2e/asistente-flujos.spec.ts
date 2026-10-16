import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/**
 * Flujos del asistente de extremo a extremo: propuestas desactualizadas y fallidas, reintento, autocompletado con
 * revisión, aislamiento entre novelas y manuscritos intactos. Cada prueba crea su propia novela con la API.
 */

const API = "http://127.0.0.1:8100";
const runId = `flujo-${Date.now().toString(36)}`;

async function createProject(page: Page, name: string): Promise<number> {
  await page.goto("/proyectos");
  await page.getByLabel("Nombre de la novela").fill(name);
  await page.getByRole("button", { name: "Crear proyecto" }).click();
  await expect(page).toHaveURL(/\/proyectos\/\d+$/);
  return Number(page.url().match(/\/proyectos\/(\d+)/)?.[1]);
}

async function crearPersonaje(request: APIRequestContext, projectId: number, name: string, description: string) {
  const respuesta = await request.post(`${API}/projects/${projectId}/planificacion/personajes`, {
    data: { name, description },
  });
  expect(respuesta.status()).toBe(201);
  return (await respuesta.json()) as { id: number; description: string; estado: string };
}

async function personaje(request: APIRequestContext, projectId: number, id: number) {
  return (await (await request.get(`${API}/projects/${projectId}/planificacion/personajes/${id}`)).json()) as {
    description: string;
    estado: string;
  };
}

async function enviarAlChat(page: Page, texto: string) {
  await page.goto(page.url().replace(/\/(asistente)?$/, "") + "/asistente");
  await page.getByLabel("Mensaje al asistente").fill(texto);
  await page.getByRole("button", { name: "Enviar" }).click();
}

test("una propuesta de cambio que el elemento ya no admite queda desactualizada y no sobrescribe el cambio del autor", async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const projectId = await createProject(page, `Desactualizada ${runId}`);
  const nora = await crearPersonaje(request, projectId, "Nora", "Archivista original");

  await enviarAlChat(page, "actualiza la descripción del personaje Nora a: Archivista que duda");
  await expect(page.getByText("He preparado un cambio en la descripción de «Nora»")).toBeVisible();

  // El autor cambia el elemento después de la propuesta.
  const cambio = await request.patch(`${API}/projects/${projectId}/planificacion/personajes/${nora.id}`, {
    data: { description: "Cambio del autor" },
  });
  expect(cambio.status()).toBe(200);

  await page.getByRole("button", { name: "Aprobar y aplicar" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Propuesta desactualizada." })).toBeVisible();
  await expect(page.getByText("El elemento ha cambiado desde que se propuso")).toBeVisible();
  expect((await personaje(request, projectId, nora.id)).description).toBe("Cambio del autor");
});

test("un personaje canónico no se cambia desde una propuesta: queda fallida con su motivo", async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const projectId = await createProject(page, `Fallida ${runId}`);
  const tomas = await crearPersonaje(request, projectId, "Tomás", "Canon original");
  const aprobado = await request.post(`${API}/projects/${projectId}/planificacion/personajes/${tomas.id}/aprobar`, {
    data: { confirmar: true },
  });
  expect(aprobado.status()).toBe(200);
  expect((await personaje(request, projectId, tomas.id)).estado).toBe("canonico");

  await enviarAlChat(page, "actualiza la descripción del personaje Tomás a: Otra descripción");
  await expect(page.getByText("He preparado un cambio en la descripción de «Tomás»")).toBeVisible();
  await page.getByRole("button", { name: "Aprobar y aplicar" }).click();

  await expect(page.getByRole("status").filter({ hasText: "Propuesta fallida." })).toBeVisible();
  await expect(page.getByText("el elemento es canónico", { exact: false })).toBeVisible();
  expect((await personaje(request, projectId, tomas.id)).description).toBe("Canon original");
});

test("reenviar el mismo mensaje no duplica la conversación ni llama de nuevo al proveedor", async ({ request }) => {
  const projectId = (await (await request.post(`${API}/projects`, { data: { name: `Reintento ${runId}` } })).json()).id;
  const cuerpo = { client_id: `reintento-${runId}`, texto: "dame el estado de la novela" };

  const primero = await request.post(`${API}/projects/${projectId}/asistente/mensajes`, { data: cuerpo });
  const segundo = await request.post(`${API}/projects/${projectId}/asistente/mensajes`, { data: cuerpo });

  expect(primero.status()).toBe(200);
  expect(segundo.status()).toBe(200);
  const ids = (await primero.json()).mensajes.map((m: { id: number }) => m.id);
  expect((await segundo.json()).mensajes.map((m: { id: number }) => m.id)).toEqual(ids);
  const historial = (await (await request.get(`${API}/projects/${projectId}/asistente`)).json()).mensajes;
  expect(historial.filter((m: { role: string }) => m.role === "usuario")).toHaveLength(1);
});

test("sugerir para la premisa: se revisa, se edita y solo al guardar el formulario queda guardada", async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const projectId = await createProject(page, `Autocompletar premisa ${runId}`);
  await page.goto(`/proyectos/${projectId}`);

  await page.getByRole("button", { name: "Sugerir para Premisa" }).click();
  const region = page.getByRole("region", { name: "Sugerencia para Premisa" });
  await expect(region).toBeVisible();
  await expect(region).toContainText("Sugerencia simulada, sin IA");
  await region.getByRole("textbox").fill("Premisa revisada por el autor.");
  await region.getByRole("button", { name: "Aceptar en el campo" }).click();

  await expect(page.getByRole("textbox", { name: "Premisa", exact: true })).toHaveValue("Premisa revisada por el autor.");
  // Aceptar no guarda: el servidor sigue sin premisa.
  expect((await (await request.get(`${API}/projects/${projectId}/planificacion/narrativa`)).json()).premise).toBeFalsy();

  await page.getByRole("button", { name: "Guardar visión general" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Visión general guardada." })).toBeVisible();
  expect((await (await request.get(`${API}/projects/${projectId}/planificacion/narrativa`)).json()).premise).toBe(
    "Premisa revisada por el autor.",
  );
});

test("descartar una sugerencia no cambia el campo", async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const projectId = await createProject(page, `Descartar ${runId}`);
  await page.goto(`/proyectos/${projectId}`);

  await page.getByRole("textbox", { name: "Premisa", exact: true }).fill("Texto propio del autor.");
  await page.getByRole("button", { name: "Sugerir para Premisa" }).click();
  await page.getByRole("region", { name: "Sugerencia para Premisa" }).getByRole("button", { name: "Descartar" }).click();

  await expect(page.getByRole("textbox", { name: "Premisa", exact: true })).toHaveValue("Texto propio del autor.");
  await expect(page.getByRole("region", { name: "Sugerencia para Premisa" })).toHaveCount(0);
});

test("sugerir para la descripción de un personaje: aceptar y guardar el elemento", async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const projectId = await createProject(page, `Autocompletar personaje ${runId}`);
  const lucia = await crearPersonaje(request, projectId, "Lucía", "");
  await page.goto(`/proyectos/${projectId}?coleccion=personajes&seleccionado=${lucia.id}#personajes`);

  await page.getByRole("button", { name: "Sugerir para Descripción" }).first().click();
  const region = page.getByRole("region", { name: "Sugerencia para Descripción" }).first();
  await expect(region).toBeVisible();
  await region.getByRole("button", { name: "Aceptar en el campo" }).click();
  await expect(page.getByRole("button", { name: "Guardar cambios" }).first()).toBeEnabled();
  await page.getByRole("button", { name: "Guardar cambios" }).first().click();

  await expect.poll(async () => (await personaje(request, projectId, lucia.id)).description).not.toBe("");
});

test("las propuestas y la memoria de una novela no aparecen en otra y no se pueden aprobar desde ella", async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const origen = await createProject(page, `Origen aislado ${runId}`);
  await enviarAlChat(page, "crea un personaje llamado Vera");
  await expect(page.getByRole("button", { name: "Aprobar y aplicar" })).toBeVisible();
  const otra = await createProject(page, `Otra aislada ${runId}`);

  const propuestas = await (await request.get(`${API}/projects/${origen}/asistente/propuestas`)).json();
  expect(propuestas).toHaveLength(1);

  await page.goto(`/proyectos/${otra}/asistente`);
  await expect(page.getByText("No hay propuestas pendientes.")).toBeVisible();
  const intento = await request.post(`${API}/projects/${otra}/asistente/propuestas/${propuestas[0].id}/aprobar`);
  expect(intento.status()).toBe(404);
  expect(await (await request.get(`${API}/projects/${origen}/planificacion/personajes`)).json()).toEqual([]);
});

test("el asistente no toca manuscritos ni sus versiones", async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const projectId = await createProject(page, `Manuscrito intacto ${runId}`);
  const creado = await request.post(`${API}/projects/${projectId}/manuscripts`, {
    data: { title: "Capítulo original", content: "Texto que no debe cambiar." },
  });
  expect(creado.status()).toBe(201);
  const antes = await (await request.get(`${API}/projects/${projectId}/manuscripts`)).json();

  await enviarAlChat(page, "crea un lugar llamado Puerto");
  await page.getByRole("button", { name: "Aprobar y aplicar" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Propuesta aplicada." })).toBeVisible();

  expect(await (await request.get(`${API}/projects/${projectId}/manuscripts`)).json()).toEqual(antes);
});
