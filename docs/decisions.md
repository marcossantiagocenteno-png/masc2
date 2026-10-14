# Decisiones técnicas

Registro de decisiones. Cada entrada indica su estado: **aceptada**, **provisional** o **pendiente**. Una decisión provisional debe revisarse antes de la fase que depende de ella.

---

## D-001 · Monorepo con frontend y backend separados
**Estado:** aceptada

Un único repositorio con `apps/web` (frontend) y `backend/` (API y benchmark). Se eligió para compartir el contrato de datos (`evals/`) sin publicar paquetes. El coste es que cada componente tiene su propio gestor de dependencias: pip para el backend y npm para el frontend.

## D-002 · Next.js con App Router, TypeScript y Tailwind CSS 4
**Estado:** aceptada

Stack acordado por el autor. Se usa App Router porque es la vía que Next.js mantiene. Tailwind 4 se integra mediante `@tailwindcss/postcss`. Las versiones se fijan en `package-lock.json`.

## D-003 · FastAPI y Pydantic 2 en el backend
**Estado:** aceptada

Stack acordado. Pydantic valida tanto la API como los archivos del benchmark. En esta fase la API solo expone `/health`. Pydantic está configurado con `StrictInt` para las puntuaciones, de modo que `"3"` y `3.0` se rechazan y no se convierten en silencio.

## D-004 · Dependencias mínimas en el backend
**Estado:** aceptada (ampliada en D-015)

Dependencias de ejecución iniciales: `fastapi` y `pydantic`. Dependencias de desarrollo: `pytest` y `httpx`. No se incluye un framework de agentes ni un cliente de IA. La tarea 002 añade SQLAlchemy, Alembic y uvicorn, según D-015.

## D-005 · Benchmark como datos versionados en JSON
**Estado:** aceptada

Los casos y la rúbrica son archivos JSON en `evals/`. Son legibles, versionables y validables sin ejecutar código. Cada caso se nombra como su identificador (`<id>.json`), y el validador lo comprueba.

## D-006 · Los casos son ficticios y están marcados así
**Estado:** aceptada

El campo `provenance` solo admite `ejemplo_ficticio`. El modelo `BenchmarkCase` no tiene campo para versiones de referencia. Así, la fase 0 no inventa textos "aprobados" por el autor. Cuando el autor apruebe una referencia, se añadirá un modelo nuevo con su procedencia.

## D-007 · El validador comprueba forma, no calidad
**Estado:** aceptada

`validator.py` y `cli.py` comprueban que los archivos cumplen los modelos, que los identificadores son únicos, que el nombre del archivo coincide con el identificador y que una evaluación completada puntúa exactamente las dimensiones del caso. No calculan puntuaciones ni asignan notas. Una evaluación pendiente es válida y sin puntuaciones.

## D-008 · Escala de cinco niveles con enteros
**Estado:** aceptada

Escala de 1 a 5 con enteros estrictos. Los descriptores de cada nivel se definen en la rúbrica para las cinco dimensiones. Se eligieron enteros para evitar falsa precisión: no se admiten decimales como 3,7.

## D-009 · Los defectos críticos limitan la puntuación a 2
**Estado:** provisional

Regla implementada en `DimensionScore`: si una dimensión tiene defectos críticos, su puntuación no puede superar 2. Es una decisión de diseño, no una verdad sobre literatura. Hay que revisarla cuando existan evaluaciones reales. Las notas estilísticas no afectan a la puntuación y no pueden mezclarse con los defectos críticos.

## D-010 · Estados de una evaluación
**Estado:** aceptada

- `pendiente`: sin evaluador ni puntuaciones.
- `completada`: con evaluador y una puntuación por dimensión, sin repeticiones.

No hay estado intermedio ni de "borrador". Si hace falta, se añadirá en una fase posterior.

## D-011 · Pruebas: pytest en backend y Playwright en frontend
**Estado:** aceptada

pytest prueba modelos, validador, CLI y API, incluidos los límites de la escala (1 y 5 aceptados; 0 y 6 rechazados). Playwright prueba la página en Chromium, incluido el comportamiento en un viewport de móvil. Las pruebas no requieren red ni claves de API.

## D-012 · Sin llamadas a APIs de IA en la fase 0
**Estado:** aceptada

Ningún código de la fase 0 envía manuscritos ni casos a una API externa. El evaluador literario real se decidirá en una fase posterior, con revisión explícita del autor.

## D-013 · Configuración por variables de entorno con plantilla
**Estado:** aceptada (actualizada en la tarea 002)

`.env.example` documenta nombres de variables sin valores secretos. `.env` está en `.gitignore`. La aplicación **no lee ningún archivo `.env`**: las variables se leen del entorno del proceso (`app/config.py`). Si más adelante se quiere leer `.env`, se añadirá de forma explícita y con su prueba.

## D-014 · Ruta del navegador de Playwright configurable
**Estado:** aceptada

`playwright.config.ts` acepta `PLAYWRIGHT_CHROMIUM_EXECUTABLE`. Así se puede usar un Chromium ya instalado cuando su versión no coincide con la que espera `@playwright/test`. No se escriben rutas de una máquina concreta en el repositorio.

---

## D-015 · SQLite con SQLAlchemy y Alembic desde la tarea 002
**Estado:** aceptada

La tarea 002 crea el primer modelo de datos, que era la condición de D-004. Se usa SQLite como base local por defecto, sin servidor. SQLAlchemy 2 define los modelos y Alembic gestiona el esquema mediante migraciones. `DATABASE_URL` permite cambiar de motor por configuración, pero **PostgreSQL no está soportado ni probado**: la migración inicial rechaza otros motores. Migrar a PostgreSQL exigirá reescribir la inmutabilidad (D-016) y probarla.

## D-016 · Versiones inmutables, en el servicio y en la base de datos
**Estado:** aceptada

Doble protección:

1. El servicio (`TextService`) no tiene operaciones de actualización ni de borrado de versiones, revisiones ni ítems.
2. La migración `0001` crea triggers en SQLite que rechazan `UPDATE` y `DELETE` sobre `manuscript_versions`, `editorial_reviews` y `review_items`. Las pruebas comprueban los triggers desde SQL directo y desde el ORM.

Partir de una versión anterior crea una versión nueva con el siguiente número y un `parent_version_id`. No modifica la versión de origen.

Al leer una versión se comprueba su SHA-256. Si no coincide, la API responde `500` y no devuelve el contenido.

**Límite conocido:** los triggers no impiden que alguien sustituya o edite el archivo de la base de datos fuera de la aplicación. El hash detecta el cambio de contenido, pero no protege contra la sustitución completa del archivo.

## D-017 · Citas literales con posición y línea, validadas contra la versión
**Estado:** aceptada

Cada ítem guarda la cita literal, su posición inicial y final, y el número de línea calculado en el servidor. Al crear el comentario, la cita debe coincidir exactamente con `content[start:end]` de la versión indicada. Si no coincide, el lote entero se rechaza.

El contenido original de la versión se guarda completo en `manuscript_versions.content`. Las posiciones nunca se usan para reconstruirlo.

## D-018 · Tipos de ítem en un registro, sin restricción en la base de datos
**Estado:** aceptada

Los tipos permitidos (`observacion`, `inferencia`) están en `app/texts/kinds.py`. La columna `review_items.kind` es texto libre sin `CHECK`, de modo que añadir un tipo es un cambio de código y no una migración. La regla de cadena de inferencia se aplica en el servicio. Se decidió no usar un `CHECK` para no tener que migrar al añadir tipos.

## D-019 · Límite de 500.000 caracteres por versión
**Estado:** provisional

Valor inicial configurable con `NOVEL_ENGINE_MAX_VERSION_CHARS`. Se cuenta tras normalizar (NFC y `\n`). Se responde `413` si se supera. El valor es una decisión de esta fase y debe revisarse con el uso real.

## D-020 · Localhost, sin autenticación y sin servicios externos
**Estado:** aceptada

Backend y frontend se arrancan en `localhost` según el README. No hay autenticación porque la aplicación es de un solo usuario. Exponerla en red exige añadir autenticación. No hay conexiones a APIs de IA ni envío de contenido a servicios externos.

## D-021 · Pruebas E2E con servidores propios en puertos distintos
**Estado:** aceptada

Las pruebas Playwright arrancan una API en `127.0.0.1:8100` y el frontend en `localhost:3100`, sobre `data/e2e.sqlite`. Así no interfieren con el desarrollo en los puertos 3000 y 8000. Los títulos de prueba son únicos porque la base E2E se conserva entre ejecuciones.

## D-022 · Proveedores de modelos intercambiables, pero solo uno autorizado
**Estado:** aceptada

`app/analysis/provider.py` define el contrato `AnalysisProvider` y un registro `PROVIDER_FACTORIES`. Hoy el registro contiene únicamente `simulado`. Cualquier otro valor de `NOVEL_ENGINE_ANALYSIS_PROVIDER` responde `503` con el mensaje «no está autorizado ni configurado». No hay código de ningún servicio externo ni cliente de IA. Añadir uno exige código nuevo, una entrada en el registro y una decisión explícita del autor sobre el envío de manuscritos.

El cliente no puede elegir proveedor: el campo `provider` se rechaza con `422`.

## D-023 · El analizador simulado se identifica como tal en cada respuesta
**Estado:** aceptada

`SimulatedAnalyzer` solo produce datos estructurales: número de frases y la frase más larga, con su posición. Cada hallazgo lleva el prefijo «[Simulado]», la respuesta incluye `provider_simulated: true` y su etiqueta, y la interfaz muestra un aviso. No produce juicios literarios. Sirve para probar el flujo.

## D-024 · Los problemas verificables solo los produce un proceso determinista
**Estado:** aceptada

`app/analysis/checks.py` contiene tres reglas mecánicas: palabra funcional repetida de forma inmediata («que que»), espacios dobles entre palabras y guiones o comillas de diálogo sin pareja. Son las únicas que pueden producir la categoría `problema_verificable`. Un proveedor que intente producirla recibe un rechazo. Ninguna regla mira la longitud de las frases, la ambigüedad ni la falta de explicaciones.

## D-025 · Validación de cada hallazgo antes de guardar, con rechazo atómico
**Estado:** aceptada

`app/analysis/validation.py` valida cada hallazgo: la cita debe coincidir exactamente con el fragmento en la posición indicada; cada categoría admite solo sus certezas y su procedencia; las observaciones, inferencias y elementos a preservar deben explicar su efecto; y ningún texto puede atribuir intención al autor. Si un hallazgo falla, se rechaza el análisis entero y no se guarda nada (`502`).

El filtro de intenciones es léxico. Reduce el riesgo, no lo elimina: un texto que atribuya intención con otra formulación pasaría.

## D-026 · Análisis inmutables, con su fragmento y su proveedor
**Estado:** aceptada

La migración `0002` crea `analysis_runs` y `analysis_findings`, con triggers de SQLite que impiden modificarlos o borrarlos, como en la migración `0001`. Cada análisis guarda el texto del fragmento, el proveedor, su etiqueta y si era simulado. Al leerlo se comprueba que el fragmento coincide con la versión original; si no coincide, la API responde `500`.

Las posiciones de los hallazgos son absolutas, dentro de la versión. La línea se calcula en el servidor.

El análisis nunca modifica la versión. Los hallazgos no se ofrecen como texto reescrito ni como sugerencias de cambio.

## D-027 · Límite de fragmento de 8.000 caracteres
**Estado:** provisional

Configurable con `NOVEL_ENGINE_MAX_ANALYSIS_CHARS`. Responde `413` si se supera. Es un valor inicial para una escena.

## D-028 · Proveedor real: API oficial de Anthropic, con SDK oficial de Python
**Estado:** aceptada

`app/analysis/anthropic_provider.py` usa el SDK `anthropic` (dependencia `>=1.13,<2.0`) y la Messages API. Es el único proveedor externo. Elegirlo exige `NOVEL_ENGINE_ANALYSIS_PROVIDER=anthropic`, `ANTHROPIC_API_KEY` y `NOVEL_ENGINE_ANTHROPIC_MODEL`. Si falta cualquiera, el análisis responde 503. No hay respaldo: nunca se usa el simulador ni otro servicio en su lugar.

El modelo no tiene valor por defecto. El código no inventa identificadores: el usuario indica uno que su cuenta admita (README).

## D-029 · Autorización explícita por petición, sin persistencia
**Estado:** aceptada

El envío de un fragmento a un proveedor externo exige `external_authorization` en el cuerpo de la petición, con el nombre del proveedor configurado, `scope: "fragmento_seleccionado"` y `acknowledged: true`. Sin ella, la ruta responde 403 antes de cualquier llamada. El servicio vuelve a comprobarlo (defensa en profundidad).

La autorización no se guarda, no se deriva de una variable de entorno y no se reutiliza entre peticiones. La configuración elige el proveedor; no autoriza el envío. La interfaz muestra el fragmento exacto y pide una casilla antes de enviar; la casilla se reinicia tras cada análisis.

## D-030 · Un único envío por análisis, sin reintentos
**Estado:** aceptada

El cliente se crea con `max_retries=0`. El SDK reintenta por defecto, y eso duplicaría llamadas y costes. Cada análisis hace exactamente una llamada a `messages.create`, con `max_tokens` y `timeout` configurables. Un fallo responde 502 y no guarda nada. La interfaz deshabilita el botón mientras el análisis está en curso.

## D-031 · Salida estructurada forzada y posiciones calculadas por el backend
**Estado:** aceptada

La respuesta se fuerza a una herramienta con esquema (`tool_choice` de tipo `tool`). Cada hallazgo indica la cita y la aparición que se refiere (`occurrence`). El backend calcula las posiciones sobre el fragmento recibido; el modelo nunca fija desplazamientos. Si la cita no aparece, o la aparición no existe, la respuesta se rechaza. Si cualquier hallazgo del lote falla, no se guarda ninguno.

La categoría `problema_verificable` queda fuera del esquema de Claude. Solo la producen las verificaciones deterministas (D-024).

Limitación: la cita debe coincidir carácter a carácter. Una cita con espacios o comillas tipográficas distintas se rechaza aunque sea correcta. Es deliberado: prefiere rechazar a guardar una cita que no corresponde.

## D-032 · Secretos: solo en configuración, nunca en respuestas ni logs
**Estado:** aceptada

- `ANTHROPIC_API_KEY` se lee en `app/config.py` y se oculta en `repr` (`repr=False`).
- Los errores del SDK no se exponen: el mensaje devuelto contiene solo el tipo de error (p. ej. `APITimeoutError`).
- Los logs registran metadatos: modelo, tamaño del fragmento, motivo de parada y tipo de error. No registran el texto, la clave, los comentarios ni la respuesta completa.
- El estado del proveedor (`GET /analysis/provider`) no llama a ningún servicio y no incluye la clave.

Las pruebas comprueban que la clave y el texto no aparecen en respuestas, logs ni en la representación de la configuración.

## D-033 · Procedencia visible: real y simulado no se confunden
**Estado:** aceptada

Cada análisis guarda `provider_simulated`, `sent_external` y `model_name`. La interfaz presenta cada análisis según su propia procedencia: un aviso azul para el proveedor real y uno ámbar para el simulado. La etiqueta del análisis indica si fue real o simulado. La migración 0003 mantiene los triggers de inmutabilidad, y su bajada los recrea.

## D-034 · Instrucciones de diagnóstico y límites del prompt
**Estado:** aceptada, con limitación conocida

El prompt pide cinco categorías separadas, cita literal, justificación, efecto y certeza. Prohíbe atribuir intenciones y puntuar la calidad, y pide no penalizar la ambigüedad, la contención emocional, las frases breves ni la falta de explicaciones. Trata el fragmento como dato, no como instrucción.

**Limitación:** el prompt no se puede garantizar. El backend comprueba forma, citas, posiciones, procedencia, certeza y ausencia de atribuciones de intención (por léxico). No comprueba si el juicio literario es acertado. Eso requiere evaluación humana, que no está implementada.

## D-035 · Proyectos como contenedor de manuscritos, sin borrado
**Estado:** aceptada

Cada novela es un proyecto (`projects`). Un manuscrito pertenece a un proyecto mediante `project_id`, que es nulo solo para los manuscritos anteriores a la migración 0004 que no se asignen. Los proyectos **no se borran**: se archivan y se restauran. Mientras están archivados, sus textos siguen siendo legibles, pero no admiten manuscritos nuevos. No hay endpoint de borrado (probado: responde 405).

## D-036 · Migración 0004 con ALTER TABLE y bajada no automática
**Estado:** aceptada

La columna `project_id` se añade con `ALTER TABLE ... REFERENCES`, sin reconstruir `manuscripts`. Reconstruir esa tabla con versiones que la referencian hace fallar `DROP TABLE` con claves foráneas activas (comprobado). Por la misma razón, la bajada no es automática: lanza un error explícito que indica restaurar la copia previa. Los datos se conservan (probado).

Limitación conocida: SQLAlchemy no reconstruye el `ON DELETE` de claves añadidas con `ALTER TABLE` en SQLite. El modelo no declara `ondelete` para que `alembic check` sea coherente. La base de datos sí tiene `RESTRICT`. Como un proyecto nunca se borra, la diferencia no llega a actuar.

## D-037 · Nunca editar una migración ya aplicada
**Estado:** aceptada

Durante el desarrollo de 0004, un intento anterior dejó la base de desarrollo con una columna sin clave foránea. `alembic check` lo detectó. Se hizo una copia de seguridad de las bases de desarrollo y se regeneraron desde las migraciones. Regla: cada cambio de esquema va en una migración nueva, y una migración ya aplicada no se edita.

## D-038 · Edición segura de la versión de partida
**Estado:** aceptada

Dos correcciones a la página de nueva versión:

1. Cambiar la versión de partida con texto sin guardar pide confirmación. Al cancelar, se conservan el texto y la versión elegida.
2. La carga asíncrona de la versión de partida no sustituye un texto que el autor ya ha escrito desde la última carga (`userEditedRef`).

Ambas están probadas con pruebas E2E. La segunda se reprodujo de forma determinista retrasando la respuesta del servidor.

## D-039 · Persistencia antes que planificación
**Estado:** aceptada (reordena la especificación, sin eliminar requisitos)

La auditoría muestra que el editor puede perder texto. La fase de persistencia fiable (autoguardado, puntos de recuperación, copias) pasa antes de la planificación narrativa. Ver `docs/PLAN_IMPLEMENTACION.md`.

## D-040 · Recuperación por copia como única vía de respaldo hoy
**Estado:** aceptada, provisional

No hay copias automáticas. La copia manual del archivo SQLite, con la aplicación detenida, está documentada en `docs/RESPALDO_Y_RESTAURACION.md` y probada (`test_recovery.py`). Se sustituirá por copias automáticas en la fase 1b.


## D-041 · El borrador vive en tablas propias, no en las versiones
**Estado:** aceptada

El texto de trabajo se guarda en `manuscript_drafts` (una fila por manuscrito) y sus copias en `draft_recovery_points`, inmutables. `manuscript_versions` no cambia. Motivo: las versiones son el registro inmutable del autor (D-016). Un estado «borrador» en la misma tabla obligaría a relajar esa garantía. La migración `0005` solo crea tablas.

## D-042 · Escritura condicional por revisión, con 409 que preserva el texto
**Estado:** aceptada

Cada escritura indica la revisión que conoce el cliente. La condición y la escritura son una sola sentencia SQL, así que dos escrituras no pueden aplicarse sobre la misma revisión. Una escritura no válida responde 409 y guarda el texto rechazado como punto `conflicto` antes de responder. Restaurar y «Mantener mi texto» son transaccionales: guardan el estado anterior en el mismo `COMMIT`. Probado con una prueba que falla si se quita la condición.

## D-043 · Política de puntos de recuperación
**Estado:** aceptada, provisional

Un punto al primer guardado; después, uno cada 5 minutos con cambios, o uno por cambio importante (500 caracteres de diferencia de longitud, con 60 s desde el último). La longitud es una aproximación barata: un cambio que sustituya 500 caracteres por otros 500 no cuenta como importante. No se guarda un punto por pulsación. Los puntos no se borran todavía: el crecimiento está acotado por los intervalos, pero no hay retención (ver pendientes).

## D-044 · Copias automáticas aplazadas
**Estado:** aceptada

No se han implementado copias automáticas en esta fase. Copiar un archivo SQLite mientras se escribe exige la API de copia en caliente de SQLite, una rotación con límite de retención y una restauración probada. Mezclarlo con el borrador añadía riesgo a la parte que ya funciona. Es la primera tarea de la siguiente fase de persistencia.

---

## Pendientes

| Decisión | Motivo | Cuándo |
|---|---|---|
| **Evaluador literario** (humano, modelo o mixto) | Requiere decisión del autor sobre el uso de APIs y el coste. | Antes de ejecutar cualquier evaluación real. |
| **Calibración de la rúbrica v1** | Sus descriptores no han sido contrastados. | Tras la primera ronda de evaluaciones. |
| **PostgreSQL** | Requiere reescribir la inmutabilidad (D-016) y probar el motor. | Cuando se decida migrar. |
| **Autenticación** | La aplicación es de un solo usuario en localhost (D-020). | Antes de exponerla en red. |
| **Límite de versión** | 500.000 caracteres es un valor inicial (D-019). | Tras el uso real. |
| **Primera llamada real** | Requiere clave y modelo del usuario, y su aprobación de envío (D-028, D-029). No se ha ejecutado. | Cuando el usuario lo decida. |
| **Registro de uso y coste** | La respuesta trae `usage`, pero no se guarda (evita registrar datos de más). | Si se necesita control de costes. |
| **Límite de fragmento** | 8.000 caracteres es un valor inicial (D-027). | Tras el uso real. |
| **Copias automáticas de la base de datos** | Solo hay copia manual (D-040, D-044). | Siguiente tarea inmediata. |
| **Retención de puntos de recuperación** | Los puntos no se borran nunca (D-043). | Antes de que el tamaño sea un problema real. |
| **Paquete de proyecto restaurable** | Sin exportación ni importación completa. | Fase 5. |
| **Autenticación** | Imprescindible antes de exponer la aplicación en red. | Antes de cualquier despliegue. |
| **Pesos de las dimensiones** | La fase 0 no combina puntuaciones. | Cuando exista una evaluación completa. |
