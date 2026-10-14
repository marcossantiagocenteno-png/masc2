"""Línea de comandos de copias: códigos de salida y comportamientos seguros por defecto."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.backups.__main__ import EXIT_FAILED, EXIT_OK, EXIT_USAGE, main
from app.config import Settings
from tests.backup_fakes import FakeClock, populate, sha


@pytest.fixture
def cli_env(settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "copias"
    monkeypatch.setenv("DATABASE_URL", settings.database_url)
    monkeypatch.setenv("NOVEL_ENGINE_BACKUP_DIR", str(directory))
    return directory


def test_verificar_distingue_copia_valida_de_invalida(cli_env: Path, settings: Settings, tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    populate(settings, FakeClock())
    assert main(["copia"]) == EXIT_OK
    valid = next(cli_env.glob("novel_engine-*.sqlite"))

    assert main(["verificar", str(valid)]) == EXIT_OK
    broken = tmp_path / "rota.sqlite"
    broken.write_bytes(b"nada")
    assert main(["verificar", str(broken)]) == EXIT_FAILED
    assert "No válida" in capsys.readouterr().out


def test_restaurar_sin_confirmar_no_toca_nada(cli_env: Path, settings: Settings, capsys) -> None:  # type: ignore[no-untyped-def]
    populate(settings, FakeClock())
    main(["copia"])
    backup = next(cli_env.glob("novel_engine-*.sqlite"))
    before = sha(Path(settings.database_url.removeprefix("sqlite:///")))

    assert main(["restaurar", str(backup)]) == EXIT_USAGE
    assert sha(Path(settings.database_url.removeprefix("sqlite:///"))) == before
    assert list(cli_env.glob("preventiva-*")) == []


def test_retencion_avisa_de_que_no_borra(cli_env: Path, settings: Settings, capsys) -> None:  # type: ignore[no-untyped-def]
    populate(settings, FakeClock())
    assert main(["retencion"]) == EXIT_OK
    assert "NO SE BORRA NADA" in capsys.readouterr().out


def test_copia_con_base_no_sqlite_se_rechaza(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://usuario@servidor/base")
    monkeypatch.setenv("NOVEL_ENGINE_BACKUP_DIR", str(tmp_path))
    with pytest.raises(SystemExit):
        main(["copia"])
