# Respaldo y restauración

## Estado actual

**No hay copias automáticas de la base de datos.** La única vía de respaldo disponible hoy es copiar el archivo a mano. Está probada en `backend/tests/test_recovery.py`: una copia restaurada devuelve el estado anterior y conserva la inmutabilidad de las versiones.

Dentro de la aplicación hay otra protección, distinta de la copia: el **borrador** se guarda en el servidor mientras escribes, y tiene **puntos de recuperación** que puedes restaurar desde la página del manuscrito. Restaurar no borra nada: guarda antes el estado actual como punto. Los puntos no son copias de la base de datos.

Las copias automáticas de la base de datos son la siguiente tarea de la fase 1b (decisión D-044). El paquete de proyecto restaurable está previsto en la fase 5 (ver `PLAN_IMPLEMENTACION.md`).

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

Antes de aplicar una migración a una base con datos reales, **haz una copia** como se describe arriba. Las migraciones `0004` y `0005` no tienen reversión automática: para volver atrás, restaura la copia previa.

## Qué no protege una copia manual

- Borradores y puntos de recuperación escritos después de la copia. Están en la misma base de datos, así que una copia antigua no los contiene.
- Errores de hardware del disco que ocurran antes de la copia: la copia es tan segura como el medio donde se guarda.
- Un archivo copiado mientras la aplicación escribe puede no ser consistente. Por eso se pide detener el backend.
