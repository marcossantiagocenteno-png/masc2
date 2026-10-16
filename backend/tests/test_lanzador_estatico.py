"""Comprobaciones estáticas de los lanzadores de Windows (ver scripts/verificar_lanzador.py).

No ejecutan los .bat: solo revisan su texto. La prueba real en Windows está en docs/LANZADOR_WINDOWS.md.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]


def _verificador():
    spec = importlib.util.spec_from_file_location("verificar_lanzador", RAIZ / "scripts" / "verificar_lanzador.py")
    modulo = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modulo)
    return modulo


def test_los_lanzadores_pasan_las_comprobaciones_estaticas() -> None:
    assert _verificador().main() == 0


@pytest.mark.parametrize(
    "linea",
    ["git reset --hard", "git clean -fd", "git checkout otra-rama", "git push --force", "alembic upgrade head"],
)
def test_una_orden_destructiva_se_detecta(tmp_path: Path, linea: str) -> None:
    original = (RAIZ / "Iniciar Novel Engine.bat").read_bytes().decode("utf-8")
    copia = tmp_path / "Iniciar Novel Engine.bat"
    copia.write_bytes((original + f"\r\n{linea}\r\n").encode("utf-8"))
    assert _verificador().revisar(copia), f"no detectó «{linea}»"


def test_un_parentesis_suelto_dentro_de_un_bloque_se_detecta(tmp_path: Path) -> None:
    original = (RAIZ / "Iniciar Novel Engine.bat").read_bytes().decode("utf-8")
    copia = tmp_path / "Iniciar Novel Engine.bat"
    copia.write_bytes((original.replace("\r\n", "\n").replace("echo Actualizando", "echo cambio) Actualizando").replace("\n", "\r\n")).encode("utf-8"))
    assert any("sin bloque abierto" in p for p in _verificador().revisar(copia))
