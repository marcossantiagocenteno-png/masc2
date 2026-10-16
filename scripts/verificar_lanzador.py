"""Comprobaciones estáticas de los lanzadores de Windows. No ejecuta nada de lo que contienen.

Uso: python scripts/verificar_lanzador.py   (sale con código 1 si encuentra algún problema)

Comprueba: finales de línea CRLF, UTF-8, ausencia de órdenes destructivas o de migración, único comando de Git que
modifica el repositorio (``git merge --ff-only``), cambio al directorio del archivo y equilibrio de paréntesis en los
bloques de cmd. No sustituye a la prueba manual en Windows (ver docs/LANZADOR_WINDOWS.md).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ARCHIVOS = ("Iniciar Novel Engine.bat", "Detener Novel Engine.bat")

# Órdenes que nunca deben aparecer como comandos (no como texto de un mensaje).
PROHIBIDOS = [
    r"\bgit\s+(checkout|switch|reset|clean|push|pull|stash|commit|rebase|restore|branch\s+-[dD])\b",
    r"--force",
    r"\balembic\b\s+(upgrade|downgrade|stamp|revision)",
    r"(?m)^\s*@?(del|erase|rmdir|rd|move|format)\s",
]
# Único comando de Git permitido que cambia el repositorio.
GIT_MODIFICA = re.compile(r"\bgit\s+(merge|fetch|rev-parse|rev-list|status|remote)\b")


def _problemas_de_bloques(lineas: list[str]) -> list[str]:
    """Paréntesis sin escapar dentro de bloques ``( ... )``: cmd cierra el bloque con cualquiera de ellos."""
    problemas: list[str] = []
    profundidad = 0
    for numero, linea in enumerate(lineas, 1):
        if linea.startswith(":"):
            profundidad = 0
        dentro_comillas = False
        i = 0
        while i < len(linea):
            c = linea[i]
            if c == '"':
                dentro_comillas = not dentro_comillas
            elif not dentro_comillas and c == "^":
                i += 2
                continue
            elif not dentro_comillas and c == "(":
                profundidad += 1
            elif not dentro_comillas and c == ")":
                profundidad -= 1
                if profundidad < 0:
                    problemas.append(f"línea {numero}: paréntesis de cierre sin bloque abierto")
                    profundidad = 0
            i += 1
    if profundidad != 0:
        problemas.append(f"bloques sin cerrar al final ({profundidad})")
    return problemas


def revisar(archivo: Path) -> list[str]:
    problemas: list[str] = []
    crudo = archivo.read_bytes()
    try:
        texto = crudo.decode("utf-8")
    except UnicodeDecodeError:
        return [f"{archivo.name}: no es UTF-8"]
    if b"\r\n" not in crudo or re.search(rb"(?<!\r)\n", crudo):
        problemas.append(f"{archivo.name}: finales de línea que no son CRLF")
    for patron in PROHIBIDOS:
        for coincidencia in re.finditer(patron, texto, re.IGNORECASE):
            linea = texto[: coincidencia.start()].count("\n") + 1
            if "call :fallo" in texto.split("\n")[linea - 1]:
                continue  # texto de un mensaje de error, no un comando
            problemas.append(f"{archivo.name}:{linea}: orden prohibida «{coincidencia.group(0).strip()}»")
    lineas = texto.replace("\r", "").split("\n")
    for linea in lineas:
        # «for %%t in (git node …)» solo enumera herramientas: no es un comando de Git.
        if "in (git" in linea or linea.lstrip().startswith(("rem", "echo")):
            continue
        for comando in re.findall(r"\bgit\s+[a-z-]+", linea):
            if GIT_MODIFICA.match(comando) is None:
                problemas.append(f"{archivo.name}: comando de Git no previsto: «{comando}»")
    if "merge --ff-only" in texto and texto.count("git merge") != 1:
        problemas.append(f"{archivo.name}: debe haber exactamente un «git merge»")
    if archivo.name.startswith("Iniciar") and "git merge --ff-only" not in texto:
        problemas.append(f"{archivo.name}: falta la actualización de solo avance rápido")
    requeridos = ('cd /d "%~dp0"', "setlocal") if archivo.name.startswith("Iniciar") else ("setlocal",)
    for requerido in requeridos + (("chcp 65001",) if archivo.name.startswith("Iniciar") else ()):
        if requerido not in texto:
            problemas.append(f"{archivo.name}: falta «{requerido}»")
    problemas += [f"{archivo.name}: {p}" for p in _problemas_de_bloques(lineas)]
    return problemas


def main() -> int:
    problemas: list[str] = []
    for nombre in ARCHIVOS:
        ruta = RAIZ / nombre
        if not ruta.exists():
            problemas.append(f"falta {nombre}")
            continue
        problemas += revisar(ruta)
    for problema in problemas:
        print("[PROBLEMA]", problema)
    if not problemas:
        print("Comprobaciones estáticas del lanzador: correctas (no ejecutadas en Windows).")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
