"""Borradores persistentes y puntos de recuperación (fase 1b).

El borrador es el texto en edición de un manuscrito. Se guarda en la base de datos
con escritura condicional: cada cambio indica la revisión que conoce el cliente y
solo se aplica si sigue siendo la actual.
"""
