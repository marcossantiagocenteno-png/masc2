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
**Estado:** superada por D-045 a D-047 (fase 1c)

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
**Estado:** superada por D-045 a D-047 (fase 1c)

No se han implementado copias automáticas en esta fase. Copiar un archivo SQLite mientras se escribe exige la API de copia en caliente de SQLite, una rotación con límite de retención y una restauración probada. Mezclarlo con el borrador añadía riesgo a la parte que ya funciona. Es la primera tarea de la siguiente fase de persistencia.

## D-045 · Copias con la API de backup de SQLite, verificadas antes de nombrarse
**Estado:** aceptada

La copia usa la API de backup de SQLite, dentro de una lectura abierta: todo el contenido corresponde a una única instantánea, y las escrituras concurrentes esperan lo que dura la copia. No se copia por pasos ni con una copia de archivo, porque el módulo `sqlite3` reintenta indefinidamente los errores `BUSY` de la API: un escritor que retuviera el bloqueo dejaría la copia colgada. Se observó colgarse en una ejecución real de la línea de comandos. Una copia se verifica en un temporal (se abre en solo lectura, `PRAGMA integrity_check` = `ok`, tablas requeridas, versión de esquema conocida) y solo después se renombra. Nunca se sobrescribe una copia: dos copias en el mismo instante reciben nombres distintos. La rotación se hace después de crear y verificar la copia nueva. Una copia fallida no borra nada.

## D-046 · Programación dentro del backend, bloqueo de carpeta y marcador de ejecución
**Estado:** aceptada. El criterio del marcador se ha sustituido por D-049.

Las copias automáticas corren en un hilo del backend, cada 60 minutos por defecto (`NOVEL_ENGINE_BACKUP_INTERVAL_MINUTES`). La lógica está en `tick`, sin hilos, para que las pruebas la controlen con un reloj. Un bloqueo por creación exclusiva de archivo (`.backup.lock`) impide dos copias a la vez, y también una copia y una restauración; funciona igual en Linux y Windows. Un bloqueo de más de dos horas se considera abandonado y se retira. Mientras el backend corre, existe el marcador `.app-running`: la restauración se niega mientras exista. Un cierre brusco deja el marcador; entonces hay que usar `--ignorar-marcador` tras comprobar que no hay ningún proceso.

## D-047 · Restauración administrativa, con copia preventiva y reversión
**Estado:** aceptada

La restauración es un comando (`python -m app.backups restaurar --confirmar`), no una función de la interfaz, porque reemplaza la base con la aplicación detenida. Orden: rechazar si el marcador existe; verificar la copia (integridad, esquema conocido, hash del manifiesto); bloquear la base activa en exclusiva (si otro proceso la usa, rechazar); guardar la copia preventiva y verificarla; crear el temporal desde la copia y verificarlo; reemplazar; verificar de nuevo. Si la verificación posterior falla, se devuelve la preventiva. Ninguna copia de esquema anterior se restaura sin `--permitir-esquema-anterior`, y nunca se ejecutan migraciones durante la restauración. La copia preventiva se hace como copia de archivo porque, con el bloqueo exclusivo, el archivo es consistente; la API de backup desde esa conexión se colgaba (ver D-045).

## D-048 · Retención sin borrado automático en esta fase
**Estado:** aceptada

Los triggers de `draft_recovery_points` impiden `DELETE`, y la inmutabilidad debe mantenerse. Por tanto, esta fase no borra puntos. Se implementan métricas (`retencion`) y una vista previa de candidatos. Un punto solo sería candidato si: es `periodico` o `significativo`; tiene más de 90 días; no está entre los 20 más recientes de su manuscrito; y existe una copia verificada que contiene ese mismo punto (mismo id y hash). Los motivos `conflicto`, `antes_de_sobrescribir` y `antes_de_restaurar` nunca son candidatos. Una prueba comprueba que el módulo no expone ninguna operación de borrado. La eliminación real queda para una fase con migración y pruebas propias.

## D-049 · Marcador con latido: un marcador caducado no basta por sí solo
**Estado:** aceptada (fase 1d)

Un marcador con PID no distingue un backend vivo de uno abandonado tras un cierre brusco: el PID puede haberse reutilizado, y en otra máquina o contenedor la comprobación no significa nada. Por eso el backend renueva el latido del marcador cada 30 s. La restauración considera el marcador **abandonado** solo si el latido lleva más de 3 minutos caducado **y** el sistema confirma que el proceso ya no existe. Si no puede confirmarlo, el estado es desconocido y la restauración se niega. Nada borra el marcador automáticamente salvo el cierre limpio del backend. Además, la base activa debe poder bloquearse en exclusiva (D-047). Limitación conocida: la comprobación del proceso en Windows (API del sistema con `ctypes`) no se ha ejecutado en Windows.

## D-050 · Cifrado de las copias: evaluado, no implementado
**Estado:** aceptada (no implementar todavía)

Las copias contienen el texto legible. Se evaluaron tres opciones.

1. **Cifrado de la aplicación** con una biblioteca mantenida (por ejemplo `cryptography`, con AES-GCM y una clave derivada de una frase de paso). Es técnicamente viable, pero hoy no se implementa porque: (a) la clave tendría que gestionarse, y si se pierde las copias son irrecuperables; (b) no hay un procedimiento de recuperación de claves documentado ni probado; (c) el simulacro y la restauración tendrían que descifrar, y eso no se ha probado en Windows. Un error aquí puede borrar de forma irreversible la única copia del trabajo. Por eso no se añade.
2. **Cifrado del volumen del sistema** (BitLocker, FileVault o LUKS) sobre la carpeta de copias. Es la protección recomendada ahora, porque la gestiona el sistema operativo y su recuperación la controla el propio sistema.
3. **Herramientas externas** (por ejemplo, `age`). Añaden una dependencia y el mismo problema de gestión de claves.

Criterios para revisar la decisión: un procedimiento de recuperación de claves escrito y probado, una prueba de descifrado con clave incorrecta, y un simulacro de restauración que incluya el descifrado, ejecutado en cada sistema operativo que se soporte.

## D-051 · Simulacro de restauración reproducible en cualquier sistema
**Estado:** aceptada

`python -m app.backups simulacro` crea una base temporal, hace una copia, cambia el borrador, restaura y comprueba el resultado. No toca los datos del usuario. Sirve para verificar la restauración en una máquina concreta. Se ha ejecutado en Linux. **No se ha ejecutado en Windows**: en el entorno de desarrollo no hay Windows disponible. Un resultado `SIMULACRO CORRECTO` en Windows es la única prueba real de ese sistema.

## D-052 · Crecimiento visible, sin borrado automático
**Estado:** aceptada

Los puntos de recuperación crecen con el uso. `retencion` muestra el número de puntos, el crecimiento por día, y avisa si la base supera 200 MB o si el crecimiento estimado supera 100 MB al año. La estimación usa 2 bytes por carácter, un término medio para texto en español, y es orientativa. Se mantiene D-048: no hay borrado automático de puntos.

## D-053 · La novela es el proyecto: se reutiliza `projects` en lugar de crear otra tabla
**Estado:** aceptada (fase 2a)

`projects` ya es la novela: tiene identidad propia, archivado y aislamiento. La premisa, la sinopsis, el género, el tema, el tono y el estado de desarrollo se añaden como columnas nulables a esa tabla (migración 0006), en lugar de una tabla paralela con la misma identidad. Es un cambio aditivo: los proyectos y manuscritos existentes no se modifican. Los campos narrativos del proyecto no tienen estado de canon todavía: son la definición del propio autor. Si un día la premisa puede venir de la IA, tendrá que incorporar el mismo mecanismo que el resto (pendiente).

## D-054 · Canon: estado y origen en cada elemento, cambios solo por operaciones explícitas
**Estado:** aceptada (fase 2a)

Cada entidad tiene `estado` (`provisional`, `propuesta_ia`, `canonico`) y `origen` (`autor`, `ia`). Solo cinco operaciones cambian el estado, y todas registran una fila en `narrative_decisions` con la instantánea anterior:

- **Aprobar** (provisional o propuesta → canónico): exige `confirmar=true`. Sin él, 422 y nada cambia.
- **Aceptar propuesta** (propuesta → provisional): la deja como material del autor, no como canon. El `origen` no se borra.
- **Modificar un canónico**: exige `confirmar_cambio_canon=true`. Sin él, 409 y nada cambia. Con él, el elemento vuelve a provisional y la decisión guarda cómo era.
- **Archivar un canónico**: exige `confirmar_canon=true`.
- **Crear o editar propuestas y provisionales**: libre. Editar una propuesta no la convierte en canon.

Ninguna operación acepta el campo `estado` en el cuerpo de la petición (422). La tabla `narrative_decisions` es de solo inserción, con triggers como el resto del historial. Queda preparada para historial y análisis de impacto sin construir ahora un sistema de auditoría.

## D-055 · Vínculos tipados, con vocabulario en código y validación en el servicio
**Estado:** aceptada (fase 2a)

Las relaciones entre entidades son una sola tabla `narrative_links` con extremos tipados (`source_kind`/`source_id`, `target_kind`/`target_id`). Una tabla por cada par de tipos habría multiplicado las tablas sin ganar integridad real, porque los extremos son polimórficos de todos modos. Lo que sí se garantiza:

- El par de tipos y la relación deben estar en el registro (`app/planning/kinds.py`). Añadir un vínculo nuevo es añadir una línea allí, sin migración.
- Ambos extremos deben existir, pertenecer al mismo proyecto y no estar archivados. Si no, 404 o 422, y nada se escribe.
- No puede haber dos vínculos iguales (409).

Limitación conocida: sin clave foránea real, la integridad de los extremos depende del servicio. Como nada borra elementos (solo archiva), no pueden quedar vínculos huérfanos por borrado. Un chequeo de integridad explícito queda pendiente.

## D-056 · Estructura en un solo árbol; una escena existe antes que su prosa
**Estado:** aceptada (fase 2a)

Actos, capítulos y escenas viven en `structure_nodes`, con `parent_id` y `position` entre hermanos. Reordenar cambia `position`, no `id`: una escena conserva su identidad y sus vínculos al moverse. Las reglas de jerarquía (un acto solo en raíz; un capítulo en raíz o en acto; una escena en raíz, acto o capítulo) están en el servicio. Una escena no tiene texto: vincular una escena a un fragmento del manuscrito se hará más adelante con una tabla propia que apunte al nodo, para no duplicar ni mezclar contenidos. Mover un nodo a otro padre no está soportado todavía: solo se reordena entre hermanos.

## D-057 · Integridad de los vínculos: el servicio valida y la base lo confirma
**Estado:** aceptada (fase 2a.1)

La auditoría encontró que la base aceptaba cualquier par de ids: un `INSERT` directo podía crear un vínculo entre dos novelas, hacia un elemento archivado o con un tipo inventado. Se añaden triggers en `narrative_links` (migración 0007) que rechazan la inserción, y el cambio de extremos, cuando un extremo no existe, está archivado, es de otro proyecto o no tiene un tipo válido. Motivo: el servicio sigue siendo la vía normal, pero la base debe rechazar también una escritura que la evite.

No se usan claves foráneas para los extremos, porque son polimórficos (un id puede apuntar a tablas distintas). Los triggers cubren lo que una clave foránea no puede expresar. La relación concreta (el par de tipos) sigue validándose solo en el servicio, desde el registro de `kinds.py`, para no duplicar el vocabulario en SQL.

La migración comprueba antes que los vínculos existentes cumplen la regla. Si no, falla sin aplicar nada. Un extremo archivado después de crear el vínculo sigue siendo legítimo: el vínculo no se borra ni se archiva por ello.

Carrera: dos peticiones pueden pasar la comprobación de duplicados. La segunda falla en el `INSERT` por la restricción única; el servicio lo convierte en 409 solo si el duplicado existe, y en 422 si el rechazo es de otra causa (p. ej. el disparador).

## D-058 · Historial de canon: actor, estado resultante y atomicidad
**Estado:** aceptada (fase 2a.1)

Cada decisión de canon registra:

- `actor`: quién la origina. Hoy solo `autor`. El servicio ya rechaza cualquier otro actor para aprobar, aceptar propuestas y modificar o archivar canon. Así la IA no puede convertir una propuesta en canon aunque se conecte algún día.
- `snapshot`: el elemento antes del cambio.
- `resultado`: el elemento después del cambio (migración 0007; las decisiones anteriores lo tienen vacío).
- `estado_previo` y `estado_nuevo`, y la `nota` del autor.

Las decisiones son de solo inserción, así que `resultado` se calcula antes de insertar. En `aprobar_canon` no incluye `approved_decision_id`, porque su valor es el id de la propia decisión, que todavía no existe. El vínculo queda en el elemento y en la decisión.

Atomicidad: cada operación que escribe está envuelta en un decorador que deshace la sesión ante cualquier excepción. Antes, una confirmación fallida dejaba el cambio en la sesión y la siguiente operación lo persistía. Probado con un fallo simulado al confirmar.

Limitación deliberada: solo se registran decisiones de canon. Editar un elemento provisional o una propuesta no deja historial. Un historial completo de cambios no se ha construido todavía.

## D-059 · Datos generales de la novela sin protección de canon
**Estado:** aceptada (fase 2a.1)

Premisa, sinopsis, género, tema y tono (y el estado de desarrollo) son columnas de `projects`. Hoy se pueden cambiar en cualquier momento sin confirmación, no tienen estado de canon, no registran decisiones y no dejan historial. Es una decisión consciente: son la definición de la novela que escribe el autor, y ninguna IA las propone todavía. Antes de integrarlas en el sistema de canon hace falta: estado y origen por campo (o un registro de versiones de la premisa), decisiones de canon con su instantánea, y una confirmación en la interfaz. La interfaz debe mostrar esta diferencia, para que el autor no crea que estos campos están protegidos.

## D-060 · Interfaz de planificación: confirmaciones en línea, reordenación con botones, sin movimiento entre padres
**Estado:** aceptada (fase 2b)

Las acciones sobre canon (aprobar, modificar un canónico, archivar) muestran en la propia ficha una confirmación con la casilla explícita y el texto de lo que cambia. Se prefiere a un diálogo del navegador porque el texto y la casilla se leen antes de confirmar y el mensaje de la API se muestra donde corresponde. Si la API rechaza la acción (409 por falta de confirmación), la interfaz no reintenta con la confirmación marcada: el cambio se queda sin aplicar.

Reordenar escenas usa botones «Subir» y «Bajar», no arrastre. La API solo reordena entre hermanos y no mueve un nodo a otro padre: no se presenta como disponible. Una escena se identifica por su id en la URL, así que reordenar no cambia su dirección ni sus vínculos.

Los vínculos de una escena se crean y se retiran con las operaciones de la API. Retirar un vínculo lo archiva (no se borra), en línea con el resto del sistema.

Las etiquetas de los formularios se asocian a su control con `htmlFor`. Un `label` que envuelve un `select` incluye el texto de todas sus opciones, y eso rompía el nombre accesible del campo.

---

## D-061 · Reorganización de la estructura: revisión, confirmación previa de canon y navegación sin vínculos automáticos
**Estado:** aceptada (fase 2c)

**Revisión de la estructura (migración 0008).** Dos operaciones sobre la misma vista podían pisarse en silencio: la segunda reescribía la primera sin aviso. No hay una columna que detecte cambios en la estructura completa, así que cada escritura de estructura hace primero un `UPDATE` condicional sobre `projects.structure_version` y solo continúa si la revisión leída sigue vigente. Si no, responde 409 y no cambia nada. Se eligió una columna en el proyecto y no un bloqueo de tabla porque la base es SQLite y las escrituras ya son cortas y atómicas. La migración solo añade la columna con valor 0; no toca datos. Su retroceso no está implementado, como en el resto de migraciones.

**Movimiento.** Un nodo cambia de padre solo a un padre compatible (la misma regla de tipos que la creación), nunca a un nodo archivado, nunca dentro de su propio subárbol y nunca de otro proyecto. El movimiento conserva el id, los datos, el estado de canon y los vínculos del nodo. Va al final de los hermanos del destino y compacta el origen. Mover no cambia el canon.

**Canon.** Si un movimiento o una reordenación cambia la posición de un elemento canónico, el servidor exige `confirmar_cambio_canon` y registra una decisión (`reubicar` o `reordenar`) con el estado sin cambios. La interfaz calcula los mismos cambios antes de enviar, muestra qué elementos canónicos se afectan y solo envía la operación tras la casilla de confirmación. El cálculo de la interfaz es una vista previa: el servidor vuelve a decidir con sus propios datos.

**Errores.** La interfaz nunca muestra éxito sin respuesta del servidor. Un rechazo conserva la vista tal como estaba, explica el motivo y ofrece «Actualizar la estructura». Si un cambio de nodo tiene texto sin guardar, se pide confirmación antes de mover o reordenar, porque la recarga reemplaza el formulario.

**Navegación.** Desde una escena se abren sus personajes, lugares y elementos de trama con `?seleccionado=id`. Desde un personaje, lugar o elemento de trama se listan sus escenas, con los archivados marcados. Ninguna de las dos vistas crea vínculos: solo se crean desde la escena, con la operación de la API.

**Límites deliberados.** El movimiento no permite elegir una posición intermedia entre los hermanos (siempre va al final; el orden se cambia con Subir y Bajar). No hay arrastre. La vista de la estructura no compara su versión con la del servidor antes de mostrar el árbol: un cambio hecho en otra pestaña se detecta al operar, no al mirar.

## D-062 · Escritura de escenas: un manuscrito propio por escena, unido por una tabla
**Estado:** aceptada (fase 2d)

**Diseño anterior.** El manuscrito es el contenedor de texto: tiene versiones inmutables (`manuscript_versions`), un borrador único y mutable (`manuscript_drafts`, una fila por manuscrito) y puntos de recuperación inmutables (`draft_recovery_points`). El proyecto agrupa manuscritos por `project_id`, pero las rutas `/manuscripts/{id}/…` no comprueban el proyecto. No había unidades de escritura más pequeñas que el manuscrito.

**Decisión.** Cada escena puede tener un manuscrito propio, unido por la tabla `scene_manuscripts` (migración 0009): `node_id` y `manuscript_id` son únicos, y `project_id` debe coincidir con ambos. El texto de una escena es el borrador de su manuscrito, y sus versiones y puntos de recuperación son los de siempre: no hay copias. Así D-056 se cumple: la escena es el nodo, el texto está en el manuscrito, y la unión no depende del título ni de la posición.

**Reglas.** Iniciar la escritura crea, en una transacción, el manuscrito, su versión 1 vacía y su borrador. Es idempotente: una segunda petición, incluso concurrente, recibe la unión existente y el intento se deshace entero. La base impide unir un acto o un manuscrito de otro proyecto, y la fila es inmutable (no se actualiza ni se borra). Mover la escena no toca la unión. Renombrarla copia el título al manuscrito en la misma transacción, para que ambos nombres no se separen; el título del manuscrito es solo una copia. Una escena archivada conserva su texto, pero no admite escritura nueva. Un proyecto archivado no admite iniciar ni guardar.

**Guardado.** Escribir desde la escena usa el mismo `DraftSaver` y el mismo `DraftStatus` que el manuscrito: escritura condicional por revisión, 409 que conserva el texto, reintento y «Guardado» solo tras la respuesta del servidor. Los endpoints de escena (`/estructura/{id}/escritura`) comprueban el proyecto a través del nodo; los endpoints de manuscrito existentes no se han cambiado.

**Versiones formales.** Guardar como versión sigue siendo una acción explícita, en la página del manuscrito. Desde la escena se enlaza a esa página, pero no se duplica el editor de versiones: un guardado ordinario nunca crea una versión.

**Consecuencias visibles.** Los manuscritos de escena no aparecen en la lista de manuscritos del proyecto (sí en `/manuscritos`, con el título copiado). La estructura muestra «Sin escritura», «Sin texto» o «Con texto» en cada escena.

**Límites deliberados.** Una escena es un manuscrito completo: no hay fragmentos dentro de un manuscrito compartido, y no se reparte un manuscrito entre varias escenas. Las versiones y los puntos se gestionan en la página del manuscrito, no dentro de la ficha de escena. Ninguna operación usa IA ni reescribe texto.

## D-063 · Pertenencia de manuscritos a proyectos y fuente de verdad del título
**Estado:** aceptada (fase 2e)

**Pertenencia.** Las rutas heredadas (`/manuscripts/{id}/…`) no reciben proyecto, así que no pueden comprobar pertenencia. Las rutas nuevas `/projects/{p}/manuscripts/{m}/…` (`app/projects/scoped_routes.py`) sí la comprueban: el manuscrito debe existir y pertenecer a `p`. Un id de otro proyecto y un id inexistente dan la misma 404, para no revelar en qué novela existe un manuscrito. Las escrituras acotadas exigen proyecto activo, como la planificación. Es aislamiento entre novelas, no autenticación: la aplicación sigue siendo local y de un solo usuario.

**Compatibilidad.** La interfaz usa `manuscriptOps(projectId, manuscriptId)`: si el manuscrito tiene proyecto, usa las rutas acotadas; si no, las heredadas. No cambia ninguna URL de página ni ningún contrato de respuesta existente. El resumen del manuscrito gana dos campos (`project_id`, que ya existía en la API, y `scene_node_id`).

**Escrituras heredadas sobre escenas.** Guardar un borrador, restaurar un punto y crear una versión por la ruta heredada se rechazan (422) si el manuscrito es el texto de una escena. Sin esta guarda, esas rutas saltarían el archivado de la escena y la pertenencia. Las lecturas heredadas siguen abiertas, y los manuscritos sin proyecto siguen funcionando igual.

**Título.** La escena es la única fuente de verdad del título de su manuscrito. Ninguna interfaz ni ruta edita el título de un manuscrito: lo fija su creación y, si es de escena, lo copia la escena al renombrarse, en la misma transacción. Un fallo de sincronización deshace el renombrado completo (no quedan títulos contradictorios). La página del manuscrito de escena lo indica y enlaza a la escena. Los manuscritos independientes no se tocan. Así no hay sincronizaciones recursivas ni actualizaciones parciales.

**Límites que quedan.** Las revisiones editoriales y el análisis siguen en rutas por id de versión (no comprueban proyecto). No modifican borradores ni textos, pero sí crean registros, así que quedan como límite conocido. Las lecturas heredadas (`/manuscripts/{id}`, `/versions/{id}`, puntos) siguen aceptando ids de cualquier proyecto para los manuscritos sin proyecto. Restaurar una copia anterior a 0009 sin migrar dejaría sin tabla `scene_manuscripts`: hay que ejecutar `alembic upgrade head` tras restaurar.

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
| **Cifrado de las copias** | Las copias contienen el texto legible; no hay cifrado propio (D-050). | Cuando exista procedimiento de recuperación de claves probado. |
| **Copias fuera del equipo** | Solo hay copias locales; copiar a otro disco es manual. | Decisión del autor sobre dónde guardarlas. |
| **Prueba de restauración en Windows** | No se ha podido ejecutar: no hay Windows en el entorno de desarrollo (D-051). | Ejecutar `python -m app.backups simulacro` en Windows. |
| **Campos generales de la novela sin canon** | Premisa, sinopsis, género, tema y tono cambian sin protección (D-059). | Antes de que la IA pueda proponerlos. |
| **Planificación: contradicciones y análisis de impacto** | La estructura lo permite (D-054, D-055); no se ha implementado. | Fase posterior. |
| **Eliminación de puntos de recuperación** | Los triggers la impiden; la vista previa no borra nada (D-048). | Fase con migración propia. |
| **Paquete de proyecto restaurable** | Sin exportación ni importación completa. | Fase 5. |
| **Autenticación** | Imprescindible antes de exponer la aplicación en red. | Antes de cualquier despliegue. |
| **Pesos de las dimensiones** | La fase 0 no combina puntuaciones. | Cuando exista una evaluación completa. |
