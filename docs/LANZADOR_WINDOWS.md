# Lanzador de Windows

Dos archivos en la raíz del repositorio:

- `Iniciar Novel Engine.bat`: comprueba el repositorio, actualiza solo si es seguro, verifica la base de datos y arranca backend y frontend.
- `Detener Novel Engine.bat`: cierra las ventanas de los servidores con cierre ordenado.

> **Estado de verificación:** el lanzador se ha escrito y revisado a mano, pero **no se ha ejecutado en Windows**
> desde el entorno de desarrollo donde se creó. Hasta que alguien lo pruebe en una máquina Windows, figura como pendiente.

## Qué comprueba y qué hace

1. **Herramientas**: `git`, `node`, `npm` y `curl.exe` en el PATH.
2. **Repositorio y rama**: debe ser un repositorio Git. Avisa si la rama no es `RAMA_ESPERADA` (dentro del archivo) y **nunca cambia de rama**.
3. **Cambios locales**: los cambios en archivos versionados se detectan. `apps/web/next-env.d.ts` se ignora porque Next.js lo reescribe.
4. **Actualización segura**: solo si hay remoto `origin`, la rama tiene cambios nuevos y el árbol está limpio, hace
   `git merge --ff-only`. Si hay cambios locales, divergencia o no hay red, **no actualiza** y lo dice.
   Nunca borra archivos sin seguimiento ni hace `reset` o `clean`.
5. **Dependencias**: `backend\.venv`, `apps\web\node_modules` y `apps\web\.next` deben existir. Si no, indica el comando exacto.
6. **Instancias abiertas**: si ya escucha algo en los puertos 8000 o 3000, no arranca una segunda instancia.
7. **Migraciones**: **solo lee** si la base `data\novel_engine.sqlite` está al día. Si no lo está, se detiene y no aplica nada.
8. **Procesos separados**: backend (`uvicorn` en 127.0.0.1:8000) y frontend (`npm run start`, puerto 3000), cada uno en su ventana.
9. **Espera de disponibilidad**: `/health` hasta 60 s y la página principal hasta 90 s.
10. **Navegador**: solo se abre cuando ambos responden.

## Requisitos previos

```
cd backend
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
cd ..\apps\web
npm ci
npm run build
```

Y la base migrada según `docs\MIGRACION_LOCAL.md`. El lanzador no crea ni migra la base.

## Resolución de problemas

| Mensaje | Qué hacer |
|---|---|
| «No se encuentra git/node/npm» | Instálalos y abre una consola nueva. |
| «Esta carpeta no es un repositorio Git» | Lanza el archivo desde la carpeta clonada del proyecto. |
| «Hay cambios locales sin confirmar» | Revisa `git status`. El lanzador no toca tus cambios; arranca con el código actual. |
| «han divergido» | Resuélvelo a mano (`git status`, `git log --oneline --graph`). |
| «Falta el entorno de Python» / «Faltan dependencias» / «Falta la compilación» | Ejecuta el comando indicado en el mensaje. |
| «Ya hay algo escuchando en el puerto…» | Usa `Detener Novel Engine.bat`. Si sigue, busca el proceso con `netstat -ano`. |
| «No existe la base de datos» | Crea y migra la base siguiendo `docs\MIGRACION_LOCAL.md`. |
| «no están al día con las migraciones» | Haz copia de seguridad verificada y luego `alembic upgrade head` a mano. |
| «El backend no respondió» | Lee el error en la ventana «Novel Engine backend». Causa habitual: puerto ocupado o dependencia que falta. |
| «El frontend no respondió» | Lee la ventana «Novel Engine web». Causa habitual: no se ha hecho `npm run build`. |

## Parar

Usa `Detener Novel Engine.bat`. Envía una petición de cierre a las ventanas; no fuerza el cierre de los procesos.
Si alguna ventana sigue abierta, ciérrala a mano.
