# Entornos: qué base de datos usa cada uno

Estado: verificado leyendo el código (`backend/app/config.py`, `apps/web/playwright.config.ts`, `apps/web/lib/api.ts`)
el 15 de octubre. Este documento describe la configuración, no el contenido de tu máquina.

## Tabla

| Entorno | Backend | Base de datos | Frontend | URL de la API que usa el frontend |
|---|---|---|---|---|
| Uso normal (tu app) | `uvicorn app.main:app` en `backend/`, puerto 8000 por defecto | `data/novel_engine.sqlite` (por defecto) | `next dev` en `apps/web/`, puerto 3000 | `http://localhost:8000` (por defecto) |
| Pruebas E2E | Lo arranca Playwright en `127.0.0.1:8100` | `data/e2e.sqlite` (fijada en la configuración de Playwright) | Lo arranca Playwright en `localhost:3100` | `http://127.0.0.1:8100` (fijada) |

## Puntos que conviene conocer

- **Las pruebas E2E no usan tu base de uso normal.** Su base es `data/e2e.sqlite`. Cada ejecución añade datos y nadie los borra.
- **Playwright reutiliza un servidor que ya esté en marcha** en el mismo puerto, salvo en CI (`reuseExistingServer`). Si
  tienes un backend en 8100 con otra base, las pruebas usarán ese backend. Antes de ejecutar pruebas, comprueba qué hay
  en ese puerto.
- **El backend no migra la base al arrancar.** Hay que ejecutar `python -m alembic upgrade head` desde `backend/`.
  Una base atrasada hace que las rutas nuevas fallen; `/health` informa de ello en `esquema.al_dia`.
- **`NEXT_PUBLIC_API_BASE_URL` se incorpora al frontend al arrancar.** Si lo cambias, reinicia `next dev`. En producción
  hay que reconstruir.
- **La base de uso normal y la de pruebas están en `data/`, que está en `.gitignore`.** Nada de ahí se sube al repositorio.

## Cómo verificar tu entorno

1. Con el backend en marcha, abre `http://localhost:8000/health`. Debe mostrar `"al_dia": true` en `esquema`.
2. Para saber qué archivo usa el backend: el valor de `DATABASE_URL` si está definido; si no, `data/novel_engine.sqlite`.
3. Para saber qué base contiene tus novelas, lista proyectos con la API (`GET /projects`) antes de tocar nada.
