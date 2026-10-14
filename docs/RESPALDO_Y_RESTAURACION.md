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
5. Si la copia es de una **versión de esquema anterior**, la restauración solo se hace con `--permitir-esquema-anterior`. La copia se migra a la revisión actual **en un temporal**, nunca en la base activa, y después se verifica. No tienes que ejecutar nada más.

### Qué garantiza

- Rechaza una copia que no supera la verificación, o cuyo hash no coincide con su manifiesto, **sin tocar la base activa**.
- Rechaza si la aplicación parece estar en marcha (marcador `.app-running`), o si otro proceso tiene abierta la base.
- Guarda una **copia preventiva** de la base actual (`preventiva-*.sqlite`, con manifiesto) antes de reemplazarla. Lo que estaba en la base actual no se pierde.
- Crea el temporal desde la copia y lo verifica (integridad, tablas de su revisión, recuentos y revisión actual) antes de reemplazar nada.
- Si la base restaurada no supera la verificación posterior, o no queda en la **revisión actual del código**, **vuelve automáticamente a la copia preventiva**. El resultado es `revertida`.
- Solo migra un temporal copiado de la copia de origen, y nunca la base activa. La copia de origen no se modifica.
- No borra copias ni datos.

### Copia de un esquema anterior

Una copia de una revisión anterior a la actual se rechaza salvo que añadas `--permitir-esquema-anterior`. Con ese flag:

1. La copia se verifica y se copia a un temporal junto a la base activa.
2. El temporal se migra a la revisión actual con `alembic upgrade head`. Las migraciones desde `0005` son aditivas (tablas y columnas nuevas, sin borrar datos), y así lo prueban las pruebas de migración.
3. El temporal se verifica (integridad, tablas de la revisión actual, recuentos iguales a los de la copia en sus tablas originales).
4. Solo entonces sustituye a la base activa. El resultado es `restaurada`, con la base ya en la revisión actual.

Si la migración del temporal falla, la restauración se **rechaza**: la base activa no se toca, y el mensaje indica el procedimiento manual. Si la base final no quedara en la revisión actual, se revierte a la copia preventiva.

**Procedimiento manual de recuperación** (solo con la aplicación detenida, si la restauración automática se rechaza): copia el archivo de la copia a una carpeta de trabajo; desde `backend/`, ejecuta `DATABASE_URL=sqlite:///RUTA_DE_LA_COPIA python -m alembic upgrade head`; verifica el resultado con `python -m app.backups verificar RUTA_DE_LA_COPIA` y comprueba que la revisión es la actual; y solo entonces reemplaza la base activa, guardando antes una copia de ella. No borres copias antiguas para hacerlo.

### Marcador de backend en marcha

Mientras el backend corre, existe `data/backups/.app-running` (o la carpeta de `NOVEL_ENGINE_BACKUP_DIR`). El backend renueva su **latido** cada 30 segundos y lo retira al cerrarse limpiamente. La restauración decide así:

| Estado del marcador | Qué hace la restauración |
|---|---|
| No existe | Continúa. |
| Latido reciente (menos de 3 minutos) | **Se niega.** El backend está, casi seguro, en marcha. |
| Latido caducado y el proceso del PID ya no existe | Continúa. Registra `marcador_obsoleto_detectado`. **No borra el marcador.** |
| Latido caducado y el proceso sigue existiendo | **Se niega.** |
| Latido caducado y no se puede comprobar el proceso | **Se niega.** Es el caso de Windows, ver «Límites». |
| Marcador ilegible o con formato desconocido | **Se niega.** |

Aunque el marcador diga que es seguro, la restauración **además** exige que la base activa pueda bloquearse en exclusiva. Si otro proceso la está usando, se niega igualmente. El marcador es una ayuda, no la única protección.

Si la restauración se niega por un marcador que tú sabes obsoleto (por ejemplo, tras un corte de luz), comprueba antes que no hay ningún proceso de Novel Engine (en el Administrador de tareas, o con `ps` en Linux). Solo entonces:

```bash
python -m app.backups restaurar RUTA.sqlite --confirmar --ignorar-marcador
```

No uses `--ignorar-marcador` con el backend en marcha: puede seguir escribiendo sobre una base que ya no es la activa.

El marcador **nunca se borra automáticamente** salvo en el cierre limpio del propio backend. Si quieres retirarlo a mano, bórralo solo después de confirmar que no hay procesos.

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

- **Un disco que falla a la vez que la carpeta de copias.** Conviene una copia en otro disco o en otro lugar.
- **Texto que nunca llegó al servidor.** El borrador se guarda en el servidor mientras escribes; si el backend cae antes de confirmar un guardado, el indicador del editor lo muestra y el texto sigue en pantalla, pero no está en ninguna copia.
- **Cambios posteriores a la última copia.** La frecuencia por defecto es de una hora. Ejecuta `copia` antes de operaciones delicadas.
- **Acceso no autorizado a la carpeta de copias.** Las copias **no están cifradas** (ver siguiente sección).
- **Una copia de otro equipo o de otro usuario.** No se comprueba quién la creó.

## Las copias contienen tu texto legible

**Cada copia es una base SQLite sin cifrar.** Cualquiera que pueda leer el archivo puede abrirlo con cualquier programa SQLite y leer el texto completo de todos tus manuscritos, borradores, puntos de recuperación y comentarios. Esto incluye a cualquier persona con acceso a la carpeta, a una copia en la nube o a un disco extraído.

Lo que sí puedes hacer hoy:

- **Cifrado del disco.** BitLocker (Windows Pro/Enterprise/Education), FileVault (macOS) o LUKS (Linux) protegen la carpeta de copias si el equipo se pierde o se roba. Es la protección recomendada.
- **Permisos de la carpeta.** Que solo tu usuario pueda leerla.
- **No copiar la carpeta a servicios que no controlas.** Si la sincronizas en la nube, asume que el proveedor puede leer el contenido, salvo que lo cifres antes.

Lo que **no** hay, y por qué:

- **No hay cifrado propio de las copias.** Un cifrado casero tiene dos riesgos: una implementación incorrecta que dé falsa seguridad, y una gestión de la clave que, si se pierde, deja las copias irrecuperables. Ninguna de las dos cosas es aceptable para tus manuscritos sin un procedimiento de recuperación de claves probado. La evaluación completa está en `docs/decisions.md` (D-050).

## Simulacro de restauración

Comprueba que el procedimiento funciona en tu máquina, sin tocar tus datos:

```bash
cd backend
python -m app.backups simulacro
```

Crea una base temporal, la copia, un cambio posterior, la restauración y las comprobaciones. Imprime `[OK]` o `[FALLO]` por paso y `SIMULACRO CORRECTO` o `SIMULACRO CON FALLOS`. Su carpeta queda en el sistema temporal: bórrala cuando termines. Un simulacro correcto en Windows es la única prueba real de la restauración en ese sistema.

## Crecimiento de la base

Los puntos de recuperación se crean al guardar: uno cada 5 minutos de cambios, o uno por cambio importante. **No se borran automáticamente** (los triggers lo impiden, D-048). Por eso la base crece con el uso. `python -m app.backups retencion` muestra el número de puntos, el crecimiento por día, y avisa si la base supera 200 MB o si el crecimiento estimado supera 100 MB al año. Las cifras de crecimiento son estimaciones.

Si la advertencia aparece, la limpieza todavía no se puede hacer de forma automática. Hasta que exista una fase con eliminación controlada, la opción es conservar la base.

## Límites de esta verificación

- Las pruebas automatizadas usan archivos temporales y un reloj controlado. No simulan cortes de energía ni fallos de disco reales.
- **La restauración se ha probado en Linux. No se ha probado en Windows.** En el entorno donde se desarrolló no había ningún sistema Windows disponible. Hay pruebas e instrucciones preparadas, pero ninguna se ha ejecutado allí.
- En Windows, la comprobación de si un proceso existe usa la API del sistema a través de `ctypes`, y **no se ha ejecutado allí**. Si no se puede determinar, la restauración se niega. Si la comprobación diera «no existe» para un proceso que sigue vivo, la restauración solo continuaría con el latido caducado (un backend vivo y sano renueva el latido cada 30 s), y aun así el reemplazo de un archivo que otro proceso tiene abierto falla en Windows, así que la base activa no cambia. Es un riesgo acotado, pero no verificado.
- Ver el estado en `ESTADO_DE_IMPLEMENTACION.md`.

## Procedimiento en Windows (pendiente de verificar)

Para comprobar en Windows, desde PowerShell, con el entorno del backend creado:

```powershell
cd backend
.venv\Scripts\python.exe -m app.backups simulacro
```

Si el simulacro termina con `SIMULACRO CORRECTO`, la restauración funciona en esa máquina. Si falla, copia la salida completa y el registro (`.venv\Scripts\python.exe -m app.backups registro`) antes de intentar otra cosa.
