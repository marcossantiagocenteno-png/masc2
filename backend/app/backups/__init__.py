"""Copias de seguridad, restauración y retención de puntos de recuperación (fase 1c).

Piezas:

- ``files``: nombres, manifiestos, bloqueo, marcador de ejecución y registro operativo.
- ``verify``: comprobaciones de un archivo SQLite (integridad, esquema, conteos).
- ``service``: creación de copias verificadas y rotación.
- ``restore``: restauración administrativa con copia preventiva y reversión.
- ``retention``: métricas y vista previa de candidatos. No borra nada.
- ``scheduler``: frecuencia automática mientras corre el backend.
- ``__main__``: línea de comandos (``python -m app.backups``).
"""
