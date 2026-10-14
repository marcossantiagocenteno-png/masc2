# Plan de implementación de Novel Engine

Basado en la auditoría (`AUDITORIA_TECNICA.md`). La especificación permite reordenar fases si la auditoría lo justifica. Aquí lo hace.

## Cambio de prioridad y motivo

La especificación pone la planificación en la fase 2 y la persistencia fiable en la fase 3. La auditoría muestra que **el autor puede perder texto hoy**: el editor no guarda hasta pulsar un botón. Por eso la persistencia (autoguardado, puntos de recuperación y copias) pasa **antes** de la planificación. Construir personajes y escenas sobre un editor que puede perder texto aumentaría el daño de cualquier fallo.

## Fases

| Fase | Contenido | Estado |
|---|---|---|
| 0. Auditoría y especificación | Revisión del repositorio, auditoría, plan, pruebas de referencia | **Completada** |
| 1. Fundamentos | Proyectos aislados, navegación, panel, migraciones seguras, manejo de errores | **Parcial**: proyectos y migraciones hechos. Faltan preferencias por proyecto, duplicar, hitos y actividad reciente completos. |
| 1b. Persistencia fiable (nueva, adelantada) | Autoguardado, puntos de recuperación, estados de guardado, copias automáticas locales | **Parcial**: autoguardado, estados, conflictos, puntos y restauración hechos y probados. **Copias automáticas pendientes, siguiente tarea inmediata.** |
| 2. Planificación y estructura | Premisa, personajes, relaciones, cronología, capítulos y escenas, esquema jerárquico, tablero, estados de información, decisiones | Pendiente |
| 3. Manuscrito | Editor con capítulos y escenas flexibles, historial comparable, restauración sin pérdida de versiones posteriores, vínculos con la planificación | Pendiente |
| 4. Memoria y tareas básicas | Hechos con fuentes, relaciones, tareas con estados, detección básica de inconsistencias | Pendiente |
| 5. Importación, exportación y protección | DOCX/TXT/Markdown, exportación del manuscrito, paquete completo restaurable | Pendiente |
| 6. Proveedor real y propuestas de IA | Anthropic sobre la arquitectura común, propuestas separadas del manuscrito, reintentos limitados | Parcial: proveedor y autorización hechos; **sin verificación real**; sin propuestas integradas en el editor |
| 7. Inteligencia editorial avanzada | Supervisión continua, análisis de impacto, correcciones coordinadas, métodos narrativos, evaluación por capas | Pendiente |

## Fase 1b: persistencia fiable

Estado: los puntos 1 a 4 están hechos y probados (ver `decisions.md`, D-041 a D-043). El punto 5 queda pendiente (D-044). Garantías previstas:

1. **Autoguardado** del texto del editor, con un intervalo o al detenerse la escritura. Debe crear un estado **recuperable**, no una versión inmutable por cada pulsación. Diseño propuesto: un «borrador» por capítulo o manuscrito, separado de las versiones inmutables, que se consolida en una versión solo cuando el autor lo decide o al cerrar.
2. **Indicador de estado de guardado** fiable: «cambios pendientes», «guardado», «error de guardado». No depende solo del estado visual: el borrador está en el servidor.
3. **Recuperación ante recarga, fallo de conexión y cierre**: pruebas E2E que simulen cada caso.
4. **Puntos de recuperación periódicos**: copia del borrador en el servidor con marca temporal y política de conservación documentada.
5. **Copias automáticas locales** del archivo de base de datos, con retención limitada y restauración documentada.

Decisión tomada: el borrador vive en una tabla nueva, no en `manuscript_versions` (D-041). Reutilizar las versiones con un estado «borrador» rompería su inmutabilidad.

## Criterios de avance

Una fase solo se da por completada si funciona de extremo a extremo y sus pruebas pasan. Las pruebas unitarias no bastan para declarar una integración real.

## Lo que no se hará sin decisión tuya

- Conectar un proveedor de IA con datos reales (requiere clave y autorización).
- Desplegar en internet (requiere autenticación, que no existe).
- Cambiar la inmutabilidad de las versiones.
- Migraciones destructivas o reversiones automáticas de 0004.
