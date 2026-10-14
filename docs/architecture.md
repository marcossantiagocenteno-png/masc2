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
| `backend/app/benchmark` | Validación de casos y rúbricas (tarea 001). | No se usa en la aplicación de textos. |

## Modelo de datos

| Tabla | Contenido | Inmutable |
|---|---|---|
| `manuscripts` | Título y fecha de creación. Sin contenido propio. | No (no hay endpoints para editarlo). |
| `manuscript_versions` | Número correlativo, contenido normalizado, SHA-256, número de caracteres, nota, `parent_version_id`. | Sí (servicio y triggers). |
| `editorial_reviews` | Versión a la que pertenecen, nombre de quien revisa, fecha. | Sí. |
| `review_items` | Tipo, cita literal, posiciones, línea, comentario, cadena de inferencia, sugerencia, dimensión opcional, estado de intención. | Sí. |

Restricciones relevantes:

- `(manuscript_id, number)` es único.
- `end_offset > start_offset` y `line_number >= 1`.
- Un ítem pertenece a una revisión y a la versión de esa revisión.

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

## Pendiente

- Evaluador automático. Queda fuera de esta fase por decisión explícita (D-012).
- Solicitudes de revisión y tope de puntuación (ver la propuesta de rúbrica v2).
- Editor Tiptap.
- Autenticación, antes de exponer la aplicación en red (D-020).
- Soporte de PostgreSQL, con su propia migración de inmutabilidad y pruebas (D-015).
- Límite de versión: valor inicial, pendiente de revisión (D-019).
