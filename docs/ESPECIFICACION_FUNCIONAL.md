# Especificación funcional: resumen y estado

La especificación completa de Novel Engine se mantiene en el mensaje de encargo. Este documento resume sus módulos y muestra el estado de cada uno, para que el repositorio no declare nada que no exista.

| Módulo | Requisito principal | Estado |
|---|---|---|
| 1. Biblioteca de novelas | Crear, abrir, renombrar, archivar, restaurar, duplicar proyectos aislados | Parcial: crear, renombrar, archivar, restaurar y listar. Falta duplicar, buscar y vincular. |
| 2. Panel de control | Dónde se quedó, pendientes, observaciones, acciones rápidas | Parcial: estado, recuento y último manuscrito. Faltan pendientes, observaciones y actividad. |
| 3. Planificación narrativa | Elementos opcionales, estados de información, decisiones | Parcial (fase 2a): núcleo de datos y API con canon, relaciones, estructura y decisiones. Sin interfaz, sin IA, sin análisis de contradicciones. |
| 4. Manuscrito y editor | Capítulos y escenas, guardado automático, puntos de recuperación | Parcial: versiones inmutables, borrador con autoguardado y puntos de recuperación. No hay capítulos. |
| 5. Memoria narrativa | Hechos con fuentes, contradicciones, distinción de niveles de certeza | No implementado |
| 6. Centro editorial | Tareas con estados, dependencias, historial | No implementado |
| 7. Tareas y decisiones | Decisiones con alternativas y escenarios separados del canon | No implementado |
| 8. Métodos narrativos | Biblioteca ampliable con jerarquía de criterios | No implementado |
| 9. Importación | DOCX, TXT, Markdown con procedencia y resumen verificable | No implementado |
| 10. Historial y recuperación | Comparar y restaurar sin borrar estados posteriores | Parcial: las versiones se conservan; no hay interfaz de comparación ni restauración |
| 11. Copias y paquetes | Copias automáticas y paquete trasladable validado | No implementado. Copia manual del archivo documentada. |
| 12. Exportación | DOCX, PDF, TXT, EPUB con orden correcto | No implementado |
| 13. Preferencias literarias | Generales y por proyecto | No implementado |
| 14. Privacidad y autorización de IA | Autorización por operación, vista del envío exacto | Parcial: autorización por petición y vista del fragmento. Falta la vista de contexto completo. |
| 15. Proveedores de IA | Interfaz común y estados de proveedor | Parcial: un proveedor (Anthropic), probado con dobles. Estado del proveedor visible. |
| 16. Propuestas de escritura | Separadas del manuscrito, aceptables por partes | No implementado |
| 17. Errores de IA | Reintentos limitados y causas distinguidas | Parcial: un intento sin reintentos (diseño deliberado para no duplicar costes) |

## Principios que se respetan hoy

- El manuscrito no se sobrescribe con texto generado por IA: no existe esa operación.
- No se envía contenido a servicios externos sin autorización por petición.
- Los datos de un proyecto no se mezclan con los de otro (probado).
- Las versiones son inmutables.

## Principios pendientes de implementar

- Preferencias y perfiles por proyecto que no se heredan automáticamente.
- Distinción entre hecho, interpretación, hipótesis y propuesta en la memoria narrativa.
- Historial que distinga cambios del autor y cambios de la IA.
