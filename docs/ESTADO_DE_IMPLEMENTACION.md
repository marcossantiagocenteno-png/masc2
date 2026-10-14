# Estado de implementación

Fecha de corte: esta entrega. Cada afirmación indica cómo se ha comprobado.

## Implementado y probado

- **Manuscritos y versiones inmutables** con hash SHA-256. Pruebas de servicio, API, inmutabilidad (SQL y ORM) y E2E.
- **Partir de una versión anterior** crea una versión nueva. Pruebas de servicio y E2E.
- **Comentarios con cita literal exacta**, validada contra la versión. Pruebas de servicio, API y E2E.
- **Análisis editorial con analizador simulado**, identificado como simulado en la API y en la interfaz. Pruebas y E2E.
- **Autorización de envío externo por petición**: sin ella no hay llamada externa (403). Pruebas de API y E2E con proveedor mock en el navegador.
- **Proyectos aislados**: crear, renombrar, archivar, restaurar, listar activos o archivados. Pruebas de backend (`test_projects.py`) y E2E.
- **Migración de datos a proyectos**: los manuscritos existentes pasan a «Proyecto inicial» sin tocar sus textos. Prueba de migración con datos.
- **Edición segura de la versión de partida**: confirmación antes de sustituir texto sin guardar, y protección frente a la carga asíncrona. Pruebas E2E (tres casos).
- **Recuperación por copia de la base de datos**: restaurar una copia devuelve el estado anterior, y la copia conserva los triggers. Pruebas de backend.
- **Marcador con latido** (fase 1d): el backend renueva el marcador cada 30 s. Un marcador caducado solo se considera abandonado si el sistema confirma que el proceso terminó; si no puede confirmarlo, la restauración se niega. Nunca se borra automáticamente. Pruebas: 11 de marcador (incluida una con un proceso real terminado).
- **Simulacro de restauración** (fase 1d): `python -m app.backups simulacro`, reproducible en cualquier sistema. Ejecutado en Linux; pendiente en Windows.
- **Advertencias de crecimiento** (fase 1d): `retencion` avisa al superar 200 MB o 100 MB al año estimados.
- **Núcleo de planificación narrativa** (fase 2a): personajes, lugares, elementos de trama, acontecimientos, estructura (actos, capítulos y escenas) y vínculos tipados, con estado de canon (provisional, propuesta de IA, canónico) y decisiones de canon registradas. Pruebas: 30 de planificación, 3 de migración y 2 de verificación de copias con tablas nuevas. Siete mutaciones de reglas de canon, aislamiento y atomicidad se detectan. Aislado por proyecto (probado). Sin interfaz de planificación.
- **Copias de seguridad automáticas** (fase 1c): API de backup de SQLite en una lectura consistente; verificación de integridad y esquema antes de nombrar la copia; rotación por cantidad y antigüedad que nunca borra antes de crear y verificar la nueva; nombres que nunca se sobrescriben; registro operativo sin texto. Pruebas: 17 de copias, 9 de restauración, 9 de retención y 4 de línea de comandos (39 en la fase; 335 en total). Siete mutaciones deliberadas de las reglas de seguridad (verificación previa, rotación, bloqueos, instantánea, copia preventiva, retención de conflictos) hacen fallar al menos una prueba.
- **Restauración administrativa** (fase 1c): rechaza sin tocar la base si la copia es inválida, si el hash no coincide, si la base está en uso o si el backend parece en marcha; copia preventiva antes de reemplazar; reversión automática si la verificación posterior falla. Probado en Linux. **No probado en Windows.**
- **Retención de puntos**: métricas y vista previa de candidatos. No borra nada (D-048).
- **Migraciones 0001 a 0006** aplicadas y comprobadas con `alembic check`. La 0005 crea solo tablas nuevas (borradores y puntos). La 0006 añade columnas nulables a `projects` y crea tablas de planificación; no modifica datos existentes.
- **Borrador persistente con autoguardado** (fase 1b): escritura condicional por revisión, 409 con texto preservado, indicador de estado que nunca muestra «guardado» sin confirmación del servidor, reintento, recuperación al abrir, puntos de recuperación con política documentada, restauración transaccional y aviso al salir con cambios pendientes. Pruebas: 18 de backend en `test_drafts.py` (incluida una de concurrencia con lectura obsoleta forzada), 4 de migración en `test_migraciones_borradores.py`, 12 unitarias del guardado (`tests/unit`) y 7 E2E (`tests/e2e/borrador.spec.ts`). Comprobado también que la prueba de concurrencia falla si se quita la condición de revisión.

## Implementado, pero no verificado con servicios reales

- **Proveedor Anthropic**: el adaptador, la validación de respuestas, los errores y la autorización se prueban con dobles del SDK. **No se ha hecho ninguna llamada real**. La primera llamada requiere clave y tu autorización explícita (ver README, sección «Proveedor real»).

## Parcialmente implementado

- **Proyectos**: falta duplicar (con operación explícita y segura), vincular proyectos, preferencias por proyecto, hitos y actividad reciente completos, y el panel con pendientes.
- **Editor**: área de texto. Funciona para versiones, pero no tiene capítulos, escenas ni formato.
- **Análisis**: el simulador produce datos de longitud y tres comprobaciones mecánicas. No es un análisis literario.

## Pendiente

- Eliminación de puntos de recuperación: no existe. Requiere quitar la protección de los triggers con una migración propia (D-048).
- Cifrado de las copias y copias fuera del equipo (D-045).
- Restauración desde la interfaz: deliberadamente no existe (D-047).
- Paquete de proyecto restaurable (fase 5).
- Historial con restauración desde la interfaz (fase 3).
- Planificación, personajes, relaciones, cronología, capítulos y escenas (fase 2).
- Memoria narrativa, tareas, decisiones, métodos narrativos (fases 2 a 4 y 7).
- Importación DOCX, TXT y Markdown; exportación DOCX, PDF, TXT y EPUB (fase 5).
- Preferencias literarias generales y por proyecto (fase 2).
- Propuestas de IA integradas en el editor, con comparación y aceptación parcial (fase 6).
- Supervisión editorial continua y análisis de impacto (fase 7).
- Autenticación (imprescindible antes de cualquier despliegue en red).

## Bloqueado por credenciales o dependencias externas

- Llamada real a Anthropic: requiere clave de API y un identificador de modelo que tu cuenta admita. No se inventa ninguno.
- Exportación a EPUB: no se ha evaluado todavía si puede integrarse con garantías; se documentará si queda fuera.

## Pendiente de la planificación (fase 2a no lo incluye)

- Interfaz de planificación (fase 2b). Hoy solo hay API.
- Historial y restauración de decisiones desde la interfaz. El registro existe; la vista no.
- Mover un nodo de estructura a otro padre. Hoy solo se reordena entre hermanos.
- Restaurar elementos archivados (la operación inversa de archivar).
- Estado de canon para los campos narrativos del proyecto (premisa, sinopsis). Hoy son datos del autor sin estado.
- Escena vinculada a un fragmento del manuscrito (D-056).
- Análisis de contradicciones e impacto de una decisión. La estructura lo permite; no está implementado.
- Chequeo de integridad de los vínculos (sin clave foránea real, D-055).

## Riesgos abiertos (verificados al cierre de la fase 1d)

Cada riesgo indica si se ha comprobado o es una afirmación sin verificar.

- **Texto legible en las copias.** Las copias automáticas son bases SQLite sin cifrar. Cualquiera con acceso a la carpeta lee los manuscritos. Mitigación: cifrado del disco del sistema (BitLocker, FileVault o LUKS) y permisos de usuario. No hay cifrado propio: su recuperación de claves no está resuelta (D-050). **Abierto.**
- **Restauración no probada en Windows.** Todo lo verificado es de Linux. El simulacro existe (`python -m app.backups simulacro`), pero no se ha ejecutado en Windows porque el entorno de desarrollo no lo permite. **Abierto; no verificado.**
- **Comprobación de procesos en Windows.** La detección de procesos que han terminado usa la API de Windows vía `ctypes`. No se ha ejecutado allí. Si falla, la restauración se niega o, en el peor caso, depende del bloqueo de la base y del latido (ver RESPALDO). **Abierto; no verificado.**
- **Marcador de un backend en marcha en otra máquina.** La comprobación de procesos solo es válida en el mismo equipo. El latido es la señal principal, y un latido reciente siempre bloquea la restauración. **Mitigado; probado en el mismo equipo.**
- **Crecimiento de la base por puntos de recuperación.** Los puntos no se borran automáticamente (D-048). `retencion` avisa al superar 200 MB o 100 MB al año estimados. **Abierto; sin límite duro.**
- **Copias y disco en el mismo equipo.** Por defecto, `data/backups/` está en el mismo disco que la base. Un fallo de disco puede afectar a ambas. **Abierto: depende de la configuración del autor.**
- **Copias fuera del equipo.** No hay copias externas automáticas. **Abierto.**
- **Texto no guardado si el servidor cae antes de confirmar.** El indicador lo muestra y el texto sigue en pantalla, pero no está en ninguna copia. **Abierto; mitigado por la visibilidad del estado.**
- **Ejecución de pruebas en Linux.** Ninguna prueba de restauración se ha ejecutado en Windows ni en macOS. **Abierto.**
- **Autenticación.** No existe. Cualquiera con acceso a la red local a los puertos puede leer los datos. **Abierto; imprescindible antes de cualquier despliegue en red.**

Riesgos que se han cerrado en las fases 1b y 1c, con su evidencia:

- Texto escrito sin guardar se pierde al cerrar o recargar: mitigado con el borrador en servidor (1b, pruebas E2E).
- Único archivo de base de datos sin copias automáticas: mitigado con copias verificadas cada hora, rotación y restauración con copia preventiva (1c, pruebas y mutaciones).
- Marcador de backend obsoleto que bloquea la restauración: resuelto con latido y comprobación de proceso (1d, pruebas con reloj y con un proceso real).
