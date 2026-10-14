# Novel Engine

Aplicación web privada para escribir y editar novelas con asistencia de IA.

**Estado: fase 0 (fundamentos).** Hoy el repositorio contiene la estructura, la documentación, la rúbrica literaria v1, tres casos de benchmark ficticios, los modelos de validación y una página inicial. **No hay generador de novelas, agentes autónomos ni entrenamiento de modelos.** Ninguna evaluación de calidad literaria se ha ejecutado todavía.

## Requisitos

- Python 3.11 o superior
- Node.js 20.9 o superior, con npm
- Git

## Estructura

```
apps/web/        Frontend: Next.js, TypeScript, Tailwind CSS
backend/         API FastAPI y benchmark literario (app/, tests/)
evals/           Casos ficticios, rúbricas e informes del benchmark
docs/            Arquitectura, criterio literario y decisiones técnicas
```

## 1. Backend

Desde la raíz del repositorio:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # En Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Ejecutar las pruebas (deben terminar con `65 passed` o más, y sin fallos):

```bash
pytest
```

Validar la estructura de los casos, la rúbrica y los informes del directorio `evals/` (debe imprimir `Validación estructural correcta.` y terminar con código 0):

```bash
python -m app.benchmark.cli --evals-dir ../evals
```

Levantar la API en el puerto 8000:

```bash
uvicorn app.main:app --reload --port 8000
```

Comprobar que responde, desde otra terminal:

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"novel-engine-backend","version":"0.1.0"}
```

## 2. Frontend

Desde la raíz del repositorio:

```bash
cd apps/web
npm ci
```

Comprobar tipos y compilar:

```bash
npm run typecheck
npm run build
```

Ejecutar las pruebas end-to-end con Playwright. Hacen falta los navegadores de Playwright, o bien un Chromium ya instalado:

```bash
# Opción A: instalar el navegador que usa Playwright
npx playwright install chromium

# Opción B: usar un Chromium existente
export PLAYWRIGHT_CHROMIUM_EXECUTABLE=/ruta/a/chromium

npm run test:e2e
```

Deben pasar 2 pruebas. Playwright arranca el servidor de desarrollo por su cuenta.

Levantar el entorno de desarrollo en `http://localhost:3000`:

```bash
npm run dev
```

## 3. Configuración

Copia la plantilla y ajusta los valores si hace falta:

```bash
cp .env.example .env
```

`.env` está ignorado por git. No escribas credenciales en `.env.example`. Hoy el backend no lee estas variables; la lista está en `.env.example` para las fases siguientes.

## 4. Datos privados

Los manuscritos del autor no deben guardarse en el repositorio. `.gitignore` excluye `manuscritos/`, `manuscripts/`, `data/` y los formatos de documento habituales. Los casos de `evals/cases/` son ficticios y sí se versionan.

## 5. Documentación

- [`docs/architecture.md`](docs/architecture.md): responsabilidades de cada componente.
- [`docs/literary-standard.md`](docs/literary-standard.md): qué se entiende por calidad en el benchmark y sus límites.
- [`docs/decisions.md`](docs/decisions.md): decisiones técnicas, su estado y los pendientes.
- [`evals/README.md`](evals/README.md): formato de casos, rúbricas e informes.

## Limitaciones actuales

- La rúbrica v1 no ha sido calibrada con evaluadores humanos.
- El validador comprueba la estructura de los archivos, no la calidad de los textos.
- No hay persistencia: PostgreSQL, SQLAlchemy y Alembic llegarán en una fase posterior.
- El editor Tiptap todavía no está integrado.
