"""Versiones: numeración, inmutabilidad lógica, límites y hash."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.config import DEFAULT_MAX_VERSION_CHARS, Settings
from app.texts.errors import ContentTooLarge, IntegrityFailure, NotFoundError, ValidationFailed
from app.texts.normalization import content_sha256
from app.texts.service import TextService


def test_crear_manuscrito_genera_version_1_con_hash(service: TextService) -> None:
    manuscript = service.create_manuscript("Novela", "Primera frase.", "inicio")
    versions = service.list_versions(manuscript.id)
    assert [v.number for v in versions] == [1]
    assert versions[0].content == "Primera frase."
    assert versions[0].sha256 == content_sha256("Primera frase.")
    assert versions[0].char_count == len("Primera frase.")
    assert versions[0].note == "inicio"
    assert versions[0].parent_version_id is None


def test_anadir_version_incrementa_el_numero_y_conserva_las_anteriores(service: TextService) -> None:
    manuscript = service.create_manuscript("Novela", "Versión uno.", None)
    first = service.list_versions(manuscript.id)[0]
    first_hash = first.sha256

    service.add_version(manuscript.id, "Versión dos.", "revisión", None)

    versions = service.list_versions(manuscript.id)
    assert [v.number for v in versions] == [1, 2]
    assert versions[0].content == "Versión uno."
    assert versions[0].sha256 == first_hash
    assert versions[1].content == "Versión dos."


def test_partir_de_una_version_anterior_crea_una_version_nueva(service: TextService) -> None:
    manuscript = service.create_manuscript("Novela", "Base.", None)
    base = service.list_versions(manuscript.id)[0]
    service.add_version(manuscript.id, "Cambio posterior.", None, None)

    derived = service.add_version(manuscript.id, "Derivada de la base.", None, base.id)

    assert derived.number == 3
    assert derived.parent_version_id == base.id
    assert service.get_version(base.id).content == "Base."


def test_partir_de_una_version_de_otro_manuscrito_se_rechaza(service: TextService) -> None:
    first = service.create_manuscript("Uno", "Texto A.", None)
    second = service.create_manuscript("Dos", "Texto B.", None)
    foreign = service.list_versions(second.id)[0]
    with pytest.raises(ValidationFailed, match="mismo manuscrito"):
        service.add_version(first.id, "Intento.", None, foreign.id)


def test_partir_de_una_version_inexistente_se_rechaza(service: TextService) -> None:
    manuscript = service.create_manuscript("Novela", "Texto.", None)
    with pytest.raises(ValidationFailed):
        service.add_version(manuscript.id, "Intento.", None, 999_999)


def test_contenido_se_guarda_normalizado(service: TextService) -> None:
    manuscript = service.create_manuscript("Novela", "línea uno\r\nlínea dos\r", None)
    stored = service.list_versions(manuscript.id)[0]
    assert stored.content == "línea uno\nlínea dos\n"
    assert stored.char_count == len(stored.content)


def test_manuscrito_inexistente_lanza_no_encontrado(service: TextService) -> None:
    with pytest.raises(NotFoundError):
        service.get_manuscript(424242)
    with pytest.raises(NotFoundError):
        service.list_versions(424242)


def test_limite_configurable_acepta_el_maximo_y_rechaza_uno_mas(session: Session) -> None:
    small = TextService(session, max_version_chars=10)
    manuscript = small.create_manuscript("Límite", "x" * 10, None)
    assert small.list_versions(manuscript.id)[0].char_count == 10
    with pytest.raises(ContentTooLarge, match="límite es 10"):
        small.add_version(manuscript.id, "x" * 11, None, None)


def test_limite_se_cuenta_tras_normalizar_los_saltos(session: Session) -> None:
    small = TextService(session, max_version_chars=3)
    # "a\r\nb" tiene 4 caracteres en bruto y 3 tras normalizar: debe aceptarse.
    manuscript = small.create_manuscript("Saltos", "a\r\nb", None)
    assert small.list_versions(manuscript.id)[0].content == "a\nb"


def test_limite_por_defecto_es_500000() -> None:
    assert DEFAULT_MAX_VERSION_CHARS == 500_000
    assert Settings().max_version_chars == 500_000


def test_limite_por_defecto_acepta_500000_y_rechaza_500001(service: TextService) -> None:
    manuscript = service.create_manuscript("Tamaño", "a" * 500_000, None)
    assert service.list_versions(manuscript.id)[0].char_count == 500_000
    with pytest.raises(ContentTooLarge):
        service.add_version(manuscript.id, "a" * 500_001, None, None)


def test_hash_incorrecto_impide_leer_la_version(
    service: TextService,
    session: Session,
    session_factory: sessionmaker[Session],
    settings: Settings,
) -> None:
    manuscript = service.create_manuscript("Corrupto", "Contenido íntegro.", None)
    version = service.list_versions(manuscript.id)[0]

    # Simulación de manipulación del archivo: se desactiva el trigger solo dentro de esta prueba.
    session.execute(text("DROP TRIGGER trg_manuscript_versions_no_update"))
    session.execute(
        text("UPDATE manuscript_versions SET content = 'manipulado' WHERE id = :id"),
        {"id": version.id},
    )
    session.commit()

    # Una sesión nueva: la sesión original conserva en caché el objeto ya cargado.
    with session_factory() as fresh_session:
        fresh_service = TextService(fresh_session, max_version_chars=settings.max_version_chars)
        with pytest.raises(IntegrityFailure, match="hash"):
            fresh_service.get_version(version.id)
