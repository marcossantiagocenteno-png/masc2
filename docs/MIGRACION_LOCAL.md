# Migrar tu base local

Esta migración no se ejecuta sola ni la ejecuta ninguna prueba. Es un procedimiento que haces tú, con copia previa.

**Qué hace:** añade las tablas de géneros y directrices (`0010`) y de recomendaciones de estructura (`0011`). No borra
ni modifica filas existentes. Ambas son aditivas.

**Cuándo hace falta:** si `GET /health` indica `"al_dia": false`, o si la visión general muestra «No se pudo conectar»
en la premisa, los géneros o las directrices.

**Cuándo no hace falta:** si tu base ya está al día, `/health` lo indica. No la ejecutes por precaución.

## Procedimiento

Ejecuta cada paso en orden y confirma el resultado antes de seguir.

### 1. Para el backend y el frontend

Ciérralos. Una copia tomada con la base en uso puede quedar incompleta.

### 2. Copia de seguridad, verificada

Desde la raíz del repositorio (PowerShell o terminal):

```
New-Item -ItemType Directory -Force data\backups\manual | Out-Null
$fecha = Get-Date -Format "yyyyMMdd-HHmmss"
Copy-Item data\novel_engine.sqlite "data\backups\manual\novel_engine-antes-0011-$fecha.sqlite"
Get-FileHash data\novel_engine.sqlite, "data\backups\manual\novel_engine-antes-0011-$fecha.sqlite"
```

Los dos hashes **deben ser idénticos**. Si no lo son, no sigas.

El sistema de copias automáticas está descrito en `docs/RESPALDO_Y_RESTAURACION.md`. Esta copia manual es adicional.

### 3. Revisión actual

Desde `backend/`:

```
python -m alembic current
```

Anota la revisión que muestra. Debe ser `0009_escritura_escenas` o una anterior a `0011`.

### 4. Recuento de filas antes

```
python -c "import sqlite3; c=sqlite3.connect('../data/novel_engine.sqlite'); print({t: c.execute(f'select count(*) from {t}').fetchone()[0] for t in ['projects','manuscripts','manuscript_versions','manuscript_drafts','structure_nodes','scene_manuscripts']})"
```

Guarda la salida.

### 5. Migrar

Desde `backend/`:

```
python -m alembic upgrade head
```

Debe terminar sin errores y mostrar los pasos `0010` y `0011`.

### 6. Verificar

Repite el recuento del paso 4. **Debe ser idéntico.** Después arranca el backend y abre `http://localhost:8000/health`:
`"al_dia": true` y `"revision_actual": "0011_recomendaciones_estructura"`.

### 7. Si algo falla

1. Para el backend.
2. Restaura la copia del paso 2: `Copy-Item` de la copia sobre `data\novel_engine.sqlite`.
3. Repite la comprobación de hashes.

**No uses `alembic downgrade`.** Las migraciones `0010` y `0011` no tienen bajada automática: la bajada lanza un error a
propósito. La restauración del archivo es la única vuelta atrás.

## Lo que este procedimiento no hace

- No borra ninguna novela, manuscrito, escena, versión ni punto de recuperación.
- No elimina la copia de seguridad: tú decides cuándo borrarla.
- No migra la base de pruebas `data/e2e.sqlite`; las pruebas la migran por sí solas.
