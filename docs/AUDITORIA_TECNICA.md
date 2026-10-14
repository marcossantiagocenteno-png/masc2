# Auditoría técnica de Novel Engine

Fecha de la auditoría: sesión de implementación de la especificación «Novel Engine». Rama `claude/beautiful-hypatia-5613so`, línea base `cd71a14`.

Este documento separa lo que se ha **comprobado** (con pruebas o con ejecución real en este entorno) de lo que solo se ha **leído** en el código. Cuando una afirmación no se ha comprobado, se indica.

## 1. Resumen

Novel Engine es, hoy, un **gestor de versiones de texto con análisis editorial de fragmentos**. No es todavía una herramienta de trabajo novelesco. Lo que existe es sólido en su núcleo (versiones inmutables, citas verificadas, análisis con garantías de privacidad). Falta casi toda la capa de trabajo: planificación, personajes, estructura, memoria, tareas, respaldo y exportación.

Antes de implementar nada nuevo, la auditoría encontró dos riesgos reales de pérdida de datos. Ambos están tratados o documentados en esta entrega (ver sección 5).

## 2. Qué existe realmente

| Funcionalidad | Estado | Cómo se ha verificado |
|---|---|---|
| Crear manuscrito con versión 1 | Implementado y probado | Pruebas de backend y E2E |
| Crear versión nueva (inmutable, con hash SHA-256) | Implementado y probado | Pruebas de inmutabilidad (SQL y ORM), E2E |
| Partir de una versión anterior (crea una versión nueva) | Implementado y probado | Pruebas de servicio y E2E |
| Comentarios editoriales con cita literal exacta | Implementado y probado | Pruebas de servicio, API y E2E |
| Análisis editorial con analizador **simulado** | Implementado y probado | Pruebas y E2E. El simulador **no es una IA**; solo cuenta frases y detecta tres errores mecánicos |
| Proveedor real Anthropic | Implementado; **probado solo con dobles del SDK** | Pruebas con dobles. **Ninguna llamada real se ha realizado.** |
| Autorización de envío externo por petición | Implementado y probado | Pruebas de API y E2E con proveedor mock en navegador |
| Proyectos aislados (crear, renombrar, archivar, restaurar) | **Implementado en esta entrega** | Pruebas de backend y E2E |
| Migración de manuscritos existentes a «Proyecto inicial» | **Implementado en esta entrega** | Prueba de migración con datos reales |
| Edición segura al cambiar la versión de partida | **Corregido en esta entrega** | Pruebas E2E (tres casos, incluida la de carrera) |
| Copia de seguridad automática | **No existe** | Solo es posible copiar el archivo SQLite a mano (ver RESPALDO_Y_RESTAURACION.md) |
| Autoguardado y puntos de recuperación | **No existen** | El editor es un área de texto: solo se guarda al pulsar «Guardar como nueva versión» |
| Historial con restauración desde la interfaz | **No existe** | Las versiones existen en la base de datos, pero no hay interfaz para restaurar |
| Planificación, personajes, capítulos, escenas | **No existen** | — |
| Memoria narrativa, tareas, decisiones, métodos | **No existen** | — |
| Importación (DOCX, TXT, Markdown) | **No existe** | — |
| Exportación del manuscrito | **No existe** | — |
| Preferencias literarias (generales y por proyecto) | **No existen** | — |
| Autenticación | **No existe** | Diseñado para un solo usuario en `localhost` |

**Componentes visuales sin función operativa:** ninguno detectado. La página de inicio lista como «pendiente» el editor Tiptap y la generación de novelas; no hay botones decorativos.

## 3. Modelo de datos

Tablas (migraciones 0001 a 0004):

- `manuscripts`: título, fecha y, desde 0004, `project_id` (nulo para manuscritos creados antes de los proyectos).
- `projects`: nombre, estado (`activo` o `archivado`), fechas. Sin borrado: solo archivado.
- `manuscript_versions`: contenido normalizado, número correlativo, SHA-256, recuento, nota, origen. **Inmutable**.
- `editorial_reviews`, `review_items`: comentarios con cita. **Inmutables**.
- `analysis_runs`, `analysis_findings`: análisis con fragmento, proveedor, modelo y justificación. **Inmutables**.

Relaciones: el proyecto contiene manuscritos; el manuscrito contiene versiones; las versiones tienen revisiones y análisis. No hay relaciones entre proyectos.

**Hallazgo de integridad (corregido):** durante la migración 0004, un intento anterior añadió la columna `project_id` sin clave foránea en la base de desarrollo. `alembic check` lo detectó. La base de desarrollo se regeneró desde las migraciones (con copia de seguridad previa). Regla para el futuro: **nunca editar una migración ya aplicada**; cada cambio va en una migración nueva.

## 4. Flujos principales, comprobados

- **Crear un proyecto y un manuscrito dentro de él:** funciona; probado en E2E con dos proyectos independientes.
- **Escribir:** el editor es un área de texto. Lo escrito **no se guarda hasta pulsar «Guardar como nueva versión»**. Si el autor cierra la pestaña o recarga, el texto no guardado se pierde. Confirmado por lectura del código y por la ausencia de autoguardado. No se ha medido el alcance de la pérdida en un navegador real.
- **Guardar:** crea una versión inmutable. Si falla la red, se muestra el error, pero el texto solo sobrevive si sigue en el área de texto.
- **Cambiar de versión de partida:** antes de esta entrega, sustituía el texto sin avisar. **Reproducido con una prueba que falló**, y corregido. Además, se detectó una carrera: la carga asíncrona de la versión de partida podía sustituir lo escrito durante la carga. **Reproducido de forma determinista**, corregido, y probado.
- **Analizar un fragmento:** funciona con el simulador (E2E). Con el proveedor real, **no verificado**.
- **Guardar análisis:** inmutable; persiste tras recargar (E2E).

## 5. Riesgos de pérdida de datos

| Riesgo | Gravedad | Estado |
|---|---|---|
| Texto escrito sin guardar se pierde al recargar o cerrar | **Alta** | Abierto. Se trata en la fase de persistencia (autoguardado + puntos de recuperación). |
| Sustitución silenciosa del texto al cambiar de versión | Alta | **Corregido** (confirmación + prueba) |
| Sustitución del texto durante la carga asíncrona | Alta | **Corregido** (prueba determinista) |
| Único archivo SQLite sin copias automáticas | Alta | Abierto. Respaldo manual documentado y probado; automático pendiente. |
| Migración que deja la base en un estado inconsistente | Media | Mitigado: migraciones probadas sobre datos; 0004 no reversible automáticamente, con procedimiento de copia |
| Eliminación accidental de manuscritos | Baja | Mitigado: no hay endpoint de borrado; las versiones son inmutables |
| Envío de texto a un proveedor externo sin consentimiento | Alta si ocurriera | Mitigado: autorización por petición, probada con dobles; verificación real pendiente |

## 6. Seguridad y privacidad

- **Autenticación:** no existe. Válido para un usuario en `localhost`; no debe exponerse en red.
- **Clave de Anthropic:** solo en la configuración del backend, oculta en `repr`, nunca en respuestas ni logs (probado).
- **Logs:** el adaptador de Anthropic registra solo metadatos (probado: no aparecen claves, fragmentos, comentarios ni títulos).
- **Respuestas de error:** la validación de FastAPI (422) puede repetir el valor enviado en el cuerpo de la respuesta. Es tráfico entre el navegador local y la API local, pero conviene vigilarlo si la API se expone.
- **CORS:** limitado a `localhost:3000` y `127.0.0.1:3000` por defecto.
- **Datos fuera del equipo:** solo con el proveedor real configurado y con autorización por petición. Lo que Anthropic hace con los datos depende de sus condiciones: no verificado.

## 7. Deuda técnica

- **Duplicación leve:** funciones de conversión de versiones repetidas en `texts/routes.py` y `analysis/routes.py`. No es urgente.
- **Componentes grandes:** `AnalysisPanel.tsx` (≈400 líneas) y la página de versión (≈340 líneas) mezclan estado, llamadas y presentación. Deberían dividirse antes de añadir más funciones.
- **Cliente API en un solo archivo** (`lib/api.ts`), que crece con cada módulo. Aceptable hoy; separar por dominio cuando haya más de cuatro.
- **Sin gestor de estado:** cada pantalla gestiona su estado con `useState`. Suficiente para lo actual; insuficiente para el autoguardado y la sincronización entre paneles que exige la especificación.
- **Efectos al importar:** `app/main.py` crea la aplicación y el motor al importarse. Es conveniente para `uvicorn`, pero dificulta reconfigurar en pruebas.
- **Módulo `benchmark`** (tarea 001) no forma parte del flujo del producto. Se mantiene: tiene pruebas y forma parte del historial.
- **Documentación duplicada:** configuración en README y en `.env.example`; arquitectura en `docs/architecture.md`. La especificación pide no duplicar: se actualizan los existentes.
- **Avisos de dependencias:** `starlette.testclient` avisa de `httpx` (no afecta al resultado).
- **Configuración de Playwright:** la ruta de Python por defecto es POSIX (`.venv/bin/python`). Para Windows hay que usar `NOVEL_ENGINE_PYTHON`.

## 8. Pruebas: qué cubren y qué no

Estado tras esta entrega:

- Backend: **274 pruebas** en total, incluidas las 65 de la tarea 001. Cubren modelos, validación, API, inmutabilidad, análisis, proveedor real con dobles, autorización, migraciones, proyectos y recuperación por copia. Todas pasan.
- Playwright: **10 pruebas**, ejecutadas tres veces seguidas sin fallos.

Lo que las pruebas **no** cubren:

- La llamada real a Anthropic (solo dobles del SDK).
- Restauración desde la interfaz (no existe).
- Recuperación ante cierre inesperado del navegador (no existe autoguardado).
- Comportamiento en Windows (las pruebas se han ejecutado en Linux).
- Carga, concurrencia y tamaños grandes más allá de 500 000 caracteres.

## 9. Conclusión

La base técnica es correcta en lo que construye: inmutabilidad, citas verificables, privacidad por petición, migraciones con datos. Los riesgos de pérdida de texto son lo más urgente. La prioridad inmediata, por encima de la planificación, es la persistencia fiable: autoguardado, puntos de recuperación y copias. El plan de implementación refleja ese orden.
