"""Análisis editorial de fragmentos.

Un análisis examina un fragmento de una versión y produce hallazgos. El
análisis nunca modifica el texto: solo guarda diagnósticos vinculados a la
versión analizada.

Piezas:

- ``checks``: verificaciones deterministas. Son las únicas que pueden producir
  problemas verificables.
- ``provider``: interfaz de proveedores de modelos. Hoy solo existe el
  analizador simulado, identificado como tal en cada respuesta.
- ``validation``: reglas que todo hallazgo debe cumplir antes de guardarse.
- ``service``: orquesta el análisis y la persistencia.
"""
