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
**Estado:** aceptada

Dependencias de ejecución: `fastapi` y `pydantic`. Dependencias de desarrollo: `pytest` y `httpx`. No se incluye un framework de agentes, ni un ORM, ni un cliente de IA. El ORM (SQLAlchemy) y las migraciones (Alembic) se añadirán cuando exista un modelo de datos que probar.

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
**Estado:** aceptada

`.env.example` documenta nombres de variables sin valores secretos. `.env` está en `.gitignore`. El backend todavía no lee estas variables; cuando lo haga, se usará `pydantic-settings` o una lectura explícita, según la complejidad.

## D-014 · Ruta del navegador de Playwright configurable
**Estado:** aceptada

`playwright.config.ts` acepta `PLAYWRIGHT_CHROMIUM_EXECUTABLE`. Así se puede usar un Chromium ya instalado cuando su versión no coincide con la que espera `@playwright/test`. No se escriben rutas de una máquina concreta en el repositorio.

---

## Pendientes

| Decisión | Motivo | Cuándo |
|---|---|---|
| **Evaluador literario** (humano, modelo o mixto) | Requiere decisión del autor sobre el uso de APIs y el coste. | Antes de ejecutar cualquier evaluación real. |
| **Calibración de la rúbrica v1** | Sus descriptores no han sido contrastados. | Tras la primera ronda de evaluaciones. |
| **Modelo de datos de manuscritos y persistencia** | No hay requisitos aún. | Fase de persistencia. |
| **Pesos de las dimensiones** | La fase 0 no combina puntuaciones. | Cuando exista una evaluación completa. |
