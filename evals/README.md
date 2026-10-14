# Evals

Contenido del benchmark literario. Todo lo que aparece aquí se valida con `python -m app.benchmark.cli --evals-dir ../evals` desde `backend/`.

## Carpetas

| Carpeta | Contenido | ¿Se versiona? |
|---|---|---|
| `cases/` | Casos de prueba. Encargo, contexto, restricciones, propiedades esperadas y criterios. | Sí. Solo casos ficticios. |
| `rubrics/` | Rúbricas con cinco dimensiones, niveles 1 a 5, defectos críticos y preferencias. | Sí. |
| `reports/` | Evaluaciones completadas o pendientes. Pueden contener fragmentos de texto. | No (ignorado por git, salvo `.gitkeep`). |

## Casos ficticios

Los tres casos actuales son **ejemplos ficticios e ilustrativos**. Su campo `provenance` es `ejemplo_ficticio`. No son versiones de referencia aprobadas por el autor y no deben usarse como tales. No hay ningún texto de referencia en el repositorio.

## Formato de un caso

Un archivo `cases/<id>.json`, donde `<id>` coincide con el campo `id`. El identificador usa minúsculas, dígitos y guiones, con entre 3 y 63 caracteres.

Campos obligatorios: `schema_version`, `id`, `title`, `provenance`, `language` (siempre `es`), `assignment`, `narrative_context`, `constraints`, `expected_properties`, `dimensions_under_test` y `evaluation_criteria`.

Cada dimensión evaluada necesita al menos un criterio, y no puede haber criterios para dimensiones no evaluadas.

## Dimensiones

Valores permitidos: `prosa_y_voz`, `dramaturgia`, `personajes_y_dialogo`, `focalizacion`, `continuidad`.

## Escala

Enteros de 1 a 5. Un entero en formato de cadena o un decimal se rechazan.

Una dimensión con defectos críticos no puede puntuar más de 2 (ver `docs/decisions.md`, D-009).

## Evaluaciones

Un archivo `reports/<nombre>.json` con `status`:

- `pendiente`: sin evaluador ni puntuaciones.
- `completada`: con `assessor` y una puntuación por cada dimensión del caso.

La validación comprueba que una evaluación completada cubra exactamente las dimensiones de su caso.
