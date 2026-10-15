"""Endpoints de planificación, bajo ``/projects/{project_id}/planificacion``.

Sin ``from __future__ import annotations``: las rutas se generan con clausuras y FastAPI
necesita los tipos resueltos en tiempo de ejecución.
"""

import json
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.planning.schemas import (
    AcontecimientoIn,
    AprobacionIn,
    DirectricesIn,
    GenerarPropuestasIn,
    ModeloEstructuraIn,
    PropuestaEstructuraPatch,
    ElementoTramaIn,
    EstructuraCreate,
    EstructuraPatch,
    GenerosIn,
    LugarIn,
    MoverIn,
    NarrativeIn,
    PersonajeIn,
    ReordenarIn,
    VinculoIn,
)
from app.drafts.schemas import DraftOut, DraftSave
from app.planning import directrices as DIR
from app.planning import generos as GENEROS
from app.planning.escritura import SIN_ESCRITURA, SceneWritingService, scene_states
from app.planning.service import PlanningService
from app.texts.routes import get_session

router = APIRouter(prefix="/projects/{project_id}/planificacion")


def get_service(request: Request, session: Session = Depends(get_session)) -> PlanningService:
    return PlanningService(session, clock=request.app.state.clock)


def _out(row: Any) -> dict[str, Any]:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def _genero_out(row: Any) -> dict[str, Any]:
    return {"key": row.genre_key, "label": GENEROS.ETIQUETAS[row.genre_key], "custom_label": row.custom_label}


def _directivas_out(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    return {campo: getattr(row, campo) for campo in (*DIR.CAMPOS_TEXTO, *DIR.CAMPOS_VALOR)} | {
        "updated_at": row.updated_at.isoformat()
    }


@router.get("/narrativa")
def get_narrative(project_id: int, service: PlanningService = Depends(get_service)) -> dict[str, Any]:
    project = service.get_narrative(project_id)
    generos = [_genero_out(row) for row in service.get_genres(project_id)]
    return {
        "id": project.id,
        "name": project.name,
        "premise": project.premise,
        "synopsis": project.synopsis,
        "genres": generos,
        # Texto derivado de la selección activa, para compatibilidad. No es una fuente de datos.
        "genre": ", ".join(g["custom_label"] or g["label"] for g in generos) or None,
        "genre_catalog": GENEROS.catalogo(),
        "theme": project.theme,
        "tone": project.tone,
        "development_status": project.development_status,
        "directives": _directivas_out(service.get_directives(project_id)),
    }


@router.put("/generos")
def put_genres(
    project_id: int, payload: GenerosIn, service: PlanningService = Depends(get_service)
) -> dict[str, Any]:
    rows = service.set_genres(project_id, [(g.key, g.custom_label) for g in payload.generos])
    return {"genres": [_genero_out(row) for row in rows]}


@router.get("/directrices")
def get_directives(project_id: int, service: PlanningService = Depends(get_service)) -> dict[str, Any] | None:
    return _directivas_out(service.get_directives(project_id))


@router.put("/directrices")
def put_directives(
    project_id: int, payload: DirectricesIn, service: PlanningService = Depends(get_service)
) -> dict[str, Any] | None:
    row = service.put_directives(project_id, payload.model_dump())
    return _directivas_out(row)


@router.patch("/narrativa")
def update_narrative(
    project_id: int, payload: NarrativeIn, service: PlanningService = Depends(get_service)
) -> dict[str, Any]:
    service.update_narrative(project_id, payload.model_dump(exclude_unset=True))
    return get_narrative(project_id, service)


def _register_kind(route: str, kind: str, create_model: type) -> None:
    """Rutas CRUD y de canon para un tipo de elemento."""

    @router.get(f"/{route}", name=f"listar_{kind}")
    def list_items(
        project_id: int,
        include_archived: bool = False,
        estado: str | None = Query(default=None),
        service: PlanningService = Depends(get_service),
    ) -> list[dict[str, Any]]:
        return [_out(row) for row in service.list(kind, project_id, include_archived, estado)]

    @router.post(f"/{route}", status_code=status.HTTP_201_CREATED, name=f"crear_{kind}")
    def create_item(project_id: int, payload: create_model, service: PlanningService = Depends(get_service)) -> dict[str, Any]:  # type: ignore[valid-type]
        return _out(service.create(kind, project_id, payload.model_dump(exclude_unset=True)))

    @router.post(f"/{route}/propuestas", status_code=status.HTTP_201_CREATED, name=f"proponer_{kind}")
    def propose_item(project_id: int, payload: create_model, service: PlanningService = Depends(get_service)) -> dict[str, Any]:  # type: ignore[valid-type]
        return _out(service.create(kind, project_id, payload.model_dump(exclude_unset=True), propuesta=True))

    @router.get(f"/{route}/{{element_id}}", name=f"obtener_{kind}")
    def get_item(project_id: int, element_id: int, service: PlanningService = Depends(get_service)) -> dict[str, Any]:
        return _out(service.get(kind, project_id, element_id))

    @router.patch(f"/{route}/{{element_id}}", name=f"editar_{kind}")
    def update_item(
        project_id: int,
        element_id: int,
        payload: create_model,  # type: ignore[valid-type]
        confirmar_cambio_canon: bool = False,
        service: PlanningService = Depends(get_service),
    ) -> dict[str, Any]:
        row = service.update(
            kind,
            project_id,
            element_id,
            payload.model_dump(exclude_unset=True),
            confirmar_cambio_canon=confirmar_cambio_canon,
        )
        return _out(row)

    @router.post(f"/{route}/{{element_id}}/archivar", name=f"archivar_{kind}")
    def archive_item(
        project_id: int,
        element_id: int,
        confirmar_canon: bool = False,
        service: PlanningService = Depends(get_service),
    ) -> dict[str, Any]:
        return _out(service.archive(kind, project_id, element_id, confirmar_canon=confirmar_canon))

    @router.post(f"/{route}/{{element_id}}/aprobar", name=f"aprobar_{kind}")
    def approve_item(
        project_id: int,
        element_id: int,
        payload: AprobacionIn,
        service: PlanningService = Depends(get_service),
    ) -> dict[str, Any]:
        return _out(service.approve(kind, project_id, element_id, confirmar=payload.confirmar, nota=payload.nota))

    @router.post(f"/{route}/{{element_id}}/aceptar-propuesta", name=f"aceptar_{kind}")
    def accept_item(project_id: int, element_id: int, service: PlanningService = Depends(get_service)) -> dict[str, Any]:
        return _out(service.accept_proposal(kind, project_id, element_id))

    @router.get(f"/{route}/{{element_id}}/decisiones", name=f"decisiones_{kind}")
    def decisions(project_id: int, element_id: int, service: PlanningService = Depends(get_service)) -> list[dict[str, Any]]:
        return [_out(item) for item in service.decisions(kind, project_id, element_id)]

    @router.get(f"/{route}/{{element_id}}/vinculos", name=f"vinculos_de_{kind}")
    def links(
        project_id: int,
        element_id: int,
        include_archived: bool = False,
        service: PlanningService = Depends(get_service),
    ) -> list[dict[str, Any]]:
        service.get(kind, project_id, element_id)
        return [_out(row) for row in service.links_of(project_id, kind, element_id, include_archived)]


_register_kind("personajes", "personaje", PersonajeIn)
_register_kind("lugares", "lugar", LugarIn)
_register_kind("elementos-trama", "elemento_trama", ElementoTramaIn)
_register_kind("acontecimientos", "acontecimiento", AcontecimientoIn)


# ----------------------------------------------------------------------
# Estructura: actos, capítulos y escenas
# ----------------------------------------------------------------------


@router.get("/estructura")
def list_structure(
    project_id: int,
    include_archived: bool = False,
    service: PlanningService = Depends(get_service),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    """Nodos de la estructura. Cada escena lleva ``escritura``: ``sin_escritura``, ``sin_texto`` o ``con_texto``."""
    states = scene_states(session, project_id)
    rows = []
    for row in service.list("estructura", project_id, include_archived):
        data = _out(row)
        if row.kind == "escena":
            data["escritura"] = states.get(row.id, SIN_ESCRITURA)
        rows.append(data)
    return rows


def get_writing_service(request: Request, session: Session = Depends(get_session)) -> SceneWritingService:
    return SceneWritingService(session, clock=request.app.state.clock, max_chars=request.app.state.settings.max_version_chars)


@router.get("/estructura/{element_id}/escritura")
def read_scene_writing(
    project_id: int, element_id: int, service: SceneWritingService = Depends(get_writing_service)
) -> dict[str, Any]:
    """Estado de la escritura de una escena y su borrador. Solo accesible dentro de su proyecto."""
    info = service.read(project_id, element_id)
    draft = info.pop("draft")
    info["draft"] = DraftOut.model_validate(draft, from_attributes=True).model_dump() if draft is not None else None
    return info


@router.post("/estructura/{element_id}/escritura", status_code=status.HTTP_201_CREATED, response_model=None)
def start_scene_writing(
    project_id: int, element_id: int, response: Response, service: SceneWritingService = Depends(get_writing_service)
) -> dict[str, Any]:
    """Inicia la escritura de una escena. Idempotente: si ya existe, devuelve la existente (200)."""
    _, created = service.start(project_id, element_id)
    if not created:
        response.status_code = status.HTTP_200_OK
    info = service.read(project_id, element_id)
    draft = info.pop("draft")
    info["draft"] = DraftOut.model_validate(draft, from_attributes=True).model_dump() if draft is not None else None
    return info


@router.put("/estructura/{element_id}/escritura/borrador")
def save_scene_draft(
    project_id: int,
    element_id: int,
    payload: DraftSave,
    service: SceneWritingService = Depends(get_writing_service),
) -> dict[str, Any]:
    """Guarda el texto de una escena con escritura condicional (409 si la revisión no es la actual)."""
    draft = service.save(project_id, element_id, payload.content, payload.base_revision, keep_previous=payload.keep_previous)
    return DraftOut.model_validate(draft, from_attributes=True).model_dump()


@router.post("/estructura", status_code=status.HTTP_201_CREATED)
def create_structure(
    project_id: int, payload: EstructuraCreate, service: PlanningService = Depends(get_service)
) -> dict[str, Any]:
    data = payload.model_dump(exclude_unset=True, exclude={"kind", "parent_id"})
    return _out(service.create_node(project_id, payload.kind, payload.parent_id, data))


@router.post("/estructura/reordenar")
def reorder_structure(
    project_id: int, payload: ReordenarIn, service: PlanningService = Depends(get_service)
) -> list[dict[str, Any]]:
    rows = service.reorder(project_id, payload.parent_id, payload.orden, confirmar_cambio_canon=payload.confirmar_cambio_canon)
    return [_out(row) for row in rows]


@router.post("/estructura/{element_id}/mover")
def move_structure_node(
    project_id: int, element_id: int, payload: MoverIn, service: PlanningService = Depends(get_service)
) -> dict[str, Any]:
    """Mueve un acto, capítulo o escena a otro padre compatible, o a la raíz."""
    row = service.move_node(
        project_id,
        element_id,
        payload.parent_id,
        payload.posicion,
        confirmar_cambio_canon=payload.confirmar_cambio_canon,
    )
    return _out(row)


@router.get("/estructura/{element_id}")
def get_structure(project_id: int, element_id: int, service: PlanningService = Depends(get_service)) -> dict[str, Any]:
    return _out(service.get("estructura", project_id, element_id))


@router.patch("/estructura/{element_id}")
def update_structure(
    project_id: int,
    element_id: int,
    payload: EstructuraPatch,
    confirmar_cambio_canon: bool = False,
    service: PlanningService = Depends(get_service),
) -> dict[str, Any]:
    return _out(
        service.update(
            "estructura",
            project_id,
            element_id,
            payload.model_dump(exclude_unset=True),
            confirmar_cambio_canon=confirmar_cambio_canon,
        )
    )


@router.post("/estructura/{element_id}/archivar")
def archive_structure(
    project_id: int, element_id: int, confirmar_canon: bool = False, service: PlanningService = Depends(get_service)
) -> dict[str, Any]:
    return _out(service.archive("estructura", project_id, element_id, confirmar_canon=confirmar_canon))


@router.post("/estructura/{element_id}/aprobar")
def approve_structure(
    project_id: int, element_id: int, payload: AprobacionIn, service: PlanningService = Depends(get_service)
) -> dict[str, Any]:
    return _out(service.approve("estructura", project_id, element_id, confirmar=payload.confirmar, nota=payload.nota))


@router.get("/estructura/{element_id}/vinculos")
def structure_links(
    project_id: int,
    element_id: int,
    include_archived: bool = False,
    service: PlanningService = Depends(get_service),
) -> list[dict[str, Any]]:
    """Vínculos de un nodo. Solo las escenas se vinculan (personajes, lugares, acontecimientos y trama)."""
    node = service.get("estructura", project_id, element_id)
    if node.kind != "escena":
        return []
    return [_out(row) for row in service.links_of(project_id, "escena", element_id, include_archived)]


@router.get("/estructura/{element_id}/decisiones")
def structure_decisions(project_id: int, element_id: int, service: PlanningService = Depends(get_service)) -> list[dict[str, Any]]:
    return [_out(item) for item in service.decisions("estructura", project_id, element_id)]


# ----------------------------------------------------------------------
# Vínculos
# ----------------------------------------------------------------------


@router.get("/vinculos")
def list_links(
    project_id: int, include_archived: bool = False, service: PlanningService = Depends(get_service)
) -> list[dict[str, Any]]:
    return [_out(row) for row in service.list("vinculo", project_id, include_archived)]


@router.post("/vinculos", status_code=status.HTTP_201_CREATED)
def create_link(project_id: int, payload: VinculoIn, service: PlanningService = Depends(get_service)) -> dict[str, Any]:
    row = service.link(
        project_id,
        (payload.origen.tipo, payload.origen.id),
        (payload.destino.tipo, payload.destino.id),
        payload.relacion,
        propuesta=payload.propuesta,
    )
    return _out(row)


@router.get("/vinculos/{element_id}")
def get_link(project_id: int, element_id: int, service: PlanningService = Depends(get_service)) -> dict[str, Any]:
    return _out(service.get("vinculo", project_id, element_id))


@router.post("/vinculos/{element_id}/archivar")
def archive_link(
    project_id: int, element_id: int, confirmar_canon: bool = False, service: PlanningService = Depends(get_service)
) -> dict[str, Any]:
    return _out(service.archive("vinculo", project_id, element_id, confirmar_canon=confirmar_canon))


@router.post("/vinculos/{element_id}/aprobar")
def approve_link(
    project_id: int, element_id: int, payload: AprobacionIn, service: PlanningService = Depends(get_service)
) -> dict[str, Any]:
    return _out(service.approve("vinculo", project_id, element_id, confirmar=payload.confirmar, nota=payload.nota))


def _propuesta_out(row: Any) -> dict[str, Any]:
    """Propuesta con sus entradas decodificadas, para que el autor pueda inspeccionar qué datos se usaron."""
    return _out(row) | {"entradas": json.loads(row.entradas)}


@router.get("/estructura-recomendada")
def get_recomendaciones(project_id: int, service: PlanningService = Depends(get_service)) -> dict[str, Any]:
    data = service.recomendaciones_estructura(project_id)
    data["propuestas"] = [_propuesta_out(row) for row in data["propuestas"]]
    return data


@router.put("/estructura-recomendada/modelo")
def put_modelo_estructura(
    project_id: int, payload: ModeloEstructuraIn, service: PlanningService = Depends(get_service)
) -> dict[str, Any]:
    row = service.elegir_modelo_estructura(project_id, payload.model_key)
    return {"modelo_elegido": row.model_key, "elegido_en": row.created_at.isoformat()}


@router.post("/estructura-recomendada/propuestas", status_code=status.HTTP_201_CREATED)
def post_propuestas_estructura(
    project_id: int, payload: GenerarPropuestasIn, service: PlanningService = Depends(get_service)
) -> list[dict[str, Any]]:
    rows = service.generar_propuestas_estructura(project_id, payload.model_key)
    return [_propuesta_out(row) for row in rows]


@router.patch("/estructura-recomendada/propuestas/{proposal_id}")
def patch_propuesta_estructura(
    project_id: int,
    proposal_id: int,
    payload: PropuestaEstructuraPatch,
    service: PlanningService = Depends(get_service),
) -> dict[str, Any]:
    row = service.editar_propuesta_estructura(project_id, proposal_id, payload.model_dump(exclude_unset=True))
    return _propuesta_out(row)


@router.post("/estructura-recomendada/propuestas/{proposal_id}/aceptar")
def aceptar_propuesta_estructura(
    project_id: int, proposal_id: int, service: PlanningService = Depends(get_service)
) -> dict[str, Any]:
    return _out(service.aceptar_propuesta_estructura(project_id, proposal_id))


@router.post("/estructura-recomendada/propuestas/{proposal_id}/rechazar")
def rechazar_propuesta_estructura(
    project_id: int, proposal_id: int, service: PlanningService = Depends(get_service)
) -> dict[str, Any]:
    return _propuesta_out(service.rechazar_propuesta_estructura(project_id, proposal_id))
