# Privacidad y datos

## Dónde están los datos

- **Base de datos local**: `data/novel_engine.sqlite` dentro del repositorio. La carpeta `data/` está en `.gitignore`. Contiene manuscritos, versiones, comentarios y análisis.
- **Pruebas**: usan bases temporales (`pytest`) y `data/e2e.sqlite` (Playwright). Tampoco se versionan.
- **Nada se sube al repositorio** salvo código, documentación y casos ficticios de `evals/cases`.

## Qué sale del equipo

- **Por defecto, nada.** El proveedor de análisis es `simulado`, que es local.
- **Con el proveedor Anthropic** (configuración explícita), sale **únicamente el fragmento seleccionado** en cada análisis, junto con las instrucciones de análisis. No salen el título, otras versiones, comentarios ni el resto del texto.
- Cada envío exige una **autorización en esa petición**. No se guarda, no viene de variables de entorno y no se reutiliza.
- La interfaz muestra el fragmento exacto antes de enviarlo.

## Qué se guarda en los análisis

Fragmento, proveedor, modelo, si salió del equipo, hallazgos con su cita y su justificación. No se guarda la respuesta completa del proveedor ni la clave.

## Secretos

- La clave de Anthropic se lee de la configuración del backend. No aparece en `repr`, respuestas HTTP ni logs (comprobado con pruebas).
- No se escriben claves en el repositorio ni en `.env.example`.
- Las exportaciones y los paquetes de proyecto **no incluirán secretos** (diseño; la exportación aún no existe).

## Logs

El backend registra metadatos de las llamadas al proveedor: modelo, tamaño del fragmento, motivo de parada y tipo de error. No registra texto, claves ni comentarios (comprobado con pruebas).

## Lo que no está resuelto

- **Retención en Anthropic**: depende de sus condiciones y de la configuración de tu cuenta. No verificado aquí.
- **Autenticación**: no existe. Cualquiera con acceso a la red local a los puertos puede leer los datos.
- **Cifrado en reposo**: la base de datos no está cifrada.
- **Datos personales en fragmentos**: si el texto contiene datos personales, se enviarán tal cual al proveedor que autorices. El proyecto no los detecta ni los oculta.
