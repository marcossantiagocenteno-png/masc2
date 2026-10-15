"""Contexto de la novela que recibe el asistente. Solo lectura.

Incluye planificación, estructura, decisiones confirmadas y memoria narrativa. Nunca incluye el texto de los
manuscritos ni de las escenas: ese texto no sale del proyecto salvo que una función futura lo pida expresamente.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AssistantMemoryItem,
    Character,
    NarrativeDecision,
    NarrativeDirective,
    PlotElement,
    Place,
    Project,
    ProjectGenre,
    StructureNode,
    TimelineEvent,
)
from app.planning import directrices as DIR
from app.planning import generos as GENEROS

MAX_FIELD_CHARS = 300
MAX_ITEMS_PER_SECTION = 60
MEMORY_ITEMS_PER_KIND = 10
RECENT_DECISIONS = 10

# Campos editables que el autocompletado puede rellenar, por entidad. Cualquier otro campo se rechaza.
CAMPOS_TEXTO: dict[str, tuple[str, ...]] = {
    "personaje": ("description", "goals", "motivations", "conflicts", "evolution", "notes"),
    "lugar": ("description", "features", "notes"),
    "elemento_trama": ("description", "notes"),
    "acontecimiento": ("description", "notes"),
    "premisa": ("premise", "theme"),
}

ETIQUETAS_CAMPO: dict[str, str] = {
    "description": "descripción",
    "goals": "objetivos",
    "motivations": "motivaciones",
    "conflicts": "conflictos",
    "evolution": "evolución",
    "notes": "notas",
    "features": "rasgos",
    "premise": "premisa",
    "theme": "tema",
}


@dataclass(frozen=True)
class ContextoAsistente:
    """Contexto que se envía al proveedor. ``texto`` es exactamente lo que se muestra al autor antes de autorizar."""

    texto: str
    resumen: dict[str, Any] = field(default_factory=dict)


def _recortar(valor: str | None, limite: int = MAX_FIELD_CHARS) -> str:
    if not valor:
        return ""
    limpio = " ".join(valor.split())
    return limpio if len(limpio) <= limite else limpio[: limite - 1] + "…"


def _linea(etiqueta: str, valor: str | None) -> str:
    return f"{etiqueta}: {_recortar(valor)}" if valor and valor.strip() else f"{etiqueta}: (sin escribir)"


def construir_contexto(session: Session, project_id: int, limite_chars: int) -> ContextoAsistente:
    """Contexto completo de la novela. Solo elementos no archivados del proyecto indicado."""
    project = session.get(Project, project_id)
    if project is None:
        raise LookupError("proyecto inexistente")

    generos = session.scalars(
        select(ProjectGenre).where(ProjectGenre.project_id == project_id, ProjectGenre.activo.is_(True)).order_by(ProjectGenre.id)
    ).all()
    directivas = session.scalar(select(NarrativeDirective).where(NarrativeDirective.project_id == project_id))
    personajes = session.scalars(
        select(Character).where(Character.project_id == project_id, Character.archived_at.is_(None)).order_by(Character.id)
    ).all()
    lugares = session.scalars(
        select(Place).where(Place.project_id == project_id, Place.archived_at.is_(None)).order_by(Place.id)
    ).all()
    tramas = session.scalars(
        select(PlotElement).where(PlotElement.project_id == project_id, PlotElement.archived_at.is_(None)).order_by(PlotElement.id)
    ).all()
    eventos = session.scalars(
        select(TimelineEvent)
        .where(TimelineEvent.project_id == project_id, TimelineEvent.archived_at.is_(None))
        .order_by(TimelineEvent.narrative_order, TimelineEvent.id)
    ).all()
    nodos = session.scalars(
        select(StructureNode).where(StructureNode.project_id == project_id, StructureNode.archived_at.is_(None)).order_by(StructureNode.parent_id, StructureNode.position)
    ).all()
    decisiones = session.scalars(
        select(NarrativeDecision)
        .where(NarrativeDecision.project_id == project_id, NarrativeDecision.accion.in_(("aprobar_canon", "modificar_canon")))
        .order_by(NarrativeDecision.id.desc())
        .limit(RECENT_DECISIONS)
    ).all()
    memoria = session.scalars(
        select(AssistantMemoryItem).where(AssistantMemoryItem.project_id == project_id).order_by(AssistantMemoryItem.id.desc())
    ).all()

    lineas: list[str] = [f"PROYECTO: {project.name}"]
    lineas.append(_linea("PREMISA", project.premise))
    lineas.append(_linea("TEMA", project.theme))
    lineas.append(_linea("TONO", project.tone))
    etiquetas_generos = [
        GENEROS.ETIQUETAS.get(g.genre_key, g.genre_key) if g.genre_key != GENEROS.OTRO else (g.custom_label or "Otro")
        for g in generos
    ]
    lineas.append("GÉNEROS: " + (", ".join(etiquetas_generos) if etiquetas_generos else "(ninguno elegido)"))
    if directivas is not None:
        valores = [
            f"{etiqueta}={valor}"
            for etiqueta, valor in (
                ("punto de vista", directivas.punto_de_vista),
                ("focalización", directivas.focalizacion),
                ("persona", directivas.persona),
                ("tiempo verbal", directivas.tiempo_verbal),
                ("narrador", directivas.tipo_narrador),
            )
            if valor
        ]
        lineas.append("DIRECTRICES: " + (", ".join(valores) if valores else "(sin decidir)"))
        for etiqueta, valor in (("estilo", directivas.estilo), ("intención", directivas.intencion), ("límites", directivas.limites)):
            if valor and valor.strip():
                lineas.append(f"  {etiqueta}: {_recortar(valor)}")

    lineas.append(f"PERSONAJES ({len(personajes)}):")
    for personaje in personajes[:MAX_ITEMS_PER_SECTION]:
        lineas.append(f"- {personaje.name or '(sin nombre)'} [{personaje.estado}]")
        for campo in CAMPOS_TEXTO["personaje"]:
            valor = getattr(personaje, campo)
            if valor and valor.strip():
                lineas.append(f"    {ETIQUETAS_CAMPO[campo]}: {_recortar(valor)}")

    lineas.append(f"LUGARES ({len(lugares)}):")
    for lugar in lugares[:MAX_ITEMS_PER_SECTION]:
        lineas.append(f"- {lugar.name or '(sin nombre)'}: {_recortar(lugar.description) or '(sin descripción)'}")

    lineas.append(f"TRAMA ({len(tramas)}):")
    for trama in tramas[:MAX_ITEMS_PER_SECTION]:
        lineas.append(f"- [{trama.kind}] {trama.title or '(sin título)'}: {_recortar(trama.description) or '(sin descripción)'}")

    lineas.append(f"CRONOLOGÍA ({len(eventos)}):")
    for evento in eventos[:MAX_ITEMS_PER_SECTION]:
        orden = evento.narrative_order if evento.narrative_order is not None else "sin orden"
        momento = evento.story_time or "momento sin determinar"
        lineas.append(f"- ({orden}) {evento.title or '(sin título)'} · {momento}: {_recortar(evento.description)}")

    lineas.append(f"ESTRUCTURA ({len(nodos)} nodos):")
    lineas.extend(_esquema_estructura(nodos)[:MAX_ITEMS_PER_SECTION])

    if decisiones:
        lineas.append("DECISIONES CONFIRMADAS RECIENTES:")
        for decision in reversed(decisiones):
            lineas.append(f"- {decision.accion} {decision.element_kind} #{decision.element_id}: {_recortar(decision.nota) or 'sin nota'}")

    for tipo, etiqueta in (("confirmado", "MEMORIA CONFIRMADA"), ("pendiente", "PREGUNTAS PENDIENTES"), ("rechazada", "RECHAZADO ANTES")):
        elementos = [m for m in memoria if m.kind == tipo][:MEMORY_ITEMS_PER_KIND]
        if elementos:
            lineas.append(f"{etiqueta}:")
            lineas.extend(f"- {_recortar(m.texto)}" for m in elementos)

    texto = "\n".join(lineas)
    if len(texto) > limite_chars:
        texto = texto[: limite_chars - 40] + "\n[contexto recortado por el límite configurado]"

    resumen = {
        "personajes": [p.name for p in personajes[:MAX_ITEMS_PER_SECTION] if p.name],
        "lugares": [lugar.name for lugar in lugares[:MAX_ITEMS_PER_SECTION] if lugar.name],
        "tramas": len(tramas),
        "eventos": len(eventos),
        "nodos_estructura": len(nodos),
        "premisa": bool(project.premise and project.premise.strip()),
    }
    return ContextoAsistente(texto=texto, resumen=resumen)


def _esquema_estructura(nodos: Sequence[StructureNode]) -> list[str]:
    por_padre: dict[int | None, list[StructureNode]] = {}
    for nodo in nodos:
        por_padre.setdefault(nodo.parent_id, []).append(nodo)
    etiquetas = {"acto": "Acto", "capitulo": "Capítulo", "escena": "Escena"}
    salida: list[str] = []

    def visitar(padre: int | None, nivel: int) -> None:
        for nodo in por_padre.get(padre, []):
            titulo = nodo.title or "(sin título)"
            salida.append(f"{'  ' * nivel}- {etiquetas.get(nodo.kind, nodo.kind)}: {titulo} [{nodo.estado}]")
            visitar(nodo.id, nivel + 1)

    visitar(None, 0)
    return salida


def memoria_resumen(session: Session, project_id: int) -> list[AssistantMemoryItem]:
    return list(
        session.scalars(
            select(AssistantMemoryItem).where(AssistantMemoryItem.project_id == project_id).order_by(AssistantMemoryItem.id)
        ).all()
    )


def contexto_autocompletado(
    session: Session,
    project_id: int,
    entidad: str,
    campo: str,
    entidad_id: int | None,
    limite_chars: int,
) -> ContextoAsistente:
    """Contexto mínimo para completar un campo: premisa, géneros, directrices, decisiones y el propio elemento."""
    project = session.get(Project, project_id)
    if project is None:
        raise LookupError("proyecto inexistente")
    lineas = [f"PROYECTO: {project.name}", _linea("PREMISA", project.premise), _linea("TEMA", project.theme)]
    generos = session.scalars(
        select(ProjectGenre).where(ProjectGenre.project_id == project_id, ProjectGenre.activo.is_(True))
    ).all()
    etiquetas = [GENEROS.ETIQUETAS.get(g.genre_key, g.genre_key) for g in generos if g.genre_key != GENEROS.OTRO]
    lineas.append("GÉNEROS: " + (", ".join(etiquetas) if etiquetas else "(ninguno)"))
    directivas = session.scalar(select(NarrativeDirective).where(NarrativeDirective.project_id == project_id))
    if directivas is not None:
        for campo_dir in DIR.CAMPOS_VALOR:
            valor = getattr(directivas, campo_dir)
            if valor:
                lineas.append(f"{campo_dir}: {valor}")
    decisiones = session.scalars(
        select(NarrativeDecision)
        .where(NarrativeDecision.project_id == project_id, NarrativeDecision.accion.in_(("aprobar_canon", "modificar_canon")))
        .order_by(NarrativeDecision.id.desc())
        .limit(RECENT_DECISIONS)
    ).all()
    if decisiones:
        lineas.append("DECISIONES CONFIRMADAS:")
        lineas.extend(f"- {_recortar(d.nota) or d.accion}" for d in reversed(decisiones))

    if entidad == "premisa":
        lineas.append("ELEMENTO: premisa del proyecto")
    else:
        modelo = {"personaje": Character, "lugar": Place, "elemento_trama": PlotElement, "acontecimiento": TimelineEvent}[entidad]
        if entidad_id is not None:
            fila = session.scalar(select(modelo).where(modelo.id == entidad_id, modelo.project_id == project_id))
            if fila is None:
                raise LookupError("elemento inexistente en este proyecto")
            nombre = getattr(fila, "name", None) or getattr(fila, "title", None) or "(sin nombre)"
            lineas.append(f"ELEMENTO ({entidad}): {nombre}")
            for otro in ("description", "goals", "motivations", "conflicts", "evolution", "notes", "features"):
                if hasattr(fila, otro) and getattr(fila, otro):
                    lineas.append(f"  {ETIQUETAS_CAMPO.get(otro, otro)} actual: {_recortar(getattr(fila, otro))}")
        else:
            lineas.append(f"ELEMENTO ({entidad}): nuevo, sin datos previos")
    lineas.append(f"CAMPO A COMPLETAR: {ETIQUETAS_CAMPO.get(campo, campo)}")
    texto = "\n".join(lineas)
    if len(texto) > limite_chars:
        texto = texto[: limite_chars - 40] + "\n[contexto recortado por el límite configurado]"
    return ContextoAsistente(texto=texto, resumen={"entidad": entidad, "campo": campo})


def huella(texto: str) -> str:
    """Huella SHA-256 del contenido exacto. Permite autorizar sin reenviar el contenido."""
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def huella_de_fila(fila: Any, campos: Sequence[str]) -> str:
    """Resumen de los campos de un elemento. Detecta cambios incompatibles antes de aplicar una propuesta."""
    datos = {campo: _valor_serializable(getattr(fila, campo, None)) for campo in sorted(campos)}
    return hashlib.sha256(json.dumps(datos, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _valor_serializable(valor: Any) -> Any:
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return valor
    return str(valor)
