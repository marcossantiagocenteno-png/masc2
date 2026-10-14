# Novel Engine

Aplicación web privada para escribir y editar novelas con asistencia de IA.

**Estado: análisis editorial de fragmentos.** La aplicación guarda textos en una base de datos local, conserva cada versión sin modificarla, permite comentar fragmentos y analizar un fragmento con un proveedor. **Hoy el único proveedor disponible es el analizador simulado, que no es una IA y no produce juicios literarios.** No hay generación automática de novelas ni conexión con servicios externos.

## Requisitos

- Python 3.11 o superior
- Node.js 20.9 o superior, con npm
- Git

## Estructura

```
apps/web/        Frontend: Next.js, TypeScript, Tailwind CSS
backend/         API FastAPI, persistencia (SQLAlchemy, Alembic) y benchmark
evals/           Casos ficticios, rúbricas e informes del benchmark
docs/            Arquitectura, criterio literario y decisiones técnicas
data/            Base de datos local (se crea al migrar; ignorada por git)
```

## Arrancar la aplicación

Los pasos siguientes arrancan la aplicación completa. Desde la raíz del repositorio.

### 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # En Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m alembic upgrade head   # crea data/novel_engine.sqlite con su esquema
uvicorn app.main:app --reload --port 8000
```

Deja esta terminal abierta. Desde otra terminal, comprueba que responde:

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"novel-engine-backend","version":"0.1.0"}
```

### 2. Frontend

En otra terminal, desde la raíz del repositorio:

```bash
cd apps/web
npm ci
npm run dev
```

Abre `http://localhost:3000/manuscritos`.

## Uso desde la interfaz

### Análisis editorial de un fragmento

En la pantalla de una versión, selecciona un fragmento del contenido y pulsa *Analizar la selección del contenido*. El resultado se muestra en cinco secciones separadas: problemas verificables, observaciones literarias, inferencias inciertas, preferencias de gusto y elementos que conviene preservar. Cada hallazgo cita su fragmento exacto, indica su línea y su certeza, y explica su efecto. El análisis no modifica el texto y queda guardado con esa versión.

**Proveedor.** Por defecto se usa el analizador simulado, y así se indica en la pantalla. Sus observaciones solo describen datos de longitud. Los problemas verificables proceden de reglas mecánicas (repeticiones de palabras funcionales, espacios dobles y comillas sin pareja), no del simulador.

1. **Crear un manuscrito.** En `/manuscritos`, escribe un título y el texto de la versión 1.
2. **Crear una versión nueva.** Dentro del manuscrito, elige de qué versión partir, edita el texto y guarda. Se crea la versión siguiente. Las anteriores no cambian.
3. **Comentar un fragmento.** Abre una versión, selecciona un fragmento del texto, pulsa *Usar la selección del contenido*, escribe el comentario y guárdalo. El comentario queda vinculado solo a esa versión.

Cada comentario guarda la cita literal y su línea en la versión. Si el comentario es una inferencia, debe incluir su cadena de inferencia. Las sugerencias de revisión se muestran, pero no se aplican al texto.

## Pruebas

### Backend

Con el entorno virtual activado, desde `backend/`:

```bash
pytest
```

Todas las pruebas deben pasar. Incluyen las de la tarea 001 (modelos del benchmark, validador y API de salud) y las de la tarea 002 (migraciones, inmutabilidad, citas, límites y API HTTP).

Validar la estructura del directorio `evals/` (debe terminar con código 0):

```bash
python -m app.benchmark.cli --evals-dir ../evals
```

### Frontend

Desde `apps/web/`:

```bash
npm run typecheck
npm run build
```

Las pruebas E2E con Playwright arrancan por su cuenta una API en el puerto 8100 y el frontend en el 3100, con una base de datos de prueba (`data/e2e.sqlite`). Necesitan el entorno de backend del paso 1 y un navegador:

```bash
# Opción A: instalar el navegador que usa Playwright
npx playwright install chromium

# Opción B: usar un Chromium ya instalado
export PLAYWRIGHT_CHROMIUM_EXECUTABLE=/ruta/a/chromium

npm run test:e2e
```

Si el entorno virtual no está en `backend/.venv`, indica el intérprete con `NOVEL_ENGINE_PYTHON=/ruta/a/python npm run test:e2e`.

## Configuración

Las variables se leen del entorno del proceso. **La aplicación no lee ningún archivo `.env`.** Para cambiar un valor, expórtalo antes de arrancar. `.env.example` documenta las variables disponibles.

| Variable | Por defecto | Uso |
|---|---|---|
| `DATABASE_URL` | `data/novel_engine.sqlite` | Base de datos. Solo SQLite está probado. |
| `NOVEL_ENGINE_MAX_VERSION_CHARS` | `500000` | Límite de caracteres por versión. Ver abajo. |
| `NOVEL_ENGINE_CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Orígenes permitidos para el frontend. |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | URL de la API que usa el frontend. |
| `NOVEL_ENGINE_ANALYSIS_PROVIDER` | `simulado` | Proveedor de análisis. Ningún otro valor está autorizado; responde 503. |
| `NOVEL_ENGINE_MAX_ANALYSIS_CHARS` | `8000` | Tamaño máximo de un fragmento analizado. |

### Límite de versión

Cada versión admite **500.000 caracteres** como valor inicial. El límite se cuenta después de normalizar el texto (Unicode NFC y saltos de línea `\n`), no sobre el texto que se envió. Si se supera, la API responde `413`. Para cambiarlo: `export NOVEL_ENGINE_MAX_VERSION_CHARS=200000` antes de arrancar el backend.

### Escucha en localhost

El backend y el frontend escuchan solo en `localhost` cuando se arrancan con los comandos de este README. La aplicación no tiene autenticación: si se expone en una red, hace falta añadirla antes, y eso queda fuera de esta fase.

## Reglas de integridad

- **Versiones inmutables.** Una versión no se modifica ni se borra. Esto se impone en el servicio (no existen operaciones de actualización) y en la base de datos (triggers de SQLite que rechazan `UPDATE` y `DELETE`). Un cambio, incluido partir de una versión anterior, crea una versión nueva.
- **Comprobación de hash.** Al leer una versión se comprueba su SHA-256. Si no coincide, la API responde `500` y no devuelve el contenido.
- **Citas exactas.** Un comentario se guarda solo si su cita coincide literalmente con el texto de la versión en esas posiciones.
- **Revisiones vinculadas.** Un comentario pertenece a una versión concreta y no aparece en las demás.

## Migraciones

```bash
cd backend
python -m alembic upgrade head      # aplica las migraciones
python -m alembic downgrade base    # revierte todas (borra las tablas)
python -m alembic check             # comprueba que los modelos coinciden con las migraciones
```

PostgreSQL no está soportado todavía. La migración inicial rechaza cualquier motor que no sea SQLite, porque la inmutabilidad se implementa con triggers de SQLite.

## Documentación

- [`docs/architecture.md`](docs/architecture.md): responsabilidades de cada componente.
- [`docs/decisions.md`](docs/decisions.md): decisiones técnicas, su estado y los pendientes.
- [`docs/literary-standard.md`](docs/literary-standard.md): criterio de calidad del benchmark y sus límites.
- [`evals/README.md`](evals/README.md): formato de casos, rúbricas e informes.

## Limitaciones actuales

- Un usuario, sin autenticación.
- Los triggers protegen las versiones frente a la API y frente a SQL normal, pero no frente a quien pueda sustituir el archivo de la base de datos. La comprobación de hash detecta cualquier cambio de contenido en una versión existente.
- Sin evaluador automático real. El único proveedor es el simulado. Las revisiones las escriben personas.
- Sin ningún proveedor de IA conectado. Conectar uno exige código nuevo y una autorización explícita para enviar textos fuera del equipo.
- Sin editor enriquecido (Tiptap): el texto se edita en áreas de texto simples.
- Sin exportación ni copias de seguridad.
- El benchmark de `evals/` (tarea 001) no está conectado a los textos del usuario.
