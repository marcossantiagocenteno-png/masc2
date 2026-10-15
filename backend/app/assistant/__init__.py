"""Asistente conversacional del proyecto (chat global y autocompletado).

Un solo motor de asistencia comparte proveedor, contexto, memoria y propuestas entre el chat y el autocompletado.
El modelo propone; el backend valida y aplica. Ningún proveedor accede a la base de datos ni al sistema de archivos.
"""
