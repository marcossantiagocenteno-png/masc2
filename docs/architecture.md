# Arquitectura de Novel Engine

Estado: **tarea 002 (textos, versiones y comentarios editoriales)**. Este documento describe lo que existe hoy y lo que queda reservado para fases posteriores. Lo reservado no tiene implementación.

## Principios

1. **Privacidad por defecto.** Los textos del autor se guardan en una base de datos local. Ningún componente envía contenido a servicios externos ni llama a APIs de IA.
2. **Versiones inmutables.** Una versión guardada no cambia. Cualquier cambio crea una versión nueva.
3. **Separar forma de juicio.** El validador del benchmark comprueba la forma de los datos. Los comentarios editoriales los escribe una persona, y se guardan con su cita exacta.
4. **Monorepo simple.** Un frontend y un backend en un solo repositorio, sin frameworks de agentes ni colas de tareas.

## Vista general

```
masc2/
├── apps/web/                  Frontend (Next.js, TypeScript, Tailwind CSS)
│   ├── app/manuscritos/       Lista, versiones y comentarios de cada versión
│   ├── lib/api.ts             Cliente HTTP hacia el backend
│   └── tests/e2e/             Pruebas Playwright
├── backend/
│   ├── app/
│   │   ├── main.py            Factoría FastAPI, CORS, /health
│   │   ├── projects/          Proyectos (novelas) aislados: archivar, restaurar, manuscritos por proyecto
│   │   ├── config.py          Configuración desde variables de entorno
│   │   ├── db/                Base declarativa, motor, sesiones y modelos SQLAlchemy
│   │   ├── texts/             Dominio: normalización, tipos de ítem, servicio, rutas
│   │   └── benchmark/         Modelos Pydantic, validador y CLI del benchmark (tarea 001)
│   ├── migrations/            Migraciones Alembic (0001: textos y versiones)
│   └── tests/                 Pruebas pytest
├── evals/                     Casos ficticios, rúbricas e informes del benchmark (tarea 001)
├── data/                      Base de datos local (ignorada por git)
└── docs/                      Arquitectura, criterio literario y decisiones
```

## Responsabilidades

| Componente | Responsabilidad | Fuera de alcance |
|---|---|---|
| `apps/web/app/manuscritos` | Crear manuscritos, crear versiones, seleccionar citas y guardar comentarios. Muestra versión, contenido y comentarios vinculados. | Editor enriquecido, generación de texto. |
| `apps/web/lib/api.ts` | Llamadas HTTP y tipos de la API. Único punto de contacto con el backend. | Caché, sincronización offline. |
| `backend/app/main.py` | Crear la aplicación, CORS, traducción de errores de dominio a HTTP, `/health`. | Autenticación. |
| `backend/app/config.py` | Leer `DATABASE_URL`, `NOVEL_ENGINE_MAX_VERSION_CHARS` y `NOVEL_ENGINE_CORS_ORIGINS`. | Leer archivos `.env`. |
| `backend/app/db` | Modelos SQLAlchemy, motor (con claves foráneas activas en SQLite), sesiones. | Lógica de dominio. |
| `backend/app/texts/normalization.py` | Normalizar a NFC y `\n`; calcular SHA-256. | Otras transformaciones del texto. |
| `backend/app/texts/kinds.py` | Registro de tipos de ítem y estados de intención permitidos. | Evaluación de calidad. |
| `backend/app/texts/service.py` | Reglas de dominio: versiones inmutables, numeración, validación de citas, comprobación de hash. | Acceso HTTP. |
| `backend/app/texts/routes.py` | Endpoints REST. | Reglas de negocio. |
| `backend/migrations` | Esquema y triggers de inmutabilidad, versionados con Alembic. | Datos de ejemplo. |
| `backend/app/analysis` | Análisis editorial de fragmentos: proveedores, verificaciones, validación y persistencia. | Generación de texto y reescritura. |
| `backend/app/planning` | Planificación narrativa: registro de tipos, servicio con reglas de canon y aislamiento, API bajo `/projects/{id}/planificacion`. | Texto del manuscrito; IA; interfaz. |
| `backend/app/backups` | Copias verificadas con la API de backup de SQLite, rotación, restauración administrativa, vista previa de retención, planificador y línea de comandos. | Versiones y edición: no las toca. |
| `backend/app/drafts` | Borrador por manuscrito con escritura condicional, puntos de recuperación, política de puntos y restauración transaccional. | Versiones formales: no las crea ni las modifica. |
| `apps/web/lib/draft-saver.ts` | Guardado del borrador sin React: una escritura en vuelo, anti-rebote, estados y conflictos. | Renderizado. |
| `backend/app/benchmark` | Validación de casos y rúbricas (tarea 001). | No se usa en la aplicación de textos. |

## Modelo de datos

| Tabla | Contenido | Inmutable |
|---|---|---|
| `projects` | Nombre, estado (`activo` o `archivado`), fechas. Sin borrado. | No se borra; se archiva. |
| `manuscript_drafts` | Texto de trabajo de un manuscrito (uno por manuscrito), revisión, hash y recuento. | No. Cambia solo con escritura condicional. |
| `draft_recovery_points` | Copias del borrador con su motivo (`periodico`, `significativo`, `conflicto`, `antes_de_sobrescribir`, `antes_de_restaurar`). | Sí (triggers). |
| `manuscripts` | Título, fecha y `project_id` (nulo para manuscritos anteriores a los proyectos). Sin contenido propio. | No (no hay endpoints para editarlo). |
| `manuscript_versions` | Número correlativo, contenido normalizado, SHA-256, número de caracteres, nota, `parent_version_id`. | Sí (servicio y triggers). |
| `analysis_runs` | Versión analizada, fragmento y su texto, proveedor, etiqueta y si era simulado. | Sí (triggers). |
| `analysis_findings` | Categoría, procedencia, cita, posiciones, línea, explicación, efecto y certeza. | Sí (triggers). |
| `editorial_reviews` | Versión a la que pertenecen, nombre de quien revisa, fecha. | Sí. |
| `review_items` | Tipo, cita literal, posiciones, línea, comentario, cadena de inferencia, sugerencia, dimensión opcional, estado de intención. | Sí. |

Restricciones relevantes:

- `(manuscript_id, number)` es único.
- `end_offset > start_offset` y `line_number >= 1`.
- Un ítem pertenece a una revisión y a la versión de esa revisión.

## Proyectos

Un proyecto es una novela. Sus manuscritos quedan aislados de los de otros proyectos: la API de proyectos solo devuelve los manuscritos del proyecto indicado, y el listado global `/manuscripts` sigue mostrando todos. Archivar no borra nada; un proyecto archivado no admite manuscritos nuevos hasta restaurarse.

Pendiente: duplicar proyectos, vincular proyectos (compartir personajes o cronologías), preferencias por proyecto y memoria narrativa propia de cada proyecto.

## Flujo de una revisión

1. El usuario selecciona un fragmento en la versión. El navegador devuelve la cita y sus posiciones, tomadas del contenido ya normalizado.
2. La API recibe el lote y, para cada ítem, comprueba que `content[start:end] == quote` en la versión indicada.
3. Si un ítem falla, el lote entero se rechaza y no se guarda nada.
4. Si todo es correcto, se guardan la revisión y sus ítems. La versión no cambia.
5. La revisión aparece solo en la versión a la que pertenece.

## Flujo de una versión nueva

1. El usuario elige una versión de partida y edita el texto. La versión de partida no cambia.
2. La API normaliza el contenido, comprueba el límite y crea la versión con el siguiente número.
3. `parent_version_id` registra el origen. La versión de origen no se toca.

## Stack

| Capa | Tecnología | Estado |
|---|---|---|
| Frontend | Next.js 16, React 19, TypeScript 5, Tailwind CSS 4 | Implementado |
| Editor | Tiptap | Pendiente. El texto se edita en áreas de texto simples. |
| Backend | Python 3.11+, FastAPI, uvicorn | Implementado |
| Validación | Pydantic 2 | Implementado |
| Persistencia | SQLAlchemy 2, Alembic, SQLite | Implementado |
| PostgreSQL | Mismo ORM, distinta configuración | No soportado. No probado. |
| Pruebas backend | pytest, httpx | Implementado |
| Pruebas frontend | Playwright | Implementado (flujo principal y validaciones) |

## Configuración

Las variables se leen del entorno del proceso. La aplicación no carga archivos `.env`. Ver `.env.example` y el README.

## Datos privados

- Los textos se guardan en `data/`, que está en `.gitignore`.
- Los manuscritos no se deben añadir a `evals/cases`, que es la carpeta de casos ficticios del benchmark.
- Las pruebas E2E usan `data/e2e.sqlite`, también ignorado.

## Persistencia del borrador

El texto del editor es un **borrador**, separado de las versiones. Migración `0005`.

- **Un borrador por manuscrito**, con un número de revisión que sube en cada guardado. Abrir la página lo crea desde la última versión si no existe, y nunca reemplaza uno existente (`POST /manuscripts/{id}/draft` devuelve `created: false` si ya estaba).
- **Escritura condicional.** `PUT /manuscripts/{id}/draft` indica la revisión que conoce el cliente. La comprobación y la escritura son una sola sentencia SQL (`UPDATE ... WHERE revision = ?`). Si no coincide, responde **409** con `current_revision`, `current_content` y `preserved_point_id`, y el texto rechazado queda en un punto `conflicto`. Nada se sobrescribe.
- **Mantener el texto propio.** Con `keep_previous`, el contenido anterior se guarda antes como punto `antes_de_sobrescribir`, en la misma transacción.
- **Puntos de recuperación.** Política en `app/drafts/policy.py`: uno al primer guardado; después, uno cada 5 minutos de cambios, o uno por cambio importante (500 caracteres de diferencia de longitud, con al menos 60 s desde el último). No hay un punto por pulsación.
- **Restaurar.** `POST /manuscripts/{id}/recovery-points/{punto}/restore` guarda el estado actual como `antes_de_restaurar` y cambia el borrador, en una sola transacción. Crea una revisión nueva. No toca las versiones.
- **Las versiones formales no cambian.** Ninguna operación del borrador crea versiones. «Guardar como nueva versión» sigue siendo explícito.

### Comportamiento ante fallos

| Caso | Qué ocurre |
|---|---|
| El servidor no responde o no hay conexión | El indicador muestra el error. El texto queda en el editor. «Reintentar» envía de nuevo. No se muestra «guardado». |
| Escrituras fuera de orden | Solo hay una escritura en vuelo; las demás esperan y usan la revisión que devolvió la anterior. Una escritura con revisión antigua recibe 409. |
| Otra ventana guardó antes | 409 y estado «conflicto». El texto de esta ventana se conserva en un punto `conflicto`. El usuario elige entre la versión guardada y «Mantener mi texto». |
| Error de validación o límite (413) | El borrador no cambia. El texto sigue en el editor, con copia `.txt` disponible. |
| Cambio de página con cambios pendientes | Se guarda antes de navegar. Si no puede, pide confirmación. |
| Cierre o recarga con cambios pendientes | Aviso del navegador. Además, un envío `keepalive` de hasta 64 KB. Es de mejor esfuerzo: no hay respuesta que leer. |

Límite del borrador: el mismo que las versiones (500.000 caracteres).

## Planificación narrativa

Módulo `backend/app/planning/`. Decisiones en D-053 a D-056. Migración `0006`.

| Tabla | Contenido |
|---|---|
| `projects` (columnas nuevas) | Premisa, sinopsis, género, tema, tono y estado de desarrollo. Todas opcionales. |
| `characters`, `places`, `plot_elements`, `timeline_events` | Personajes, lugares, elementos de trama (acontecimiento, conflicto, subtrama, misterio, pregunta abierta) y acontecimientos con orden narrativo y posición temporal libre. |
| `structure_nodes` | Actos, capítulos y escenas en un árbol (`parent_id`, `position`). |
| `narrative_links` | Relaciones tipadas entre entidades del mismo proyecto. |
| `narrative_decisions` | Decisiones de canon. Solo de inserción. |

Todas las entidades llevan `project_id`, `estado` (`provisional`, `propuesta_ia`, `canonico`), `origen` (`autor`, `ia`), `approved_decision_id` y `archived_at`.

- **Revisión de la estructura (migración 0008):** `projects.structure_version` cambia con cada escritura de estructura. Las escrituras hacen un `UPDATE` condicional sobre esa columna; una vista desfasada recibe 409 sin cambios (D-061).
- **Movimiento de nodos:** `POST .../estructura/{id}/mover` (padre y posición). Valida tipo de padre, ciclos, archivados y proyecto antes de escribir.
- **Análisis y revisiones (fase 2f):** `versionOps` en el cliente y rutas acotadas en `app/projects/scoped_routes.py`. Las rutas heredadas por versión rechazan manuscritos de proyecto (D-064).
- **Restauración de copias anteriores (fase 2f):** `app/backups/restore.py` migra solo un temporal a la revisión actual antes de sustituir la base activa (D-064).
- **Aislamiento de manuscritos (fase 2e):** `app/projects/membership.py` centraliza la comprobación de pertenencia y la guarda de escrituras heredadas sobre escenas. Las rutas `/projects/{p}/manuscripts/{m}/…` la usan; las heredadas se mantienen para manuscritos sin proyecto (D-063).
- **Escritura de escenas (migración 0009):** `scene_manuscripts` une una escena con su manuscrito propio (uno a uno, mismo proyecto, inmutable). El texto es el borrador de ese manuscrito. `app/planning/escritura.py` inicia la escritura de forma idempotente y delega el guardado en `DraftService` (D-062).

- **Vínculos (migración 0007):** triggers en `narrative_links` rechazan extremos inexistentes, archivados, de otro proyecto o de tipo no válido (D-057).
- **Historial de canon:** cada decisión guarda `actor`, `snapshot` (antes) y `resultado` (después). Cada operación de escritura es atómica: un fallo deshace la sesión (D-058).
- **Datos generales de la novela:** premisa, sinopsis, género, tema y tono no tienen estado de canon (D-059).

- **Aislamiento:** cada acceso filtra por proyecto. Un id ajeno es 404.
- **Canon:** solo cambia con aprobar, aceptar propuesta, modificar un canónico (con confirmación) o archivar un canónico (con confirmación). Todas dejan una decisión con instantánea.
- **Atomicidad:** cada operación valida antes de escribir y confirma una vez.
- **Archivado de proyecto:** las escrituras de planificación se rechazan, como ya ocurre con los manuscritos.

## Interfaz de planificación

Rutas bajo `apps/web/app/proyectos/[id]/`. Un diseño común (`layout.tsx`) identifica el espacio de trabajo de la novela y organiza las secciones: visión general (`page.tsx`), `personajes`, `lugares`, `trama`, `cronologia`, `estructura` y `estructura/[nodeId]` (escena).

| Pieza | Responsabilidad |
|---|---|
| `lib/planning.ts` | Campos de cada tipo, etiquetas de canon, árbol y reordenación. Sin React. |
| `components/planning/ElementEditor.tsx` | Edición de un elemento y sus acciones de canon. Compartido por todos los tipos. |
| `components/planning/ElementCollection.tsx` | Lista, creación con solo un nombre, archivados y selección protegida. |
| `components/planning/StructureView.tsx` | Árbol de actos, capítulos y escenas: ramas plegables, alta desde cada fila, reordenación entre hermanos y vista previa de canon. |
| `components/planning/StructureMove.tsx` | Movimiento de un nodo con selectores de lugar y botón explícito. |
| `components/planning/SceneDetail.tsx` | Escena por su id, planificación y vínculos, con enlaces a los elementos vinculados. |
| `components/planning/SceneWriting.tsx` | Editor de la escena: usa `DraftSaver` y `DraftStatus` del manuscrito, con los endpoints de escena. |
| `components/planning/RelatedScenes.tsx` | Escenas en las que aparece un personaje, lugar o elemento de trama (solo lectura). |
| `components/planning/ConfirmPanel.tsx` | Confirmación en línea: enfoca su primer control al abrirse y devuelve el foco al cerrarse. |
| `components/planning/UnsavedChanges.tsx` | Registro de cambios sin guardar: aviso al salir por un enlace o al cerrar la pestaña. |

Reglas de la interfaz: el éxito solo se muestra tras una respuesta del servidor; cada operación de estructura se prevé con la misma regla que el servidor (D-061); un error conserva el texto escrito; una acción sobre canon exige la casilla de confirmación y, si la API la rechaza, se muestra el mensaje sin reintentar con la confirmación.

## Copias de seguridad y restauración

Módulo `backend/app/backups/`. Detalle operativo en `RESPALDO_Y_RESTAURACION.md`; decisiones en D-045 a D-048.

- **Copia:** API de backup de SQLite dentro de una lectura abierta (instantánea consistente). Verificación del temporal antes de nombrarlo. Rotación solo después de crear y verificar la copia nueva. Nombres que nunca se sobrescriben.
- **Planificación:** hilo del backend, cada `NOVEL_ENGINE_BACKUP_INTERVAL_MINUTES`. Un bloqueo de carpeta impide dos operaciones a la vez.
- **Marcador:** `.app-running`, con latido renovado cada 30 s mientras corre el backend. La restauración se niega si el latido es reciente o si no puede confirmar que el proceso terminó. Nunca borra el marcador (D-049).
- **Restauración:** comando administrativo. Rechaza sin tocar la base si la copia no es válida, si el hash no coincide, si la base está en uso o si el backend está en marcha. Copia preventiva antes de reemplazar. Reversión si la verificación posterior falla. No ejecuta migraciones.
- **Retención:** solo métricas y vista previa. No borra: los triggers de `draft_recovery_points` lo impiden.

## Análisis editorial de fragmentos

`backend/app/analysis/` contiene el análisis. Sus piezas:

| Módulo | Responsabilidad |
|---|---|
| `provider.py` | Contrato `AnalysisProvider` y registro. Hoy solo `simulado`. |
| `simulated.py` | Analizador simulado: datos estructurales, marcado como simulado. |
| `checks.py` | Verificaciones deterministas: únicas fuentes de problemas verificables. |
| `categories.py` | Categorías, certezas admitidas, efecto obligatorio y procedencia. |
| `validation.py` | Reglas de cada hallazgo: cita exacta, procedencia, certeza, efecto y filtro de intenciones. |
| `service.py` | Orquesta el análisis y lo guarda en una transacción. Rechazo atómico. |

Flujo de un análisis: se carga la versión (con comprobación de hash), se valida el rango, se ejecutan las verificaciones y el proveedor, se validan todos los hallazgos y se guardan el análisis y sus hallazgos. Si algo falla, no se guarda nada. Los análisis son inmutables (migración `0002`) y guardan el fragmento y el proveedor usado.

### Proveedor real y autorización

El proveedor `anthropic` (`app/analysis/anthropic_provider.py`) es el único que envía datos fuera del equipo. Su flujo:

1. La configuración elige el proveedor. Sin clave o sin modelo, el análisis responde 503.
2. La petición debe incluir `external_authorization` con el nombre del proveedor y el alcance `fragmento_seleccionado`. Sin ella, responde 403 antes de cualquier llamada.
3. El servicio vuelve a comprobar la autorización antes de llamar al proveedor.
4. Se hace una sola llamada, sin reintentos, con la herramienta de salida forzada.
5. La respuesta se valida por esquema, citas, posiciones, procedencia, certeza, justificación y ausencia de atribuciones de intención. Si algo falla, no se guarda nada.
6. El análisis se guarda con su modelo, su procedencia y si salió del equipo (`sent_external`).

El estado del proveedor (`GET /analysis/provider`) no llama a ningún servicio.

## Sistema visual

El estilo vive en `apps/web/app/globals.css`, que es la única fuente de tokens y componentes. No hay biblioteca de componentes: Tailwind v4 para disposición y ajustes puntuales, y clases `.ne-*` para lo que se repite.

- **Tokens** en `:root`: papel, superficie, tinta, texto secundario, línea, un solo acento, foco, y estados ok, aviso y peligro con su fondo. El modo oscuro se aplica por `prefers-color-scheme` (salvo `data-theme="light"`) o por `data-theme="dark"`.
- **Capas**: `@layer base` para elementos (cuerpo, encabezados, campos, foco visible) y `@layer components` para las clases `.ne-*`. Las utilidades de Tailwind prevalecen sobre ambas capas, así que un caso concreto puede ajustarse sin pelear con la especificidad.
- **Tipografía**: serif para títulos y texto narrativo (`--font-serif`), sans para la interfaz (`--font-sans`). No se cargan fuentes externas: son pilas del sistema, así que el aspecto del serif depende del sistema operativo.
- **Escala**: `.ne-page-title` (con `--hero` en la portada), `.ne-section-title`, `.ne-subtitle`, `.ne-kicker`, `.ne-lede`, `.ne-meta`, `.ne-hint`, `.ne-label`.
- **Componentes**: `.ne-button` (`--primary`, `--ghost`, `--small`, `--danger`), `.ne-link`, `.ne-tab`, `.ne-segment`, `.ne-panel`, `.ne-list`, `.ne-empty`, `.ne-badge`, `.ne-notice` (`--ok`, `--warn`, `--danger`, `--info`), `.ne-status` para el guardado, `.ne-prose-field` para el texto narrativo (serif, interlineado 1,75, columna de 68 caracteres) y `.ne-tree__*` para la estructura.
- **Estados**: cada estado lleva icono o texto además del color («✓ Borrador guardado», «Conflicto: …»). Los `role="status"` y `role="alert"` se mantienen donde estaban.
- **Reglas**: sin sombras ni degradados decorativos. El acento se reserva al foco, a la selección actual y a la cita. Las pantallas nuevas usan la escala y los componentes antes que utilidades sueltas.

Comprobaciones: sin desbordamiento horizontal medido en 1440, 1280, 768, 390 y 360 px en las páginas revisadas; capturas inspeccionadas en 1440 y 390 px, incluido el modo oscuro del sistema. Auditoría en página (heurística, no sustituye a una herramienta de accesibilidad completa): sin nombres ausentes ni campos sin etiqueta, sin contraste insuficiente y con foco visible por teclado.

El análisis distingue el analizador simulado (aviso de tono ámbar, «no es una IA») del proveedor externo (aviso azul), y ambos del estado de proveedor no disponible (rojo). Las categorías se muestran por separado, con certeza como insignia y justificación explícita.

## Pendiente

- Primera llamada real a Anthropic. Requiere clave, modelo y la decisión del usuario (D-028, D-029).
- Registro de uso de tokens y coste por análisis.
- Solicitudes de revisión y tope de puntuación (ver la propuesta de rúbrica v2).
- Editor Tiptap.
- Autenticación, antes de exponer la aplicación en red (D-020).
- Soporte de PostgreSQL, con su propia migración de inmutabilidad y pruebas (D-015).
- Límite de versión: valor inicial, pendiente de revisión (D-019).
