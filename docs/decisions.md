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

---

## Pendientes

| Decisión | Motivo | Cuándo |
|---|---|---|
| **Evaluador literario** (humano, modelo o mixto) | Requiere decisión del autor sobre el uso de APIs y el coste. | Antes de ejecutar cualquier evaluación real. |
| **Calibración de la rúbrica v1** | Sus descriptores no han sido contrastados. | Tras la primera ronda de evaluaciones. |
| **PostgreSQL** | Requiere reescribir la inmutabilidad (D-016) y probar el motor. | Cuando se decida migrar. |
| **Autenticación** | La aplicación es de un solo usuario en localhost (D-020). | Antes de exponerla en red. |
| **Límite de versión** | 500.000 caracteres es un valor inicial (D-019). | Tras el uso real. |
| **Primer proveedor real** | Exige decisión explícita sobre envío de datos a terceros (D-022). | Solo con autorización del autor. |
| **Límite de fragmento** | 8.000 caracteres es un valor inicial (D-027). | Tras el uso real. |
| **Pesos de las dimensiones** | La fase 0 no combina puntuaciones. | Cuando exista una evaluación completa. |
