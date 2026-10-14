"""Revisiones editoriales: citas literales, ubicación y reglas de los ítems."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import EditorialReview, ReviewItem
from app.texts.errors import ValidationFailed
from app.texts.kinds import INTENT_NOT_DECLARED, ITEM_KINDS
from app.texts.schemas import ReviewItemIn
from app.texts.service import TextService

TEXT = "Primera línea.\nLa lluvia caía sobre el tejado.\n  Última línea, con espacio final.  "


def _item(quote: str, start: int, end: int, **extra: object) -> ReviewItemIn:
    data: dict[str, object] = {
        "kind": "observacion",
        "quote": quote,
        "start_offset": start,
        "end_offset": end,
        "comment": "Comentario de prueba.",
    }
    data.update(extra)
    return ReviewItemIn.model_validate(data)


def _span(fragment: str) -> tuple[int, int]:
    """Posiciones (inicial, final) de un fragmento de TEXT, calculadas sin números mágicos."""
    start = TEXT.index(fragment)
    return start, start + len(fragment)


@pytest.fixture
def version_id(service: TextService) -> int:
    manuscript = service.create_manuscript("Revisiones", TEXT, None)
    return service.list_versions(manuscript.id)[0].id


def test_observacion_con_cita_exacta_se_guarda_con_su_ubicacion(
    service: TextService, version_id: int
) -> None:
    start, end = _span("lluvia")
    review = service.create_review(
        version_id, "Editora", [_item("lluvia", start, start + len("lluvia"))]
    )
    item = review.items[0]
    assert item.quote == "lluvia"
    assert item.start_offset == start
    assert item.end_offset == start + len("lluvia")
    assert item.line_number == 2
    assert item.version_id == version_id
    assert item.intent_status == INTENT_NOT_DECLARED


def test_cita_conserva_espacios_literales(service: TextService, version_id: int) -> None:
    quote = "  Última línea, con espacio final.  "
    start = TEXT.index(quote)
    review = service.create_review(version_id, "Editor", [_item(quote, start, start + len(quote))])
    assert review.items[0].quote == quote
    assert review.items[0].line_number == 3


def test_cita_que_no_coincide_se_rechaza_y_no_guarda_nada(
    session: Session, service: TextService, version_id: int
) -> None:
    with pytest.raises(ValidationFailed, match="no coincide exactamente"):
        service.create_review(version_id, "Editor", [_item("tejado", 0, 6)])
    assert session.scalar(select(func.count(EditorialReview.id))) == 0
    assert session.scalar(select(func.count(ReviewItem.id))) == 0


def test_lote_con_un_ítem_invalido_no_guarda_ninguno(
    session: Session, service: TextService, version_id: int
) -> None:
    start, end = _span("lluvia")
    good = _item("lluvia", start, end)
    bad = _item("nube", start, start + len("nube"))
    with pytest.raises(ValidationFailed, match=r"items\[1\]"):
        service.create_review(version_id, "Editor", [good, bad])
    assert session.scalar(select(func.count(ReviewItem.id))) == 0


def test_posicion_final_fuera_de_la_version_se_rechaza(service: TextService, version_id: int) -> None:
    with pytest.raises(ValidationFailed, match="supera la longitud"):
        service.create_review(version_id, "Editor", [_item("x", len(TEXT), len(TEXT) + 1)])


def test_posicion_inicial_no_menor_que_la_final_se_rechaza(service: TextService, version_id: int) -> None:
    with pytest.raises(ValidationFailed, match="menor que la final"):
        service.create_review(version_id, "Editor", [_item("x", 5, 5)])


def test_tipo_desconocido_se_rechaza(service: TextService, version_id: int) -> None:
    start, end = _span("lluvia")
    with pytest.raises(ValidationFailed, match="tipo no permitido"):
        service.create_review(version_id, "Editor", [_item("lluvia", start, end, kind="certeza")])


def test_inferencia_exige_cadena_de_inferencia(service: TextService, version_id: int) -> None:
    start, end = _span("lluvia")
    with pytest.raises(ValidationFailed, match="cadena de inferencia"):
        service.create_review(
            version_id, "Editor", [_item("lluvia", start, end, kind="inferencia")]
        )


def test_inferencia_con_cadena_se_guarda(service: TextService, version_id: int) -> None:
    start, end = _span("lluvia")
    review = service.create_review(
        version_id,
        "Editor",
        [
            _item(
                "lluvia",
                start,
                end,
                kind="inferencia",
                inference_basis="La lluvia aparece como fondo en otros pasajes.",
            )
        ],
    )
    assert review.items[0].kind == "inferencia"
    assert review.items[0].inference_basis.startswith("La lluvia")


def test_observacion_no_admite_cadena_de_inferencia(service: TextService, version_id: int) -> None:
    start, end = _span("lluvia")
    with pytest.raises(ValidationFailed, match="solo las inferencias"):
        service.create_review(
            version_id,
            "Editor",
            [_item("lluvia", start, end, inference_basis="No debería estar aquí.")],
        )


def test_dimension_invalida_se_rechaza_y_valida_se_acepta(service: TextService, version_id: int) -> None:
    start, end = _span("lluvia")
    with pytest.raises(ValidationFailed, match="dimensión no válida"):
        service.create_review(version_id, "Editor", [_item("lluvia", start, end, dimension="estilo")])
    review = service.create_review(
        version_id, "Editor", [_item("lluvia", start, end, dimension="prosa_y_voz")]
    )
    assert review.items[0].dimension == "prosa_y_voz"


def test_revision_no_aparece_en_otra_version_ni_la_modifica(
    service: TextService, version_id: int
) -> None:
    manuscript_id = service.get_version(version_id).manuscript_id
    hash_before = service.get_version(version_id).sha256
    start, end = _span("lluvia")
    service.create_review(version_id, "Editor", [_item("lluvia", start, end)])

    newer = service.add_version(manuscript_id, TEXT + " Nuevo final.", None, version_id)

    assert service.list_reviews(newer.id) == []
    assert len(service.list_reviews(version_id)) == 1
    assert service.get_version(version_id).sha256 == hash_before


def test_citas_se_validan_contra_la_version_indicada(service: TextService, version_id: int) -> None:
    """Una cita válida para la versión 1 no lo es para una versión 2 que cambió esas posiciones."""
    manuscript_id = service.get_version(version_id).manuscript_id
    start, end = _span("lluvia")
    newer = service.add_version(manuscript_id, "Otro texto completamente distinto.", None, None)
    with pytest.raises(ValidationFailed):
        service.create_review(newer.id, "Editor", [_item("lluvia", start, end)])
    review = service.create_review(version_id, "Editor", [_item("lluvia", start, end)])
    assert review.items[0].version_id == version_id


def test_listar_revisiones_devuelve_las_de_la_version(service: TextService, version_id: int) -> None:
    start, end = _span("lluvia")
    service.create_review(version_id, "Primera", [_item("lluvia", start, end)])
    service.create_review(version_id, "Segunda", [_item("lluvia", start, end)])
    reviews = service.list_reviews(version_id)
    assert [r.reviewer for r in reviews] == ["Primera", "Segunda"]


def test_tipos_permitidos_son_exactamente_observacion_e_inferencia() -> None:
    assert set(ITEM_KINDS) == {"observacion", "inferencia"}
