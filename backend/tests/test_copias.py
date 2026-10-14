"""Copias de seguridad: creación verificada, consistencia, fallos, rotación, bloqueo y registro.

Deterministas: el tiempo lo controla ``FakeClock``, las concurrencias se reproducen en
un orden fijo desde un gancho, y no hay esperas ni fechas reales.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app.backups import files
from app.backups.files import BackupLock, backup_name, list_backups, read_log
from app.backups.scheduler import BackupScheduler
from app.backups.service import BackupError, BackupService, copy_database
from app.backups.verify import schema_order, verify_sqlite
from app.config import Settings
from tests.backup_fakes import FakeClock, counts, populate, sha


def _service(settings: Settings, directory: Path, clock: FakeClock, **overrides) -> BackupService:
    options = {"keep": 14, "min_keep": 3, "max_age": timedelta(days=30)}
    options.update(overrides)
    return BackupService(
        source=Path(settings.database_url.removeprefix("sqlite:///")),
        directory=directory,
        clock=clock,
        **options,
    )


def _live(settings: Settings) -> Path:
    return Path(settings.database_url.removeprefix("sqlite:///"))


# 1. Copia válida de una base con datos -------------------------------------


def test_crea_una_copia_valida_de_una_base_con_datos(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    populate(settings, clock)
    outcome = _service(settings, tmp_path / "copias", clock).run()

    assert outcome.status == "creada"
    assert outcome.path is not None and outcome.path.exists()
    assert outcome.verification is not None and outcome.verification.ok
    assert verify_sqlite(outcome.path, schema_order()).ok
    assert files.read_manifest(outcome.path)["sha256"] == sha(outcome.path)


# 2. La copia contiene todo lo recuperable ----------------------------------


def test_la_copia_incluye_manuscritos_versiones_borradores_y_puntos(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    populate(settings, clock)
    outcome = _service(settings, tmp_path / "copias", clock).run()
    assert outcome.path is not None

    copy_counts = counts(outcome.path)
    assert copy_counts == counts(_live(settings))
    assert copy_counts["projects"] == 1
    assert copy_counts["manuscripts"] == 1
    assert copy_counts["manuscript_versions"] == 2
    assert copy_counts["manuscript_drafts"] == 1
    assert copy_counts["draft_recovery_points"] >= 2  # periódico y conflicto

    with closing(sqlite3.connect(outcome.path)) as connection:
        reasons = {row[0] for row in connection.execute("SELECT reason FROM draft_recovery_points")}
    assert {"periodico", "conflicto"} <= reasons


# 3. Consistencia mientras hay escrituras -----------------------------------


def test_la_copia_es_consistente_mientras_hay_escrituras(tmp_path: Path, settings: Settings) -> None:
    """Un escritor concurrente no puede colarse dentro de la instantánea de la copia.

    El gancho intenta escribir con la instantánea abierta: debe fallar por bloqueo
    (no hay espera). Tras la copia, la escritura sí se aplica. La copia refleja solo el estado previo.
    """
    clock = FakeClock()
    populate(settings, clock)
    before = counts(_live(settings))
    target = tmp_path / "copia.sqlite"
    outcome: dict[str, bool] = {}

    def writer_during_copy() -> None:
        writer = sqlite3.connect(_live(settings), timeout=0, isolation_level=None)
        try:
            writer.execute("INSERT INTO projects (name, status, created_at, updated_at) VALUES ('Intruso', 'activo', '2026-01-01', '2026-01-01')")
            outcome["escritura_durante_copia"] = True
        except sqlite3.OperationalError:
            outcome["escritura_durante_copia"] = False
        finally:
            writer.close()

    copy_database(_live(settings), target, on_step=writer_during_copy)

    assert outcome == {"escritura_durante_copia": False}
    assert verify_sqlite(target, schema_order()).ok
    assert counts(target) == before

    with closing(sqlite3.connect(_live(settings))) as connection:
        connection.execute("INSERT INTO projects (name, status, created_at, updated_at) VALUES ('Posterior', 'activo', '2026-01-01', '2026-01-01')")
        connection.commit()
    assert counts(_live(settings))["projects"] == before["projects"] + 1
    assert counts(target)["projects"] == before["projects"]


# 4. Copia inválida no sustituye la base activa; nada queda a medias ----------


@pytest.mark.parametrize(
    "damage",
    [
        pytest.param(lambda path: path.write_bytes(b"no es sqlite" * 100), id="no-sqlite"),
        pytest.param(lambda path: path.write_bytes(path.read_bytes()[:200]), id="truncada"),
    ],
)
def test_una_copia_invalida_no_sustituye_ni_deja_restos(tmp_path: Path, settings: Settings, damage) -> None:  # type: ignore[no-untyped-def]
    clock = FakeClock()
    populate(settings, clock)
    directory = tmp_path / "copias"
    live_before = sha(_live(settings))

    outcome = _service(settings, directory, clock, after_copy=damage).run()

    assert outcome.status == "fallida"
    assert list_backups(directory) == []
    assert not any(p.name.startswith(".tmp-") for p in directory.iterdir())
    assert sha(_live(settings)) == live_before


# 5. Un fallo no elimina las copias anteriores ----------------------------


def test_una_copia_fallida_no_elimina_las_anteriores(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    populate(settings, clock)
    directory = tmp_path / "copias"
    for _ in range(2):
        assert _service(settings, directory, clock).run().status == "creada"
        clock.advance(hours=1)
    before = {p.name for p in list_backups(directory)}
    assert len(before) == 2

    def corrupt(path: Path) -> None:
        path.write_bytes(b"roto")

    outcome = _service(settings, directory, clock, keep=1, min_keep=1, after_copy=corrupt).run()

    assert outcome.status == "fallida"
    assert {p.name for p in list_backups(directory)} == before


# 6. Rotación respeta los límites -------------------------------------------


def test_la_rotacion_respeta_la_cantidad_configurada(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    populate(settings, clock)
    directory = tmp_path / "copias"
    service = _service(settings, directory, clock, keep=2, min_keep=1)
    names = []
    for _ in range(3):
        names.append(service.run().path.name)  # type: ignore[union-attr]
        clock.advance(hours=1)

    remaining = [p.name for p in list_backups(directory)]
    assert remaining == [names[2], names[1]]
    assert not (directory / names[0]).exists()
    assert not (directory / names[0].replace(".sqlite", ".json")).exists()


def test_la_rotacion_por_antiguedad_conserva_el_minimo(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    populate(settings, clock)
    directory = tmp_path / "copias"
    service = _service(settings, directory, clock, keep=5, min_keep=2, max_age=timedelta(days=10))
    service.run()
    clock.advance(days=1)
    service.run()
    clock.advance(days=30)  # Las dos anteriores ya superan los 10 días.
    newest = service.run().path

    assert [p.name for p in list_backups(directory)] == [newest.name, list_backups(directory)[1].name]
    assert len(list_backups(directory)) == 2  # el mínimo de 2 se conserva aunque sean antiguas


# 7. Nombres nunca se sobrescriben ----------------------------------------


def test_dos_copias_en_el_mismo_instante_no_se_sobrescriben(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    populate(settings, clock)
    directory = tmp_path / "copias"
    service = _service(settings, directory, clock)
    first = service.run().path
    second = service.run().path  # mismo instante del reloj
    assert first != second
    assert first.exists() and second.exists()
    assert backup_name(clock.now) != second.name  # el segundo avanzó el nombre


# 8. Registro: fallos registrados, nunca éxito falso; sin contenido ----------


def test_los_fallos_quedan_en_el_registro_y_no_contienen_texto(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    populate(settings, clock)
    directory = tmp_path / "copias"
    secret_text = "TEXTO-DE-MANUSCRITO-NO-REGISTRAR"
    with sqlite3.connect(_live(settings)) as connection:
        connection.execute(
            "UPDATE manuscript_drafts SET content = ?, sha256 = 'x', char_count = 1",
            (secret_text,),
        )
        connection.commit()

    outcome = _service(settings, directory, clock, after_copy=lambda p: p.write_bytes(b"roto")).run()

    assert outcome.status == "fallida"
    events = [entry["evento"] for entry in read_log(directory)]
    assert "fallida" in events
    assert "correcta" not in events
    log_text = (directory / files.LOG_NAME).read_text(encoding="utf-8")
    assert secret_text not in log_text


def test_manifiesto_y_registro_no_contienen_claves_ni_texto(tmp_path: Path, settings: Settings) -> None:
    key = "sk-ant-api03-SECRETO-DE-PRUEBA-NO-REAL"
    clock = FakeClock()
    populate(settings, clock)
    directory = tmp_path / "copias"
    keyed = Settings(**{**settings.__dict__, "anthropic_api_key": key})
    outcome = _service(keyed, directory, clock).run()

    assert outcome.path is not None
    for path in directory.iterdir():
        if path.suffix in {".json", ".jsonl"}:
            assert key not in path.read_text(encoding="utf-8")
            assert "Texto formal" not in path.read_text(encoding="utf-8")


# 9. Operaciones simultáneas ----------------------------------------------


def test_una_segunda_copia_no_se_ejecuta_mientras_hay_una_en_curso(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    populate(settings, clock)
    directory = tmp_path / "copias"
    holder = BackupLock(directory, clock)
    assert holder.acquire()
    try:
        outcome = _service(settings, directory, clock).run()
    finally:
        holder.release()

    assert outcome.status == "omitida"
    assert list_backups(directory) == []
    assert "omitida" in [entry["evento"] for entry in read_log(directory)]


def test_un_bloqueo_obsoleto_se_retira_y_no_impide_copiar(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    populate(settings, clock)
    directory = tmp_path / "copias"
    directory.mkdir()
    (directory / files.LOCK_NAME).write_text('{"pid": 1, "desde": "2025-12-31T00:00:00"}', encoding="utf-8")

    outcome = _service(settings, directory, clock).run()

    assert outcome.status == "creada"
    assert not (directory / files.LOCK_NAME).exists()


def test_el_bloqueo_no_se_puede_tomar_dos_veces(tmp_path: Path) -> None:
    clock = FakeClock()
    first = BackupLock(tmp_path, clock)
    second = BackupLock(tmp_path, clock)
    assert first.acquire()
    assert not second.acquire()
    first.release()
    assert second.acquire()
    second.release()


# 10. Planificador: cadencia controlada, sin hilos ------------------------


def test_el_planificador_respeta_el_intervalo(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    populate(settings, clock)
    service = _service(settings, tmp_path / "copias", clock)
    scheduler = BackupScheduler(run=service.run, interval=timedelta(minutes=60), clock=clock)

    assert scheduler.tick() is not None  # primera ejecución inmediata
    clock.advance(minutes=30)
    assert scheduler.tick() is None
    clock.advance(minutes=31)
    assert scheduler.tick() is not None


def test_un_fallo_cuenta_como_intento_y_no_se_repite_en_bucle(tmp_path: Path, settings: Settings) -> None:
    clock = FakeClock()
    populate(settings, clock)
    failing = _service(settings, tmp_path / "copias", clock, after_copy=lambda p: p.write_bytes(b"roto"))
    scheduler = BackupScheduler(run=failing.run, interval=timedelta(minutes=60), clock=clock)

    assert scheduler.tick().status == "fallida"  # type: ignore[union-attr]
    assert scheduler.tick() is None  # no reintenta en el mismo instante


def test_nunca_se_renombra_a_nombre_definitivo_una_copia_invalida(
    tmp_path: Path, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regla: un archivo sin verificar nunca recibe el nombre definitivo de una copia.

    Se observa cada renombrado a nombre de copia. Con una copia dañada, el renombrado
    no debe producirse, aunque la verificación final también la rechazaría.
    """
    from app.backups import service as service_module

    clock = FakeClock()
    populate(settings, clock)
    directory = tmp_path / "copias"
    renamed_valid: list[bool] = []
    real_replace = os.replace

    def spy(source, destination):  # type: ignore[no-untyped-def]
        if str(destination).endswith(".sqlite") and files.COPY_PREFIX in Path(destination).name:
            renamed_valid.append(verify_sqlite(Path(source), schema_order()).ok)
        return real_replace(source, destination)

    monkeypatch.setattr(service_module.os, "replace", spy)
    outcome = _service(settings, directory, clock, after_copy=lambda p: p.write_bytes(b"roto")).run()

    assert outcome.status == "fallida"
    assert renamed_valid == []  # ningún renombrado a nombre de copia con un archivo dañado
