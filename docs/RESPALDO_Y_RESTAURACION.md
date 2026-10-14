# Respaldo y restauración

Estado: copias automáticas verificadas, rotación y restauración administrativa (fase 1c). Probado en Linux con pruebas automatizadas. **No probado en Windows** en condiciones reales (ver «Límites»).

## Qué se respalda

Toda la base de datos (`data/novel_engine.sqlite` por defecto): proyectos, manuscritos, versiones formales, comentarios, análisis, **borradores** y **puntos de recuperación**. Una copia es un archivo SQLite completo, sin cifrar.

Cada copia tiene dos archivos en la carpeta de copias:

- `novel_engine-AAAAMMDDTHHMMSSmmmmmmZ.sqlite`: la base copiada.
- `novel_engine-AAAAMMDDTHHMMSSmmmmmmZ.json`: manifiesto con el hash SHA-256, la versión de esquema, los recuentos por tabla y la fecha. No contiene texto ni claves.

Además existe `operaciones.jsonl`, el registro operativo: una línea por evento (inicio, correcta, fallida, omitida, rotada, restauración). Tampoco contiene texto de manuscritos.

## Dónde se guardan

- **Carpeta por defecto:** `data/backups/` dentro del repositorio. Está en `.gitignore` (`/data/`).
- **Otra carpeta:** variable `NOVEL_ENGINE_BACKUP_DIR`. Recomendado: un disco o una carpeta distinta de la base, porque una copia en el mismo disco no protege de un fallo de disco.
- Las copias **no se suben a ningún sitio**. Si copias la carpeta a un almacenamiento externo, ese almacenamiento contiene todo tu texto: protégelo como lo protegerías a él.

## Frecuencia, rotación y valores por defecto

| Variable | Por defecto | Significado |
|---|---|---|
| `NOVEL_ENGINE_BACKUP_INTERVAL_MINUTES` | 60 | Frecuencia mientras corre el backend. Con 0 no hay copias automáticas. Se intenta una copia al arrancar. |
| `NOVEL_ENGINE_BACKUP_KEEP` | 14 | Número máximo de copias conservadas. |
| `NOVEL_ENGINE_BACKUP_MIN_KEEP` | 3 | Copias que nunca se borran por antigüedad. |
| `NOVEL_ENGINE_BACKUP_MAX_AGE_DAYS` | 30 | Antigüedad a partir de la cual se borra una copia, si quedan más de `MIN_KEEP`. |
| `NOVEL_ENGINE_BACKUP_DIR` | `data/backups` | Carpeta de copias. |

Reglas de rotación:

1. Una copia nueva se crea, se verifica y se nombra **antes** de rotar. Si la copia falla, no se borra ninguna anterior.
2. Se borra una copia si está fuera de las `KEEP` más recientes, o si tiene más de `MAX_AGE_DAYS` y quedan más de `MIN_KEEP`.
3. Las copias preventivas (ver «Restaurar») no las borra la rotación. Las borras tú, a mano, cuando estés seguro.

Una copia fallida se registra como `fallida` con su motivo. Nunca se informa como éxito. El planificador reintenta tras el intervalo, no en bucle.

## Cómo se crea y se verifica una copia

1. Se abre una lectura de la base. Todo el contenido de la copia corresponde a una única instantánea. Las escrituras que llegan durante la copia esperan a que termine; para bases de decenas de MB dura milisegundos.
2. Se copia con la API de backup de SQLite a un archivo temporal `.tmp-*`.
3. El temporal se verifica: se puede abrir en solo lectura, `PRAGMA integrity_check` devuelve `ok`, existen todas las tablas y la versión de esquema es conocida por el código.
4. Solo si supera la verificación, se renombra a su nombre definitivo y se escribe su manifiesto. Después se verifica el archivo final.
5. Solo entonces se rota.

Verificar una copia cualquiera, en cualquier momento, sin modificarla:

```bash
cd backend
python -m app.backups verificar ../data/backups/novel_engine-AAAAMMDD....sqlite
```

Salida esperada: `Válida. Revisión ...`. Si no, `No válida:` con el motivo, y código de salida 1.

## Comandos

Ejecútalos desde `backend/`, con el entorno virtual activo.

| Acción | Linux / macOS | Windows (PowerShell) |
|---|---|---|
| Crear una copia ahora | `python -m app.backups copia` | `.venv\Scripts\python.exe -m app.backups copia` |
| Listar copias | `python -m app.backups listar` | `.venv\Scripts\python.exe -m app.backups listar` |
| Verificar una copia | `python -m app.backups verificar RUTA` | `.venv\Scripts\python.exe -m app.backups verificar RUTA` |
| Ver el registro | `python -m app.backups registro --lineas 30` | `.venv\Scripts\python.exe -m app.backups registro --lineas 30` |
| Métricas de retención (no borra) | `python -m app.backups retencion` | `.venv\Scripts\python.exe -m app.backups retencion` |
| Restaurar | ver abajo | ver abajo |

Códigos de salida: `0` correcto, `1` fallo o rechazo, `2` falta `--confirmar`, `3` omitido porque otra operación estaba en curso.

## Cómo restaurar

La restauración **no se hace desde la interfaz**. Es un procedimiento administrativo, porque reemplaza la base con la aplicación detenida.

### Pasos

1. **Detén el backend** (Ctrl+C en la terminal donde corre `uvicorn`). Si la aplicación se cerró de golpe, sigue al paso 2.
2. **Elige la copia.** Lista las copias (`listar`) y verifícala (`verificar`). Anota la ruta del archivo `.sqlite`, no del `.json`.
3. **Restaura** con confirmación explícita:

   Linux / macOS:
   ```bash
   cd backend
   python -m app.backups restaurar ../data/backups/novel_engine-AAAAMMDD....sqlite --confirmar
   ```

   Windows (PowerShell):
   ```powershell
   cd backend
   .venv\Scripts\python.exe -m app.backups restaurar ..\data\backups\novel_engine-AAAAMMDD....sqlite --confirmar
   ```

4. **Comprueba el resultado.** La salida indica la copia preventiva creada. Arranca el backend y verifica que tus manuscritos, borradores y puntos de recuperación están presentes.
5. Si la copia es de una **versión de esquema anterior** (la salida lo dirá), ejecuta después `python -m alembic upgrade head` desde `backend/`. La restauración **nunca migra** automáticamente.

### Qué garantiza

- Rechaza una copia que no supera la verificación, o cuyo hash no coincide con su manifiesto, **sin tocar la base activa**.
- Rechaza si la aplicación parece estar en marcha (marcador `.app-running`), o si otro proceso tiene abierta la base.
- Guarda una **copia preventiva** de la base actual (`preventiva-*.sqlite`, con manifiesto) antes de reemplazarla. Lo que estaba en la base actual no se pierde.
- Crea el temporal desde la copia y lo verifica (integridad y recuentos) antes de reemplazar nada.
- Si la base restaurada no supera la verificación posterior, **vuelve automáticamente a la copia preventiva**. El resultado es `revertida`.
- No ejecuta migraciones, no borra copias ni datos.

### Copia de un esquema anterior

Una copia de una revisión anterior a la actual se rechaza salvo que añadas `--permitir-esquema-anterior`. Con ese flag se restaura y, después, debes ejecutar `python -m alembic upgrade head`. Las migraciones de esta aplicación son aditivas, pero esa decisión la tomas tú, después de leer el registro. No hay una bajada automática (`0004` y `0005` no se revierten solas: restaura la copia anterior).

### Marcador de backend en marcha

Mientras el backend corre, existe `data/backups/.app-running`. La restauración se niega mientras exista. Si el backend se cerró de golpe y el marcador quedó, **comprueba que no hay ningún proceso de Novel Engine** y entonces usa `--ignorar-marcador`. Usarlo con el backend en marcha puede dejar al backend escribiendo sobre una base que ya no es la activa.

## Restauración manual (sin la herramienta)

Si la herramienta no está disponible, el procedimiento de copia de archivo sigue siendo válido con **la aplicación detenida**:

1. Copia `novel_engine-*.sqlite` a `data/novel_engine.sqlite` después de renombrar la base actual (no la borres).
2. Verifícala con `python -m app.backups verificar ...`.

Es menos seguro: no hay copia preventiva automática, ni verificación previa al reemplazo.

## Puntos de recuperación

Los puntos del borrador son otra protección, **distinta de las copias**. Están en la base, así que las copias de la base también los contienen. Su política de retención se describe en `decisions.md` (D-048):

- Hoy **no se borra ningún punto**. Los triggers de inmutabilidad lo impiden, y su eliminación exige una decisión y una migración propias.
- `retencion` muestra métricas de crecimiento y qué puntos serían candidatos en el futuro. Candidato significa: periódico o significativo, más antiguo que 90 días, fuera de los 20 más recientes de su manuscrito, y con una copia verificada que lo contiene. Los de conflicto, antes de sobrescribir y antes de restaurar **nunca** son candidatos.

## Qué no protege

- **Un disco que falla a la vez que la carpeta de copias.** Por eso conviene una copia en otro disco o en otro lugar.
- **Texto que nunca llegó al servidor.** El borrador se guarda en el servidor mientras escribes; si el backend cae antes de que se confirme un guardado, el indicador del editor lo muestra y el texto sigue en pantalla, pero no está en ninguna copia.
- **Cambios posteriores a la última copia.** La frecuencia por defecto es de una hora. Ejecuta `copia` antes de operaciones delicadas.
- **Acceso no autorizado a la carpeta de copias.** No hay cifrado.
- **Una copia de otro equipo o de otro usuario.** No se comprueba quién la creó.

## Límites de esta verificación

- Las pruebas automatizadas usan archivos temporales y un reloj controlado. No simulan cortes de energía ni fallos de disco reales.
- La restauración se ha probado en Linux. **Windows no se ha probado en condiciones reales**: el reemplazo de archivos y el bloqueo exclusivo se comportan distinto allí, y el procedimiento de Windows es el mismo pero no está verificado.
- Ver el estado en `ESTADO_DE_IMPLEMENTACION.md`.
