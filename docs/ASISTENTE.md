# Asistente de la novela

El asistente es un chat por novela. Puede responder preguntas sobre la novela y **preparar propuestas** de cambio.
Ninguna propuesta modifica la novela hasta que la persona autora la aprueba.

## Qué ve el asistente

El contexto que se envía al proveedor se construye en `backend/app/assistant/contexto.py`:

- Nombre, premisa, tema y directrices narrativas del proyecto.
- Géneros activos y decisiones de canon confirmadas (las más recientes).
- Personajes, lugares, elementos de trama, acontecimientos y estructura **no archivados** de esa novela.
- Memoria narrativa del proyecto.

**No se envían manuscritos ni texto de escenas.** El límite de tamaño lo fija `NOVEL_ENGINE_ASSISTANT_MAX_CONTEXT_CHARS`
(por defecto 15 000 caracteres); si se supera, el contexto se recorta y el texto lo indica.

## Arquitectura

| Pieza | Archivo | Responsabilidad |
|---|---|---|
| Contexto | `app/assistant/contexto.py` | Lee la novela en solo lectura, filtrando siempre por proyecto. Calcula huellas. |
| Proveedores | `app/assistant/providers.py` | Contrato `AssistantProvider`, proveedor simulado y adaptador Anthropic. Compone el contenido exacto que se envía. |
| Servicio | `app/assistant/service.py` | Conversación, envío idempotente, validación de propuestas, aprobación, rechazo y autocompletado. |
| Rutas | `app/assistant/routes.py` | API bajo `/projects/{id}/asistente`. |
| Modelos | `app/db/models.py` | `AssistantConversation`, `AssistantMessage`, `AssistantProposal`, `AssistantMemoryItem`. |
| Migración | `migrations/versions/0012_asistente.py` | Crea las cuatro tablas. No tiene `downgrade`. |
| Interfaz | `apps/web/components/asistente/AsistenteChat.tsx` | Chat, autorización de envío, propuestas y memoria. |

## Proveedores

Se elige por configuración, nunca desde el navegador.

| Variable | Valor por defecto | Efecto |
|---|---|---|
| `NOVEL_ENGINE_ASSISTANT_PROVIDER` | `simulado` | `simulado` (sin IA) o `anthropic` (externo). Cualquier otro valor es un error 503. |
| `ANTHROPIC_API_KEY` | — | Clave de Anthropic. Solo en el entorno del backend. No se registra ni se devuelve. |
| `NOVEL_ENGINE_ANTHROPIC_MODEL` | — | Modelo a usar. Obligatorio con `anthropic`. Compartido con el análisis de textos. |
| `NOVEL_ENGINE_ANTHROPIC_TIMEOUT_SECONDS` | 60 | Tiempo máximo por llamada. |
| `NOVEL_ENGINE_ANTHROPIC_MAX_OUTPUT_TOKENS` | 2000 | Límite de tokens de salida. |
| `NOVEL_ENGINE_ASSISTANT_MAX_CONTEXT_CHARS` | 15000 | Tamaño máximo del contexto enviado. |

- **Simulado** (por defecto): respuestas deterministas y marcadas como «simulado, sin IA». No hay red ni claves.
- **Anthropic**: una sola llamada por petición, sin reintentos automáticos (`max_retries=0`), herramienta forzada
  `registrar_respuesta` y validación estricta de la respuesta. Si falta la clave o el modelo, el asistente responde 503
  y **no envía nada**. No hay respaldo silencioso a otro proveedor.

## Autorización de envío a proveedores externos

Con un proveedor externo, cada envío sigue tres pasos:

1. `POST /asistente/vista-previa` devuelve el **contenido exacto** y su huella SHA-256.
2. La interfaz lo muestra y la persona autora lo autoriza.
3. `POST /asistente/mensajes` lleva `autorizacion_hash`. Si falta, responde **403**. Si la novela o la conversación han
   cambiado desde la vista previa, responde **409** y no envía nada.

La vista previa y el envío usan la misma función (`componer_envio`), así la huella coincide con lo que sale.

## Mensajes

- `client_id` lo genera el navegador. Reenviar el mismo `client_id` devuelve lo ya guardado y **no** vuelve a llamar al proveedor.
- Si el proveedor falla o devuelve algo mal formado, el mensaje del usuario se conserva, se añade un mensaje de sistema
  con el aviso, y no se crea ninguna propuesta.
- Las propuestas que no cumplen las reglas se descartan y se anota cuántas.

## Ciclo de vida de una propuesta

Estados: `pendiente`, `aplicada`, `rechazada`, `fallida`, `desactualizada`.

- **Crear** un personaje, lugar, elemento de trama o acontecimiento, o **actualizar** uno existente (solo campos de texto).
  La premisa solo puede actualizarse. Nunca se pueden cambiar identificadores, estados ni origen.
- **Aprobar**: reclama la propuesta con una actualización condicional (`estado = 'pendiente'`), revalida la huella del
  elemento y aplica los cambios en la misma transacción. Si algo falla, todo se deshace y la propuesta queda `fallida`.
  Si el elemento cambió desde que se propuso, queda `desactualizada` y no se toca nada.
  Un elemento **canónico** no se cambia desde una propuesta: queda `fallida` con el motivo.
  Aprobar dos veces devuelve la misma propuesta sin duplicar nada.
- **Rechazar**: solo cambia el estado y la memoria. No toca datos de la novela.
- Una propuesta de otra novela responde 404. Un proyecto archivado no admite envíos ni aprobaciones.

## Memoria narrativa

Tabla separada del historial. Cada propuesta tiene una entrada con su tipo:
`propuesta` (pendiente), `confirmado` (aplicada), `rechazada`, `pendiente` (desactualizada o fallida).
Los tipos `idea` y `contradiccion` están previstos en el modelo, pero **nada los genera todavía**.

## Autocompletado

Endpoints `POST /asistente/autocompletar` y `POST /asistente/autocompletar/vista-previa`, con la misma autorización que el chat.
Solo sugieren texto para campos de la lista permitida (`CAMPOS_TEXTO`); no guardan nada. Ver «Limitaciones».

## Limitaciones conocidas

- **No se ha probado con la API real de Anthropic.** Las pruebas usan un cliente falso. Falta comprobar la clave, el modelo y la latencia en un entorno con acceso.
- **El autocompletado todavía no está en los formularios de la interfaz.** Existe el endpoint, pero el campo de premisa y las fichas no ofrecen aún la sugerencia con aceptar, editar o descartar.
- **Las dependencias entre propuestas** se guardan como lista vacía; aún no se validan ni se ordenan.
- **Una sola conversación por novela.** El historial completo se devuelve sin paginar.
- **Sin detección automática de contradicciones.**
- La migración `0012` no tiene `downgrade`: para deshacerla hay que restaurar una copia de seguridad verificada (`RESPALDO_Y_RESTAURACION.md`).
