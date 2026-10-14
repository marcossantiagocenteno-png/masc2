"""Línea de comandos de copias y restauración.

Uso (desde ``backend/``, con el entorno virtual activo):

    python -m app.backups copia                  crea una copia verificada y rota las antiguas
    python -m app.backups listar                 lista las copias con su manifiesto
    python -m app.backups verificar RUTA         comprueba un archivo sin modificar nada
    python -m app.backups restaurar RUTA --confirmar
                                                 restaura (la aplicación debe estar detenida)
    python -m app.backups retencion              métricas y vista previa de limpieza; no borra
    python -m app.backups registro               últimas líneas del registro operativo
    python -m app.backups simulacro [CARPETA]    copia y restauración en una base temporal (cualquier sistema)

Códigos de salida: 0 correcto, 1 fallo o rechazo, 2 uso incorrecto, 3 omitido por otra operación.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.backups import files
from app.backups.restore import restore_backup
from app.backups.retention import RetentionPolicy, growth_warnings, newest_backup_points, preview
from app.backups.service import BackupService
from app.backups.verify import schema_order, sqlite_path, verify_sqlite
from app.config import Settings, load_settings

EXIT_OK, EXIT_FAILED, EXIT_USAGE, EXIT_SKIPPED = 0, 1, 2, 3


def _settings_paths() -> tuple[Settings, Path, Path]:
    settings = load_settings()
    source = sqlite_path(settings.database_url)
    if source is None:
        raise SystemExit("La URL de la base no es un archivo SQLite; este procedimiento no aplica.")
    if settings.backup_dir is None:
        raise SystemExit("NOVEL_ENGINE_BACKUP_DIR no está configurado.")
    return settings, source, Path(settings.backup_dir)


def _service(settings: Settings, source: Path, directory: Path) -> BackupService:
    return BackupService(
        source=source,
        directory=directory,
        clock=files.utc_clock,
        keep=settings.backup_keep,
        min_keep=settings.backup_min_keep,
        max_age=timedelta(days=settings.backup_max_age_days),
    )


def cmd_copia(_args: argparse.Namespace) -> int:
    settings, source, directory = _settings_paths()
    outcome = _service(settings, source, directory).run()
    print(outcome.message)
    if outcome.status == "creada" and outcome.verification is not None:
        print(f"Verificada: integridad ok, revisión {outcome.verification.revision}, hash {outcome.verification.sha256}")
    return {"creada": EXIT_OK, "omitida": EXIT_SKIPPED}.get(outcome.status, EXIT_FAILED)


def cmd_listar(_args: argparse.Namespace) -> int:
    _, _, directory = _settings_paths()
    backups = files.list_backups(directory)
    if not backups:
        print("No hay copias en", directory)
        return EXIT_OK
    for path in backups:
        manifest = files.read_manifest(path) or {}
        print(f"{path.name}  {path.stat().st_size:>12} bytes  sha256={str(manifest.get('sha256', 'sin manifiesto'))[:16]}…")
    return EXIT_OK


def cmd_verificar(args: argparse.Namespace) -> int:
    result = verify_sqlite(Path(args.ruta), schema_order())
    if result.ok:
        print(f"Válida. Revisión {result.revision} ({result.schema_status}). Hash {result.sha256}")
        print("Conteos:", json.dumps(result.counts, ensure_ascii=False))
        return EXIT_OK
    print("No válida:", "; ".join(result.problems))
    return EXIT_FAILED


def cmd_restaurar(args: argparse.Namespace) -> int:
    if not args.confirmar:
        print("Restaurar reemplaza la base activa. Repite el comando con --confirmar.", file=sys.stderr)
        return EXIT_USAGE
    settings, source, directory = _settings_paths()
    outcome = restore_backup(
        active=source,
        directory=directory,
        backup=Path(args.ruta),
        clock=files.utc_clock,
        allow_older_schema=args.permitir_esquema_anterior,
        ignore_running_marker=args.ignorar_marcador,
    )
    print(outcome.message)
    if outcome.preventive is not None:
        print(f"Copia preventiva de la base anterior: {outcome.preventive}")
    if outcome.status == "restaurada":
        print("Arranca el backend y comprueba que tus manuscritos y borradores están presentes.")
        return EXIT_OK
    return EXIT_FAILED


def cmd_retencion(args: argparse.Namespace) -> int:
    settings, source, directory = _settings_paths()
    engine = create_engine(f"sqlite:///{source.as_posix()}")
    try:
        with sessionmaker(bind=engine)() as session:
            result = preview(
                session,
                files.utc_clock(),
                RetentionPolicy(
                    keep_per_manuscript=settings.retention_keep_per_manuscript,
                    min_age=timedelta(days=settings.retention_min_age_days),
                ),
                newest_backup_points(directory),
            )
    finally:
        engine.dispose()
    database_bytes = source.stat().st_size if source.exists() else 0
    print("NO SE BORRA NADA. Vista previa de la política de retención.")
    for warning in growth_warnings(result, database_bytes):
        print("ADVERTENCIA:", warning)
    print(f"Puntos de recuperación: {result.points_total} {json.dumps(result.points_by_reason, ensure_ascii=False)}")
    print(f"Versiones formales: {result.versions_total} · borradores: {result.drafts_total}")
    print(f"Crecimiento reciente: {result.growth_per_day:.2f} puntos por día (últimos 30 días)")
    print("Conservados por:", json.dumps(result.kept_because, ensure_ascii=False))
    print(f"Candidatos a limpieza futura: {len(result.candidates)}")
    for candidate in result.candidates[:20]:
        print(f"  punto {candidate.point_id} · manuscrito {candidate.manuscript_id} · {candidate.reason}")
    return EXIT_OK


def cmd_simulacro(args: argparse.Namespace) -> int:
    import tempfile

    from app.backups.drill import run_drill

    folder = Path(args.carpeta) if args.carpeta else Path(tempfile.mkdtemp(prefix="novel-engine-simulacro-"))
    steps = run_drill(folder)
    for step in steps:
        print(f"[{'OK' if step.ok else 'FALLO'}] {step.name}" + (f" — {step.detail}" if step.detail and not step.ok else ""))
    print(f"Carpeta del simulacro: {folder}")
    passed = bool(steps) and all(step.ok for step in steps)
    print("SIMULACRO CORRECTO" if passed else "SIMULACRO CON FALLOS")
    return EXIT_OK if passed else EXIT_FAILED


def cmd_registro(args: argparse.Namespace) -> int:
    _, _, directory = _settings_paths()
    for line in files.read_log(directory, limit=args.lineas):
        print(json.dumps(line, ensure_ascii=False))
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.backups", description="Copias y restauración de Novel Engine.")
    commands = parser.add_subparsers(dest="comando", required=True)

    commands.add_parser("copia", help="crear una copia verificada").set_defaults(func=cmd_copia)
    commands.add_parser("listar", help="listar copias").set_defaults(func=cmd_listar)

    verify = commands.add_parser("verificar", help="verificar un archivo sin modificarlo")
    verify.add_argument("ruta")
    verify.set_defaults(func=cmd_verificar)

    restore = commands.add_parser("restaurar", help="restaurar una copia (aplicación detenida)")
    restore.add_argument("ruta")
    restore.add_argument("--confirmar", action="store_true", help="confirma que la base activa se reemplaza")
    restore.add_argument(
        "--permitir-esquema-anterior",
        action="store_true",
        help="acepta una copia de una versión de esquema anterior (luego: alembic upgrade head)",
    )
    restore.add_argument(
        "--ignorar-marcador",
        action="store_true",
        help="ignora el marcador de backend en marcha tras un cierre brusco. Solo si el backend NO está corriendo",
    )
    restore.set_defaults(func=cmd_restaurar)

    commands.add_parser("retencion", help="métricas y vista previa de limpieza (no borra)").set_defaults(
        func=cmd_retencion
    )

    drill = commands.add_parser("simulacro", help="copia y restauración en una base temporal")
    drill.add_argument("carpeta", nargs="?", help="carpeta de trabajo; por defecto, una temporal")
    drill.set_defaults(func=cmd_simulacro)

    log = commands.add_parser("registro", help="últimas líneas del registro operativo")
    log.add_argument("--lineas", type=int, default=30)
    log.set_defaults(func=cmd_registro)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
