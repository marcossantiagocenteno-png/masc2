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
- **Migraciones 0001 a 0004** aplicadas y comprobadas con `alembic check`.

## Implementado, pero no verificado con servicios reales

- **Proveedor Anthropic**: el adaptador, la validación de respuestas, los errores y la autorización se prueban con dobles del SDK. **No se ha hecho ninguna llamada real**. La primera llamada requiere clave y tu autorización explícita (ver README, sección «Proveedor real»).

## Parcialmente implementado

- **Proyectos**: falta duplicar (con operación explícita y segura), vincular proyectos, preferencias por proyecto, hitos y actividad reciente completos, y el panel con pendientes.
- **Editor**: área de texto. Funciona para versiones, pero no tiene capítulos, escenas ni formato.
- **Análisis**: el simulador produce datos de longitud y tres comprobaciones mecánicas. No es un análisis literario.

## Pendiente

- Persistencia fiable: autoguardado, puntos de recuperación, indicadores de estado de guardado (fase 1b).
- Copias automáticas locales y paquete de proyecto restaurable (fases 1b y 5).
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

## Riesgos abiertos (ver AUDITORIA_TECNICA.md)

- Texto escrito sin guardar se pierde al recargar o cerrar (alta, fase 1b).
- Único archivo de base de datos sin copias automáticas (alta, fase 1b).
- Ejecución de pruebas en Linux; no verificado en Windows.
