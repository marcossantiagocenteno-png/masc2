"""Servicio del asistente: conversación, propuestas con aprobación explícita y autocompletado.

Solo ``aprobar`` cambia datos de la novela, y solo aplica la propuesta que el autor acaba de aceptar, en una única
transacción. El resto de operaciones guardan mensajes, propuestas o memoria, nunca el canon.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.assistant.contexto import (
    CAMPOS_TEXTO,
    construir_contexto,
    contexto_autocompletado,
    huella,
    huella_de_fila,
    memoria_resumen,
)
from app.assistant.errors import AssistantFailed, AssistantOutputInvalid, AuthorizationRequired, ContextChanged, ProposalInvalid
from app.assistant.providers import AssistantProvider, PropuestaBorrador, componer_completado, componer_envio, resolver_proveedor
from app.config import Settings
from app.db.base import utc_now
from app.db.models import AssistantConversation, AssistantMemoryItem, AssistantMessage, AssistantProposal, Project
from app.planning import kinds as K
from app.planning.service import PlanningService
from app.texts.errors import ConflictError, NotFoundError, TextError, ValidationFailed

HISTORIAL_MENSAJES = 10
MAX_TEXTO_MENSAJE = 4000
MAX_CAMPO_PROPUESTA = 4000
MAX_MOTIVO = 500
ESTADOS_PROPUESTA = ("pendiente", "aplicada", "rechazada", "fallida", "desactualizada")
ESTADOS_DECIDIBLES = ("pendiente", "desactualizada")
OPERACIONES = ("crear", "actualizar")

# Campos que una propuesta puede crear. Los identificadores y el estado nunca los escribe el asistente.
CAMPOS_CREAR: dict[str, tuple[str, ...]] = {
    "personaje": ("name",) + CAMPOS_TEXTO["personaje"],
    "lugar": ("name",) + CAMPOS_TEXTO["lugar"],
    "elemento_trama": ("kind", "title") + CAMPOS_TEXTO["elemento_trama"],
    "acontecimiento": ("title",) + CAMPOS_TEXTO["acontecimiento"],
}
REQUERIDOS_CREAR: dict[str, tuple[str, ...]] = {
    "personaje": ("name",),
    "lugar": ("name",),
    "elemento_trama": ("kind", "title"),
    "acontecimiento": ("title",),
}
# Estado de memoria que corresponde a cada estado de propuesta.
MEMORIA_POR_ESTADO = {
    "pendiente": "propuesta",
    "aplicada": "confirmado",
    "rechazada": "rechazada",
    "desactualizada": "pendiente",
    "fallida": "pendiente",
}


class _Desactualizada(Exception):
    """El elemento cambió desde que se propuso. Se detecta antes de tocar nada."""

    def __init__(self, motivo: str) -> None:
        super().__init__(motivo)
        self.motivo = motivo


class AssistantService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        client_factory: Callable[[str, float], Any] | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._session = session
        self._settings = settings
        self._client_factory = client_factory
        self._clock = clock
        self._planning = PlanningService(session, clock)

    # ------------------------------------------------------------------
    # Proyecto, conversación e historial
    # ------------------------------------------------------------------

    def _proyecto(self, project_id: int) -> Project:
        project = self._session.get(Project, project_id)
        if project is None:
            raise NotFoundError(f"no existe el proyecto {project_id}")
        return project

    def _proyecto_activo(self, project_id: int) -> Project:
        project = self._proyecto(project_id)
        if project.status == "archivado":
            raise ValidationFailed("el proyecto está archivado; el asistente no escribe en él")
        return project

    def conversacion(self, project_id: int) -> AssistantConversation:
        """Chat de la novela. Hay una conversación activa por proyecto; se crea la primera vez."""
        self._proyecto(project_id)
        conversacion = self._session.scalar(
            select(AssistantConversation)
            .where(AssistantConversation.project_id == project_id)
            .order_by(AssistantConversation.id)
        )
        if conversacion is None:
            ahora = self._clock()
            conversacion = AssistantConversation(
                project_id=project_id, title="Chat de la novela", created_at=ahora, updated_at=ahora
            )
            self._session.add(conversacion)
            self._session.commit()
        return conversacion

    def mensajes(self, project_id: int) -> list[AssistantMessage]:
        conversacion = self.conversacion(project_id)
        return list(
            self._session.scalars(
                select(AssistantMessage)
                .where(AssistantMessage.project_id == project_id, AssistantMessage.conversation_id == conversacion.id)
                .order_by(AssistantMessage.id)
            ).all()
        )

    def _historial(self, conversacion_id: int) -> list[tuple[str, str]]:
        filas = self._session.scalars(
            select(AssistantMessage)
            .where(AssistantMessage.conversation_id == conversacion_id, AssistantMessage.role != "sistema")
            .order_by(AssistantMessage.id.desc())
            .limit(HISTORIAL_MENSAJES)
        ).all()
        return [(fila.role, fila.content) for fila in reversed(filas)]

    # ------------------------------------------------------------------
    # Proveedor y autorización de contenido externo
    # ------------------------------------------------------------------

    def proveedor(self) -> AssistantProvider:
        return resolver_proveedor(self._settings, self._client_factory)

    def _autorizar(self, proveedor: AssistantProvider, contenido: str, autorizacion_hash: str | None) -> None:
        """Un proveedor externo solo recibe el contenido exacto que el autor ha revisado en la vista previa."""
        if not proveedor.is_external:
            return
        if not autorizacion_hash:
            raise AuthorizationRequired(
                f"El proveedor «{proveedor.name}» es externo: revisa el contenido que se enviará y autorízalo antes de continuar."
            )
        if autorizacion_hash != huella(contenido):
            raise ContextChanged(
                "La novela o la conversación han cambiado desde la vista previa. Revisa el contenido de nuevo. No se ha enviado nada."
            )

    def vista_previa(self, project_id: int, texto: str) -> dict[str, Any]:
        """Contenido exacto que se enviaría al proveedor. Usa la misma composición que el envío real."""
        conversacion = self.conversacion(project_id)
        texto = _validar_texto(texto)
        proveedor = self.proveedor()
        contexto = construir_contexto(self._session, project_id, self._settings.assistant_max_context_chars)
        contenido = componer_envio(contexto, self._historial(conversacion.id), texto)
        return {
            "contenido": contenido,
            "huella": huella(contenido),
            "proveedor": proveedor.name,
            "externo": proveedor.is_external,
            "simulado": proveedor.is_simulated,
        }

    # ------------------------------------------------------------------
    # Mensajes
    # ------------------------------------------------------------------

    def enviar(
        self, project_id: int, client_id: str, texto: str, autorizacion_hash: str | None = None
    ) -> dict[str, Any]:
        """Envía un mensaje. Reenviar el mismo ``client_id`` devuelve lo ya guardado, sin llamar al proveedor."""
        conversacion = self.conversacion(project_id)
        texto = _validar_texto(texto)
        existente = self._session.scalar(
            select(AssistantMessage).where(
                AssistantMessage.conversation_id == conversacion.id, AssistantMessage.client_id == client_id
            )
        )
        if existente is not None:
            return self._respuesta_desde(conversacion, existente)

        self._proyecto_activo(project_id)
        proveedor = self.proveedor()
        contexto = construir_contexto(self._session, project_id, self._settings.assistant_max_context_chars)
        historial = self._historial(conversacion.id)
        self._autorizar(proveedor, componer_envio(contexto, historial, texto), autorizacion_hash)

        usuario = AssistantMessage(
            project_id=project_id,
            conversation_id=conversacion.id,
            client_id=client_id,
            role="usuario",
            content=texto,
            created_at=self._clock(),
        )
        self._session.add(usuario)
        self._session.flush()

        try:
            respuesta = proveedor.responder(contexto, historial, texto)
        except Exception as error:  # noqa: BLE001 — cualquier fallo del proveedor se informa sin su texto técnico
            if isinstance(error, AssistantOutputInvalid):
                aviso = "La respuesta del asistente no cumplió el formato esperado. Tu mensaje queda guardado; reintenta el envío."
            else:
                aviso = f"No se pudo obtener respuesta del asistente ({proveedor.name}). Tu mensaje queda guardado; reintenta el envío."
            self._mensaje_sistema(project_id, conversacion.id, aviso)
            self._session.commit()
            return self._respuesta_desde(conversacion, usuario, error=aviso)

        contenido = respuesta.texto.strip()
        if respuesta.preguntas:
            contenido += "\n\nPreguntas para ti:\n" + "\n".join(f"- {pregunta}" for pregunta in respuesta.preguntas)
        asistente = AssistantMessage(
            project_id=project_id,
            conversation_id=conversacion.id,
            role="asistente",
            content=contenido,
            proveedor=proveedor.name,
            simulado=proveedor.is_simulated,
            created_at=self._clock(),
        )
        self._session.add(asistente)
        self._session.flush()

        descartadas: list[str] = []
        for borrador in respuesta.propuestas:
            try:
                datos = self._validar_borrador(project_id, borrador)
            except ProposalInvalid as motivo:
                descartadas.append(str(motivo))
                continue
            propuesta = self._nueva_propuesta(project_id, conversacion.id, asistente.id, datos)
            self._sincronizar_memoria(propuesta)
        if descartadas:
            self._mensaje_sistema(
                project_id,
                conversacion.id,
                f"{len(descartadas)} propuesta(s) descartada(s) por no cumplir las reglas: {descartadas[0]}",
            )
        self._session.commit()
        return self._respuesta_desde(conversacion, usuario)

    def _mensaje_sistema(self, project_id: int, conversacion_id: int, texto: str) -> None:
        self._session.add(
            AssistantMessage(
                project_id=project_id, conversation_id=conversacion_id, role="sistema", content=texto, created_at=self._clock()
            )
        )
        self._session.flush()

    def _respuesta_desde(
        self, conversacion: AssistantConversation, usuario: AssistantMessage, error: str | None = None
    ) -> dict[str, Any]:
        """Mensajes desde el del usuario y las propuestas que nacieron de ellos."""
        mensajes = list(
            self._session.scalars(
                select(AssistantMessage)
                .where(
                    AssistantMessage.conversation_id == conversacion.id,
                    AssistantMessage.id >= usuario.id,
                )
                .order_by(AssistantMessage.id)
            ).all()
        )
        propuestas = list(
            self._session.scalars(
                select(AssistantProposal)
                .where(
                    AssistantProposal.conversation_id == conversacion.id,
                    AssistantProposal.message_id.in_([m.id for m in mensajes]),
                )
                .order_by(AssistantProposal.id)
            ).all()
        )
        return {"mensajes": mensajes, "propuestas": propuestas, "error": error}

    # ------------------------------------------------------------------
    # Propuestas: validación, creación y decisión
    # ------------------------------------------------------------------

    def _validar_borrador(self, project_id: int, borrador: PropuestaBorrador) -> dict[str, Any]:
        """Comprueba la propuesta contra las reglas de la novela. Lanza ``ProposalInvalid`` si no cumple."""
        if borrador.operacion not in OPERACIONES:
            raise ProposalInvalid("operación no válida")
        entidad = borrador.entidad
        if entidad not in CAMPOS_TEXTO:
            raise ProposalInvalid(f"entidad no válida: {entidad}")
        motivo = (borrador.motivo or "").strip()
        if not motivo:
            raise ProposalInvalid("la propuesta no explica su motivo")
        if not isinstance(borrador.datos, dict) or not borrador.datos:
            raise ProposalInvalid("la propuesta no contiene cambios")

        if entidad == "premisa":
            if borrador.operacion != "actualizar" or borrador.target_id is not None:
                raise ProposalInvalid("la premisa solo se puede actualizar y no lleva identificador")
            permitidos = CAMPOS_TEXTO["premisa"]
            base = huella_de_fila(self._proyecto(project_id), permitidos)
            target = None
        elif borrador.operacion == "crear":
            if borrador.target_id is not None:
                raise ProposalInvalid("crear no lleva identificador de elemento")
            permitidos = CAMPOS_CREAR[entidad]
            for campo in REQUERIDOS_CREAR[entidad]:
                if not str(borrador.datos.get(campo, "")).strip():
                    raise ProposalInvalid(f"falta «{campo}»")
            if entidad == "elemento_trama" and borrador.datos.get("kind") not in K.PLOT_KINDS:
                raise ProposalInvalid("tipo de elemento de trama no válido")
            base = None
            target = None
        else:
            if borrador.target_id is None:
                raise ProposalInvalid("actualizar exige el elemento existente")
            try:
                fila = self._planning.get(entidad, project_id, borrador.target_id)
            except NotFoundError:
                raise ProposalInvalid("el elemento no existe en esta novela") from None
            if fila.archived_at is not None:
                raise ProposalInvalid("el elemento está archivado")
            permitidos = CAMPOS_TEXTO[entidad]
            base = huella_de_fila(fila, permitidos)
            target = fila.id

        desconocidos = set(borrador.datos) - set(permitidos)
        if desconocidos:
            raise ProposalInvalid(f"campos no permitidos: {', '.join(sorted(desconocidos))}")
        campos: dict[str, str] = {}
        for campo, valor in borrador.datos.items():
            if not isinstance(valor, str):
                raise ProposalInvalid(f"«{campo}» debe ser texto")
            if len(valor) > MAX_CAMPO_PROPUESTA:
                raise ProposalInvalid(f"«{campo}» supera el límite de {MAX_CAMPO_PROPUESTA} caracteres")
            campos[campo] = valor.strip()
        return {
            "operacion": borrador.operacion,
            "entidad": entidad,
            "target_id": target,
            "campos": campos,
            "base": base,
            "motivo": motivo[:MAX_MOTIVO],
        }

    def _nueva_propuesta(
        self, project_id: int, conversacion_id: int, mensaje_id: int, datos: dict[str, Any]
    ) -> AssistantProposal:
        ahora = self._clock()
        propuesta = AssistantProposal(
            project_id=project_id,
            conversation_id=conversacion_id,
            message_id=mensaje_id,
            operacion=datos["operacion"],
            entidad=datos["entidad"],
            target_id=datos["target_id"],
            datos=json.dumps(datos["campos"], ensure_ascii=False, sort_keys=True),
            base_snapshot=datos["base"],
            motivo=datos["motivo"],
            dependencias="[]",
            estado="pendiente",
            created_at=ahora,
            updated_at=ahora,
        )
        self._session.add(propuesta)
        self._session.flush()
        return propuesta

    def _propuesta(self, project_id: int, proposal_id: int) -> AssistantProposal:
        propuesta = self._session.scalar(
            select(AssistantProposal).where(AssistantProposal.id == proposal_id, AssistantProposal.project_id == project_id)
        )
        if propuesta is None:
            raise NotFoundError(f"no existe la propuesta {proposal_id} en este proyecto")
        return propuesta

    def propuestas(self, project_id: int, estado: str | None = None) -> list[AssistantProposal]:
        self._proyecto(project_id)
        consulta = select(AssistantProposal).where(AssistantProposal.project_id == project_id)
        if estado is not None:
            if estado not in ESTADOS_PROPUESTA:
                raise ValidationFailed(f"estado no válido: '{estado}'")
            consulta = consulta.where(AssistantProposal.estado == estado)
        return list(self._session.scalars(consulta.order_by(AssistantProposal.id.desc())).all())

    def actual_de(self, propuesta: AssistantProposal) -> dict[str, Any]:
        """Valores actuales de los campos que la propuesta quiere cambiar, para revisarla frente a lo que hay."""
        if propuesta.operacion != "actualizar":
            return {}
        if propuesta.entidad == "premisa":
            fila: Any = self._session.get(Project, propuesta.project_id)
        else:
            fila = self._session.get(K.MODELS[propuesta.entidad], propuesta.target_id)
        if fila is None:
            return {}
        return {campo: getattr(fila, campo) or "" for campo in json.loads(propuesta.datos)}

    def base_cambiada(self, propuesta: AssistantProposal) -> bool:
        """True si el elemento ha cambiado desde que se propuso. La aprobación lo vuelve a comprobar."""
        if propuesta.base_snapshot is None:
            return False
        if propuesta.entidad == "premisa":
            fila: Any = self._session.get(Project, propuesta.project_id)
            campos = CAMPOS_TEXTO["premisa"]
        else:
            fila = self._session.get(K.MODELS[propuesta.entidad], propuesta.target_id)
            campos = CAMPOS_TEXTO[propuesta.entidad]
        return fila is None or huella_de_fila(fila, campos) != propuesta.base_snapshot

    def _sincronizar_memoria(self, propuesta: AssistantProposal, texto: str | None = None) -> None:
        """Una entrada de memoria por propuesta, con el estado que tiene ahora."""
        etiqueta = texto or f"{propuesta.entidad} ({propuesta.operacion}): {propuesta.motivo}"
        kind = MEMORIA_POR_ESTADO[propuesta.estado]
        item = self._session.scalar(
            select(AssistantMemoryItem).where(
                AssistantMemoryItem.project_id == propuesta.project_id, AssistantMemoryItem.proposal_id == propuesta.id
            )
        )
        ahora = self._clock()
        if item is None:
            self._session.add(
                AssistantMemoryItem(
                    project_id=propuesta.project_id,
                    kind=kind,
                    texto=etiqueta[:300],
                    proposal_id=propuesta.id,
                    created_at=ahora,
                    updated_at=ahora,
                )
            )
        else:
            item.kind = kind
            item.texto = etiqueta[:300]
            item.updated_at = ahora
        self._session.flush()

    def aprobar(self, project_id: int, proposal_id: int) -> AssistantProposal:
        """Aplica una propuesta aprobada. Idempotente: aprobar dos veces no duplica nada."""
        self._proyecto_activo(project_id)
        propuesta = self._propuesta(project_id, proposal_id)
        if propuesta.estado == "aplicada":
            return propuesta
        if propuesta.estado != "pendiente":
            raise ConflictError(f"la propuesta está «{propuesta.estado}» y no se puede aprobar")

        ahora = self._clock()
        reclamo = self._session.execute(
            update(AssistantProposal)
            .where(
                AssistantProposal.id == proposal_id,
                AssistantProposal.project_id == project_id,
                AssistantProposal.estado == "pendiente",
            )
            .values(estado="aplicada", decided_at=ahora, updated_at=ahora)
        )
        if reclamo.rowcount != 1:
            # Otra petición ya decidió la propuesta: se informa de su estado real.
            self._session.rollback()
            propuesta = self._propuesta(project_id, proposal_id)
            if propuesta.estado == "aplicada":
                return propuesta
            raise ConflictError(f"la propuesta está «{propuesta.estado}» y no se puede aprobar")
        self._session.refresh(propuesta)

        try:
            resultado_id = self._aplicar(project_id, propuesta)
        except _Desactualizada as aviso:
            propuesta.estado = "desactualizada"
            propuesta.resultado = aviso.motivo
            propuesta.updated_at = self._clock()
            self._sincronizar_memoria(propuesta)
            self._session.commit()
            return propuesta
        except Exception as error:  # noqa: BLE001 — la aplicación falla entera; nada queda a medias
            self._session.rollback()
            motivo = str(error) if isinstance(error, TextError) else "Error interno al aplicar; no se ha cambiado nada."
            self._session.execute(
                update(AssistantProposal)
                .where(AssistantProposal.id == proposal_id, AssistantProposal.estado == "pendiente")
                .values(estado="fallida", resultado=motivo, decided_at=self._clock(), updated_at=self._clock())
            )
            self._session.commit()
            propuesta = self._propuesta(project_id, proposal_id)
            self._sincronizar_memoria(propuesta)
            self._session.commit()
            return propuesta

        propuesta.resultado_id = resultado_id
        propuesta.resultado = f"{propuesta.entidad} #{resultado_id}" if resultado_id is not None else "premisa actualizada"
        propuesta.applied_at = self._clock()
        self._sincronizar_memoria(propuesta)
        self._session.commit()
        return propuesta

    def _aplicar(self, project_id: int, propuesta: AssistantProposal) -> int | None:
        """Aplica los cambios sin confirmar. Revalida antes de tocar nada. El llamador confirma o deshace."""
        campos = json.loads(propuesta.datos)
        if propuesta.entidad == "premisa":
            proyecto = self._proyecto(project_id)
            if propuesta.base_snapshot != huella_de_fila(proyecto, CAMPOS_TEXTO["premisa"]):
                raise _Desactualizada("La premisa ha cambiado desde que se propuso. Revisa la propuesta antes de aplicarla.")
            self._planning.update_narrative(project_id, campos, commit=False)
            return None

        if propuesta.operacion == "crear":
            fila = self._planning.create(propuesta.entidad, project_id, campos, commit=False)
            self._session.flush()
            return fila.id

        fila = self._planning.get(propuesta.entidad, project_id, propuesta.target_id)
        if fila.archived_at is not None:
            raise ValidationFailed("el elemento está archivado; no se aplica la propuesta")
        if huella_de_fila(fila, CAMPOS_TEXTO[propuesta.entidad]) != propuesta.base_snapshot:
            raise _Desactualizada("El elemento ha cambiado desde que se propuso. Revisa la propuesta antes de aplicarla.")
        if fila.estado == K.CANONICO:
            raise ValidationFailed(
                "el elemento es canónico; cambiarlo exige confirmación en su ficha. No se ha cambiado nada."
            )
        self._planning.update(propuesta.entidad, project_id, fila.id, campos, commit=False)
        self._session.flush()
        return fila.id

    def rechazar(self, project_id: int, proposal_id: int) -> AssistantProposal:
        """Rechaza la propuesta. No cambia ningún dato de la novela."""
        self._proyecto(project_id)
        propuesta = self._propuesta(project_id, proposal_id)
        if propuesta.estado == "rechazada":
            return propuesta
        if propuesta.estado not in ESTADOS_DECIDIBLES:
            raise ConflictError(f"la propuesta está «{propuesta.estado}» y no se puede rechazar")
        ahora = self._clock()
        reclamo = self._session.execute(
            update(AssistantProposal)
            .where(
                AssistantProposal.id == proposal_id,
                AssistantProposal.project_id == project_id,
                AssistantProposal.estado.in_(ESTADOS_DECIDIBLES),
            )
            .values(estado="rechazada", decided_at=ahora, updated_at=ahora)
        )
        if reclamo.rowcount != 1:
            self._session.rollback()
            propuesta = self._propuesta(project_id, proposal_id)
            if propuesta.estado == "rechazada":
                return propuesta
            raise ConflictError(f"la propuesta está «{propuesta.estado}» y no se puede rechazar")
        self._session.refresh(propuesta)
        self._sincronizar_memoria(propuesta)
        self._session.commit()
        return propuesta

    def memoria(self, project_id: int) -> list[AssistantMemoryItem]:
        self._proyecto(project_id)
        return memoria_resumen(self._session, project_id)

    # ------------------------------------------------------------------
    # Autocompletado de campos
    # ------------------------------------------------------------------

    def vista_previa_completado(
        self, project_id: int, entidad: str, campo: str, entidad_id: int | None, actual: str, instruccion: str | None
    ) -> dict[str, Any]:
        contenido = self._contenido_completado(project_id, entidad, campo, entidad_id, actual, instruccion)
        proveedor = self.proveedor()
        return {
            "contenido": contenido,
            "huella": huella(contenido),
            "proveedor": proveedor.name,
            "externo": proveedor.is_external,
            "simulado": proveedor.is_simulated,
        }

    def autocompletar(
        self,
        project_id: int,
        entidad: str,
        campo: str,
        entidad_id: int | None,
        actual: str,
        instruccion: str | None,
        autorizacion_hash: str | None = None,
    ) -> dict[str, Any]:
        """Sugerencia para un único campo. No guarda nada: el autor la acepta, edita o descarta en la interfaz."""
        contenido = self._contenido_completado(project_id, entidad, campo, entidad_id, actual, instruccion)
        proveedor = self.proveedor()
        self._autorizar(proveedor, contenido, autorizacion_hash)
        contexto = contexto_autocompletado(
            self._session, project_id, entidad, campo, entidad_id, self._settings.assistant_max_context_chars
        )
        try:
            texto = proveedor.completar(contexto, entidad, campo, actual, instruccion)
        except Exception as error:  # noqa: BLE001 — se informa sin el texto técnico del proveedor
            raise AssistantFailed(f"No se pudo generar la sugerencia ({proveedor.name}). Nada se ha cambiado.") from error
        return {"texto": texto.strip(), "proveedor": proveedor.name, "simulado": proveedor.is_simulated}

    def _contenido_completado(
        self, project_id: int, entidad: str, campo: str, entidad_id: int | None, actual: str, instruccion: str | None
    ) -> str:
        self._proyecto(project_id)
        if entidad not in CAMPOS_TEXTO or campo not in CAMPOS_TEXTO[entidad]:
            raise ValidationFailed(f"el campo «{campo}» no admite sugerencias de «{entidad}»")
        contexto = self._contexto_completado(project_id, entidad, campo, entidad_id)
        return componer_completado(contexto, entidad, campo, actual, instruccion)

    def _contexto_completado(self, project_id: int, entidad: str, campo: str, entidad_id: int | None):
        try:
            return contexto_autocompletado(
                self._session, project_id, entidad, campo, entidad_id, self._settings.assistant_max_context_chars
            )
        except LookupError as error:
            raise NotFoundError(str(error)) from None


def _validar_texto(texto: str) -> str:
    limpio = (texto or "").strip()
    if not limpio:
        raise ValidationFailed("el mensaje está vacío")
    if len(limpio) > MAX_TEXTO_MENSAJE:
        raise ValidationFailed(f"el mensaje supera {MAX_TEXTO_MENSAJE} caracteres")
    return limpio
