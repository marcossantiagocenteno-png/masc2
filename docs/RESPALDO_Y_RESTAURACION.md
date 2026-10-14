# Respaldo y restauración

## Estado actual

**No hay copias automáticas.** La única vía de respaldo disponible hoy es copiar el archivo de la base de datos a mano. Está probada en `backend/tests/test_recovery.py`: una copia restaurada devuelve el estado anterior y conserva la inmutabilidad de las versiones.

Las copias automáticas y el paquete de proyecto restaurable están previstos en la fase 1b y en la fase 5 (ver `PLAN_IMPLEMENTACION.md`).

## Cómo hacer una copia manual

1. Detén el backend (Ctrl+C en la terminal donde corre `uvicorn`). **No copies el archivo mientras la aplicación está en marcha.**
2. Copia `data\novel_engine.sqlite` (en Windows, dentro de la carpeta del repositorio) a otra carpeta, con la fecha en el nombre. Por ejemplo, `novel_engine_2026-10-14.sqlite`.
3. Vuelve a arrancar el backend.

## Cómo restaurar una copia manual

1. Detén el backend.
2. Renombra el archivo actual (no lo borres): por ejemplo, `novel_engine.sqlite.roto`.
3. Copia la copia de seguridad como `data\novel_engine.sqlite`.
4. Arranca el backend. Los proyectos, manuscritos y versiones vuelven al estado de la copia.

Conserva siempre el archivo que sustituyes, por si la copia era anterior a algo que querías.

## Migraciones y copias

Antes de aplicar una migración a una base con datos reales, **haz una copia** como se describe arriba. La migración `0004` no tiene reversión automática: para volver atrás, restaura la copia previa.

## Qué no protege una copia manual

- Cambios hechos en el editor sin pulsar «Guardar como nueva versión» (el autoguardado no existe todavía).
- Errores de hardware del disco que ocurran antes de la copia: la copia es tan segura como el medio donde se guarda.
- Un archivo copiado mientras la aplicación escribe puede no ser consistente. Por eso se pide detener el backend.
