# Guía breve de Novel Engine

## Arrancar

Haz doble clic en **Iniciar Novel Engine.bat**. Se abren dos ventanas de servidor y, cuando todo está listo, el navegador en `http://localhost:3000`.
Para cerrar, usa **Detener Novel Engine.bat**.

Si el lanzador muestra un error, sigue el mensaje. Los detalles están en `docs/LANZADOR_WINDOWS.md`.

## Tus textos

- Cada novela tiene sus personajes, lugares, tramas, cronología y estructura.
- Tus manuscritos y versiones **no se modifican** por el asistente.
- Las escenas se escriben desde la propia escena; el manuscrito muestra su texto en solo lectura.

## El asistente

Abre la pestaña **Asistente** de una novela y escribe, por ejemplo:

- «crea un personaje llamado Lucía»
- «dame el estado de la novela»

Cuando el asistente propone algo, aparece en **Propuestas pendientes**, con el motivo y lo que cambiaría:

- **Aprobar y aplicar**: el cambio se guarda en la novela. Si el elemento cambió mientras tanto, la propuesta se marca como *desactualizada* y no se aplica.
- **Rechazar**: no cambia nada.

Si el asistente usa un servicio externo, verás **antes de enviar** el texto exacto y tendrás que autorizarlo.
Si la pestaña dice «simulado, sin IA», las respuestas son de prueba y no consultan ningún modelo.

## Qué no hace todavía

- No sugiere texto mientras escribes en los formularios (existe en el servidor, pendiente en la interfaz).
- No detecta contradicciones por sí solo.

## Sugerencias en los formularios

Junto a la premisa, el tema y los campos de texto de personajes, lugares, trama y cronología aparece **Sugerir para …**.
Antes de pulsar, puedes escribir una **instrucción** opcional (por ejemplo, «amplía la descripción con un detalle sensorial»
o «hazla más breve»). Si la dejas vacía, la sugerencia se genera sin instrucción. La sugerencia aparece en un cuadro que puedes editar. Puedes:

- **Aceptar en el campo**: el texto entra en el formulario, pero **no se guarda** hasta que pulses guardar.
- **Descartar**: el campo queda como estaba.

Si el asistente usa un servicio externo, verás el texto exacto que se enviará y tendrás que autorizarlo antes.

## Propuestas que no se aplican

- **Desactualizada**: el elemento cambió después de la propuesta. Por seguridad no se aplica; pide una propuesta nueva.
- **Fallida**: el motivo aparece en el historial. Si el elemento es canónico, cámbialo desde su ficha con confirmación.
