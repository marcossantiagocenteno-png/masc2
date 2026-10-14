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
- **Aislamiento de análisis y revisiones, y restauración segura de copias antiguas** (fase 2f). Análisis y revisiones de una versión con ruta acotada al proyecto (`/projects/{p}/manuscripts/{m}/versions/{v}/analyses|reviews`), con la misma 404 para versión inexistente o de otra novela, y la autorización externa evaluada después de la pertenencia y antes de cualquier proveedor. Las rutas heredadas no atienden manuscritos de proyecto (lectura 404, escritura 422). La restauración de una copia anterior a 0009 migra solo un temporal, verifica tablas, conteos y revisión actual, y sustituye la base activa solo entonces; si la migración falla, rechaza sin tocar la base. Pruebas: 9 de análisis y revisiones en `test_aislamiento_analisis.py`, 4 de restauración de esquema anterior y revertida en `test_restauracion.py`, y 1 E2E del análisis acotado. Sin migración de esquema.
- **Integridad y aislamiento de manuscritos** (fase 2e). Rutas acotadas por proyecto para manuscritos, versiones, borradores y puntos de recuperación, con la misma 404 para ids inexistentes o de otra novela, y escrituras solo en proyectos activos. La interfaz usa esas rutas cuando el manuscrito tiene proyecto. Las escrituras heredadas sobre texto de escena se rechazan. Título: la escena es la única fuente de verdad; ninguna interfaz edita el título de un manuscrito de escena, y la página lo indica. Pruebas: 20 de aislamiento en `test_aislamiento_manuscritos.py` (negativas con ids válidos de otro proyecto sin cambios en datos, título, integridad, conflicto y restauración por ruta acotada), y las pruebas de escritura de escena actualizadas al contrato nuevo. Sin migración de esquema.
- **Escritura de escenas** (fase 2d). Cada escena puede empezar a escribirse con una acción explícita: crea su manuscrito propio (sin texto, con versión 1 vacía y borrador) y lo une a la escena por `scene_manuscripts` (migración 0009). El texto se guarda con el mismo motor de borrador que el manuscrito, con conflictos detectados y sin pérdida. Mover o renombrar la escena conserva el texto; renombrar actualiza el título del manuscrito. Los manuscritos de escena no aparecen en la lista del proyecto. Pruebas: 18 de backend en `test_escritura_escenas.py` (vinculación, persistencia, mover y renombrar, aislamiento, inmutabilidad de la unión, archivados, inicio concurrente, guardado concurrente, versiones y recuperación intactas, migración 0009 con datos) y 8 E2E en `tests/e2e/escritura.spec.ts`. Migración comprobada en base nueva, en copia de la base de desarrollo en 0008 y en una base con datos.
- **Reorganización y navegación de la estructura** (fase 2c). Mover actos, capítulos y escenas a un padre compatible (o a la raíz), con validaciones de tipo, ciclos, archivados y proyecto; ramas plegables; alta desde cada fila; movimiento y reordenación con confirmación previa cuando afectan a elementos canónicos; errores del servidor que conservan la vista. Navegación en ambos sentidos entre escenas y personajes, lugares y elementos de trama, sin crear vínculos. Control de revisión de la estructura (migración 0008, `structure_version`), que impide que una vista desfasada pise una operación ya confirmada. Pruebas: movimientos válidos e inválidos, aislamiento, identidad y vínculos, canon, atomicidad, concurrencia y vistas desactualizadas en backend; recorridos E2E de movimiento, confirmación, rechazo, vista desactualizada, ramas, navegación y pantalla de 360 px. Migración comprobada en base nueva, en copia de la base de desarrollo con el esquema anterior y en una base con datos.
- **Interfaz de planificación** (fase 2b). En el espacio de trabajo de cada novela: visión general (premisa, sinopsis, género, tema, tono, estado de desarrollo, con la advertencia de que no tienen protección de canon); personajes, lugares, trama y misterios, y cronología, con creación desde un nombre, edición, archivado con confirmación, aprobación como canon con casilla de confirmación, historial de decisiones de solo lectura; estructura de actos, capítulos y escenas con alta, edición y reordenación entre hermanos (botones), y una pantalla por escena con sus vínculos (personajes, lugares y elementos de trama), creados y retirados con las operaciones de la API. Pruebas: 8 E2E en `tests/e2e/planificacion.spec.ts` (recorridos principales, identidad al reordenar, canon, errores sin pérdida de texto, aislamiento entre novelas, avisos de cambios sin guardar). Sin IA y sin llamadas externas.
- **Corrección de CORS**: el backend no permitía `PATCH`, así que el navegador bloqueaba la edición del nombre del proyecto y de los elementos de planificación. Corregido y probado con una prueba de preflight.
- **Auditoría de integridad de la planificación** (fase 2a.1): vínculos validados también en la base (triggers, migración 0007); decisiones de canon con actor y estado resultante; cambios atómicos (un fallo al confirmar ya no deja cambios pendientes en la sesión); la carrera de duplicados responde 409 y no 500. Pruebas: 18 de integridad y 2 de migración 0007. Cuatro mutaciones de estas garantías se detectan.
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

## Riesgos abiertos de la planificación (verificados al cierre de la fase 2a.1)

- **Datos generales de la novela sin canon.** Premisa, sinopsis, género, tema y tono cambian sin confirmación y sin historial (D-059). La interfaz debe indicarlo. **Abierto.**
- **Historial solo de canon.** Editar un elemento provisional o una propuesta no deja registro. **Deliberado; abierto como limitación.**
- **Actor «ia» sin ruta.** El servicio rechaza al actor IA en las operaciones de canon, probado en servicio. No hay ningún endpoint de IA, así que esta regla no se ejerce todavía desde la API. **Abierto.**
- **Archivar un elemento no archiva sus vínculos.** Un vínculo sigue visible con su extremo archivado; ningún vínculo nuevo puede apuntar a él (decisión documentada). **Deliberado.**
- **Posiciones de estructura no únicas en la base.** Dos creaciones concurrentes de hermanos pueden darse la misma posición. El orden sigue siendo determinista (posición, luego id), y un reordenado lo corrige. **Abierto, de baja gravedad.**
- **Vocabulario de relaciones solo en código.** La base valida tipos y extremos; el par relación-tipos lo valida el servicio. **Deliberado (D-057).**
- **Decisiones anteriores a 0007 sin resultado.** Se atribuyen al autor y no tienen estado resultante. **Limitación de la migración.**
- **Fallo de disparador en carrera.** Un disparador que rechaza un vínculo durante una carrera responde 422, no 500. **Probado en servicio.**
- **Archivo `/m.sqlite` en la raíz del sistema.** Lo creó un comando defectuoso de la fase 2a (una variable de shell vacía dejó la ruta en la raíz). Su contenido es solo la tabla `alembic_version` vacía; no es la base del repositorio. **Pendiente de retirada por una persona.**

## Limitaciones de la interfaz de planificación (fase 2b y 2c)

- **Movimiento sin posición intermedia.** Un nodo movido va al final de los hermanos del destino; su orden se cambia después con Subir y Bajar. No hay arrastre.
- **Vista desactualizada sin aviso previo.** La estructura no se compara con el servidor al mostrarla. Un cambio hecho en otra pestaña se detecta al operar (el servidor rechaza sin cambiar nada) y la interfaz ofrece actualizar.
- **Vista previa de canon en el cliente.** La interfaz calcula los nodos afectados igual que el servidor, pero es una previsión: el servidor decide con sus datos, y una operación que cambie de forma inesperada se rechaza.
- **Accesibilidad y móvil con comprobación limitada.** Se revisan nombres, foco y desbordamiento en los flujos cubiertos por E2E, y la pantalla de 360 px sin desbordamiento horizontal en estructura, ficha y personajes. No se ha probado con un lector de pantalla ni con un dispositivo real.
- **Sin historial navegable ni restauración.** Cada elemento muestra sus decisiones de canon en solo lectura. No hay forma de restaurar un estado anterior.
- **Campos generales de la novela sin canon.** La interfaz lo indica, pero no hay protección ni historial para ellos (D-059).
- **Sin propuestas de IA.** La interfaz muestra y gestiona el estado «propuesta de IA» y permite aceptarla, pero no se generan propuestas.
- **Accesibilidad y móvil sin auditoría.** Las pruebas E2E se ejecutan en escritorio. La distribución en pantallas pequeñas está prevista pero no se ha comprobado con un dispositivo real.
- **Edición de elementos provisionales sin historial.** Solo las decisiones de canon se registran.

Límites de aislamiento: las rutas heredadas por id de versión y de manuscrito siguen existiendo solo para manuscritos sin proyecto; el metadato `GET /manuscripts/{id}` sigue abierto para descubrir el proyecto. La restauración de una copia anterior a 0009 ya no deja la base incompatible: se migra en un temporal, pero la migración automática depende de que las migraciones sigan siendo aditivas, y si falla hay que seguir el procedimiento manual de `docs/RESPALDO_Y_RESTAURACION.md`.

## Pendiente de la planificación

- Historial y restauración de decisiones desde la interfaz. El registro existe; la vista no.
- Restaurar elementos archivados (la operación inversa de archivar).
- Estado de canon para los campos narrativos del proyecto (premisa, sinopsis). Hoy son datos del autor sin estado.
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
