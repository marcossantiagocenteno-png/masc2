# Arquitectura de Novel Engine

Estado: **fase 0 (fundamentos)**. Este documento describe lo que existe hoy y lo que está reservado para fases posteriores. Lo reservado no tiene implementación.

## Principios

1. **Privacidad por defecto.** Los manuscritos del autor no salen del entorno local ni se envían a ninguna API. Ningún componente de la fase 0 realiza llamadas a servicios externos de IA.
2. **Separar forma de juicio.** El código valida la forma de los datos (casos, evaluaciones, rúbrica). La calidad literaria la juzga una evaluación explícita, nunca el validador.
3. **Monorepo simple.** Un solo repositorio con un frontend y un backend. Sin frameworks de agentes ni colas de tareas en esta fase.

## Vista general

```
masc2/
├── apps/web/            Frontend (Next.js, TypeScript, Tailwind CSS). Editor Tiptap previsto.
├── backend/
│   ├── app/
│   │   ├── main.py      API FastAPI. Solo GET /health.
│   │   └── benchmark/   Modelos Pydantic, validador y CLI del benchmark.
│   └── tests/           Pruebas pytest.
├── evals/
│   ├── cases/           Casos de prueba ficticios del benchmark (JSON).
│   ├── rubrics/         Rúbricas de evaluación (JSON).
│   └── reports/         Evaluaciones generadas. Ignoradas por git salvo .gitkeep.
└── docs/                Arquitectura, criterios de calidad y decisiones.
```

## Responsabilidades

| Componente | Responsabilidad actual | Fuera de alcance por ahora |
|---|---|---|
| `apps/web` | Página de estado de la fase 0. Pruebas E2E con Playwright. | Editor, manuscritos, llamadas al backend. |
| `backend/app/main.py` | Servir `/health`. | Manuscritos, persistencia, generación. |
| `backend/app/benchmark/models.py` | Definir y validar `BenchmarkCase`, `LiteraryEvaluation`, `DimensionScore`, `Rubric`. | Calcular puntuaciones. |
| `backend/app/benchmark/validator.py` | Cargar archivos, comprobar coherencia entre caso y evaluación, detectar duplicados. | Juzgar prosa, trama o voz. |
| `backend/app/benchmark/cli.py` | Validar `evals/` desde la línea de comandos y devolver código de salida. | Ejecutar evaluaciones literarias. |
| `evals/cases` | Encargos ficticios con restricciones, propiedades esperadas y criterios. | Versiones de referencia aprobadas por el autor. |
| `evals/rubrics` | Cinco dimensiones, niveles 1 a 5, defectos críticos y preferencias. | Calibración con evaluadores humanos. |
| `evals/reports` | Destino previsto de evaluaciones completadas. | Contenido en la fase 0 (solo `.gitkeep`). |

## Flujo de datos previsto

Fases posteriores seguirán esta secuencia. Solo los pasos 1 y 2 existen hoy, y únicamente como validación de archivos.

1. Un caso (`evals/cases/*.json`) define el encargo y los criterios.
2. El validador comprueba que el caso y la rúbrica son estructuralmente correctos.
3. Un evaluador (humano o automatizado, decidido en una fase posterior) produce una `LiteraryEvaluation` con justificación por dimensión.
4. El validador comprueba que la evaluación cubre exactamente las dimensiones del caso.

El paso 3 no está implementado. Hasta que exista, ningún resultado del benchmark significa nada sobre calidad literaria.

## Stack

| Capa | Tecnología | Estado |
|---|---|---|
| Frontend | Next.js 16, React 19, TypeScript 5, Tailwind CSS 4 | Implementado (página mínima) |
| Editor | Tiptap | Pendiente |
| Backend | Python 3.11+, FastAPI | Implementado (`/health`) |
| Validación | Pydantic 2 | Implementado |
| Persistencia | PostgreSQL con SQLAlchemy y Alembic | Pendiente. Sin modelos aún. |
| Pruebas backend | pytest, httpx | Implementado |
| Pruebas frontend | Playwright | Implementado (2 pruebas E2E) |

## Configuración

Las variables de entorno se documentan en `.env.example`. Ninguna se lee todavía en el código, salvo las que Next.js consume mediante el prefijo `NEXT_PUBLIC_`, que la página mínima no usa. Las credenciales nunca se escriben en el repositorio.

## Datos privados

- Los manuscritos del autor deben guardarse fuera del control de versiones. `.gitignore` excluye `manuscritos/`, `manuscripts/`, `data/` y formatos de documento habituales.
- Los casos de `evals/cases` son ficticios y sí se versionan. No se deben añadir manuscritos reales a esa carpeta.
- Los informes de evaluación pueden contener fragmentos de texto. Por eso `evals/reports/*` está ignorado.

## Pendiente

- Modelos SQLAlchemy y migraciones Alembic (cuando exista el modelo de datos de manuscritos).
- Integración del editor Tiptap con el backend.
- Definir el evaluador literario real (decisión pendiente, ver `decisions.md`).
