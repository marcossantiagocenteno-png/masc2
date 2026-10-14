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

### Proyectos

Cada novela es un proyecto independiente. Desde `/proyectos` puedes crear un proyecto, abrirlo, renombrarlo, archivarlo y restaurarlo. Archivar no borra nada: los textos siguen disponibles, pero el proyecto no admite manuscritos nuevos hasta restaurarlo. Los manuscritos creados antes de los proyectos se asignaron a «Proyecto inicial».

### Análisis editorial de un fragmento

En la pantalla de una versión, selecciona un fragmento del contenido y pulsa *Analizar la selección del contenido*. El resultado se muestra en cinco secciones separadas: problemas verificables, observaciones literarias, inferencias inciertas, preferencias de gusto y elementos que conviene preservar. Cada hallazgo cita su fragmento exacto, indica su línea y su certeza, y explica su efecto. El análisis no modifica el texto y queda guardado con esa versión.

**Proveedor.** Por defecto se usa el analizador simulado, y así se indica en la pantalla. Sus observaciones solo describen datos de longitud. Los problemas verificables proceden de reglas mecánicas (repeticiones de palabras funcionales, espacios dobles y comillas sin pareja), no del simulador. Con el proveedor real, cada análisis muestra el aviso azul de envío externo.

1. **Crear un manuscrito.** En `/manuscritos`, escribe un título y el texto de la versión 1.
2. **Crear una versión nueva.** Dentro del manuscrito, elige de qué versión partir, edita el texto y guarda. Se crea la versión siguiente. Las anteriores no cambian.
3. **Comentar un fragmento.** Abre una versión, selecciona un fragmento del texto, pulsa *Usar la selección del contenido*, escribe el comentario y guárdalo. El comentario queda vinculado solo a esa versión.

Cada comentario guarda la cita literal y su línea en la versión. Si el comentario es una inferencia, debe incluir su cadena de inferencia. Las sugerencias de revisión se muestran, pero no se aplican al texto.

### Proveedor real (Anthropic)

Por defecto el análisis usa el **analizador simulado**, que no es una IA y no envía nada fuera del equipo. Para usar Claude hace falta configurarlo, y cada análisis exige tu confirmación.

**Qué se envía.** Solo el fragmento que seleccionas, con las instrucciones de análisis. No se envían el título del manuscrito, otras versiones, comentarios ni el resto del texto. Aun así, el fragmento puede contener datos personales: no lo envíes si no quieres que salgan del equipo.

**Cómo se autoriza.** Al pulsar *Revisar envío a Anthropic*, la pantalla muestra el fragmento exacto y pide una casilla. La autorización vale solo para ese análisis: no se guarda, no viene de ninguna variable de entorno y no se reutiliza.

**Configuración.** Exporta las variables antes de arrancar el backend (no se leen de ningún archivo):

```bash
export NOVEL_ENGINE_ANALYSIS_PROVIDER=anthropic
export ANTHROPIC_API_KEY=...                      # tu clave; no la escribas en ningún archivo del repositorio
export NOVEL_ENGINE_ANTHROPIC_MODEL=...           # identificador de un modelo que tu cuenta admita
export NOVEL_ENGINE_ANTHROPIC_TIMEOUT_SECONDS=60  # opcional
export NOVEL_ENGINE_ANTHROPIC_MAX_OUTPUT_TOKENS=2000  # opcional
uvicorn app.main:app --port 8000
```

**Elegir el modelo.** El proyecto no incluye ningún identificador de modelo: debe ser uno que tu cuenta admita. Puedes consultar los disponibles con la API de Anthropic, desde tu terminal, con tu clave (esto lo ejecutas tú; el proyecto no lo hace):

```bash
curl https://api.anthropic.com/v1/models \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01"
```

Comprueba la documentación oficial de Anthropic para la versión actual del endpoint.

**Si algo falta.** Sin clave o sin modelo, el análisis responde 503 y no se llama a nadie. No hay respaldo: el simulador no sustituye a Claude en silencio.

**Costes.** Cada análisis hace **una** llamada, sin reintentos. El coste depende del modelo, del número de tokens de entrada (el fragmento, de hasta `NOVEL_ENGINE_MAX_ANALYSIS_CHARS` caracteres, más las instrucciones) y de los de salida (acotados por `NOVEL_ENGINE_ANTHROPIC_MAX_OUTPUT_TOKENS`). Consulta la tabla de precios oficial de tu modelo. Una llamada que falla por tiempo o error puede seguir facturándose según las condiciones de Anthropic. El proyecto no registra el uso de tokens todavía.

**Privacidad.** Qué hace Anthropic con los datos enviados depende de sus condiciones y de la configuración de tu cuenta. Revísalas antes de enviar textos que no sean tuyos o que no puedas compartir.

**Primera llamada real (paso a paso).** No se ha ejecutado ninguna llamada real durante el desarrollo. Para hacer la primera:

1. Obtén una clave en tu cuenta de Anthropic y elige un modelo que tu cuenta admita.
2. Exporta las variables de la sección anterior y arranca el backend.
3. Abre una versión con contenido, selecciona un fragmento corto (unas pocas frases) y pulsa *Revisar envío a Anthropic*.
4. Lee el fragmento que aparece en la confirmación. Si no es el que quieres enviar, pulsa *Cancelar*.
5. Marca la casilla y pulsa *Enviar a Anthropic y analizar*.
6. Comprueba que el resultado aparece con el aviso azul de proveedor real, con el modelo indicado y con la justificación de cada hallazgo.

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

## Respaldo y restauración

El texto que escribes en el editor se guarda solo como **borrador** en la base de datos (autoguardado), y se recupera al volver a abrir la página. El borrador no es una versión: las versiones solo se crean con «Guardar como nueva versión». Hay puntos de recuperación del borrador, que puedes restaurar desde la página del manuscrito.

**No hay copias automáticas de la base de datos todavía.** Para respaldar, detén el backend y copia `data\novel_engine.sqlite`. Para restaurar, detén el backend y sustituye el archivo por la copia. Detalles y advertencias en [`docs/RESPALDO_Y_RESTAURACION.md`](docs/RESPALDO_Y_RESTAURACION.md).

## Migraciones

```bash
cd backend
python -m alembic upgrade head      # aplica las migraciones
python -m alembic downgrade base    # revierte todas (borra las tablas)
python -m alembic check             # comprueba que los modelos coinciden con las migraciones
```

Las migraciones `0004` (proyectos) y `0005` (borradores y puntos de recuperación) no tienen bajada automática: para revertirlas, restaura la copia de la base de datos anterior a la migración. PostgreSQL no está soportado todavía. La migración inicial rechaza cualquier motor que no sea SQLite, porque la inmutabilidad se implementa con triggers de SQLite.

## Documentación

- [`docs/architecture.md`](docs/architecture.md): responsabilidades de cada componente.
- [`docs/decisions.md`](docs/decisions.md): decisiones técnicas, su estado y los pendientes.
- [`docs/AUDITORIA_TECNICA.md`](docs/AUDITORIA_TECNICA.md): estado real, riesgos y deuda técnica.
- [`docs/PLAN_IMPLEMENTACION.md`](docs/PLAN_IMPLEMENTACION.md) y [`docs/ESTADO_DE_IMPLEMENTACION.md`](docs/ESTADO_DE_IMPLEMENTACION.md): fases y estado.
- [`docs/PRIVACIDAD_Y_DATOS.md`](docs/PRIVACIDAD_Y_DATOS.md): qué sale del equipo y qué se guarda.
- [`docs/literary-standard.md`](docs/literary-standard.md): criterio de calidad del benchmark y sus límites.
- [`evals/README.md`](evals/README.md): formato de casos, rúbricas e informes.

## Limitaciones actuales

- Un usuario, sin autenticación.
- Los triggers protegen las versiones frente a la API y frente a SQL normal, pero no frente a quien pueda sustituir el archivo de la base de datos. La comprobación de hash detecta cualquier cambio de contenido en una versión existente.
- Sin evaluador automático real. El único proveedor es el simulado. Las revisiones las escriben personas.
- El proveedor real (Anthropic) está implementado y probado con dobles del SDK. Las pruebas automatizadas no hacen ninguna llamada real. Ninguna llamada real se ha ejecutado en el desarrollo.
- El juicio literario de Claude no está evaluado. El backend comprueba forma, citas, posiciones, procedencia y ausencia de atribuciones de intención, pero no si el diagnóstico es acertado.
- No se registra el uso de tokens ni el coste por análisis.
- Sin editor enriquecido (Tiptap): el texto se edita en áreas de texto simples.
- Sin exportación ni copias automáticas de la base de datos.
- El autoguardado necesita el backend en marcha. Si cae o no hay conexión, el texto sigue en el editor, el indicador lo dice y no se confirma como guardado hasta que el servidor responda. Un cierre de la pestaña con cambios sin confirmar muestra un aviso del navegador, pero el envío de último recurso no tiene garantía.
- El benchmark de `evals/` (tarea 001) no está conectado a los textos del usuario.
