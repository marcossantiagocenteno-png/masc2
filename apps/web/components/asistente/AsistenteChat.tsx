"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  api,
  ApiError,
  type AsistenteEstado,
  type AsistenteMemoria,
  type AsistentePropuesta,
  type AsistenteVistaPrevia,
} from "@/lib/api";

/** Chat de la novela. Solo guarda mensajes; las propuestas cambian la novela únicamente si el autor las aprueba. */

const ETIQUETA_MEMORIA: Record<AsistenteMemoria["kind"], string> = {
  confirmado: "Confirmado",
  propuesta: "Propuesta",
  idea: "Idea",
  pendiente: "Pendiente",
  contradiccion: "Contradictorio",
  rechazada: "Rechazada",
};

const ETIQUETA_ENTIDAD: Record<AsistentePropuesta["entidad"], string> = {
  personaje: "Personaje",
  lugar: "Lugar",
  elemento_trama: "Trama y misterios",
  acontecimiento: "Cronología",
  premisa: "Premisa",
};

const ETIQUETA_ESTADO: Record<AsistentePropuesta["estado"], string> = {
  pendiente: "Pendiente",
  aplicada: "Aplicada",
  rechazada: "Rechazada",
  fallida: "Fallida",
  desactualizada: "Desactualizada",
};

const ETIQUETA_ROL: Record<AsistenteEstado["mensajes"][number]["role"], string> = {
  usuario: "Tú",
  asistente: "Asistente",
  sistema: "Sistema",
};

type EnvioPendiente = { texto: string; clientId: string; vista: AsistenteVistaPrevia };

function idCliente(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return `c-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function textoDeError(reason: unknown, respaldo: string): string {
  return reason instanceof ApiError ? reason.message : respaldo;
}

export function AsistenteChat({ projectId }: { projectId: number }) {
  const [estado, setEstado] = useState<AsistenteEstado | null>(null);
  const [propuestas, setPropuestas] = useState<AsistentePropuesta[]>([]);
  const [memoria, setMemoria] = useState<AsistenteMemoria[]>([]);
  const [texto, setTexto] = useState("");
  const [envioPendiente, setEnvioPendiente] = useState<EnvioPendiente | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(true);
  const [ocupado, setOcupado] = useState(false);

  const cargar = useCallback(async () => {
    try {
      const [nuevoEstado, nuevasPropuestas, nuevaMemoria] = await Promise.all([
        api.asistenteEstado(projectId),
        api.asistentePropuestas(projectId),
        api.asistenteMemoria(projectId),
      ]);
      setEstado(nuevoEstado);
      setPropuestas(nuevasPropuestas);
      setMemoria(nuevaMemoria);
      setError(null);
    } catch (reason) {
      setError(textoDeError(reason, "No se pudo cargar el asistente."));
    } finally {
      setCargando(false);
    }
  }, [projectId]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  async function enviar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const limpio = texto.trim();
    if (!limpio || ocupado) return;
    setOcupado(true);
    setAviso(null);
    setError(null);
    try {
      // Con un proveedor externo, primero se muestra el contenido exacto y no se envía nada hasta autorizarlo.
      if (estado?.proveedor.externo) {
        const vista = await api.asistenteVistaPrevia(projectId, limpio);
        setEnvioPendiente({ texto: limpio, clientId: idCliente(), vista });
        return;
      }
      const resultado = await api.asistenteEnviar(projectId, { client_id: idCliente(), texto: limpio });
      setTexto("");
      setAviso(resultado.error);
      await cargar();
    } catch (reason) {
      setError(textoDeError(reason, "No se pudo enviar el mensaje."));
    } finally {
      setOcupado(false);
    }
  }

  async function autorizarEnvio() {
    if (!envioPendiente || ocupado) return;
    setOcupado(true);
    try {
      const resultado = await api.asistenteEnviar(projectId, {
        client_id: envioPendiente.clientId,
        texto: envioPendiente.texto,
        autorizacion_hash: envioPendiente.vista.huella,
      });
      setEnvioPendiente(null);
      setTexto("");
      setAviso(resultado.error);
      await cargar();
    } catch (reason) {
      // Un 409 significa que la novela cambió después de la vista previa: el autor debe revisar de nuevo.
      setEnvioPendiente(null);
      setError(textoDeError(reason, "No se pudo enviar el mensaje."));
      await cargar();
    } finally {
      setOcupado(false);
    }
  }

  async function decidir(propuesta: AsistentePropuesta, accion: "aprobar" | "rechazar") {
    if (ocupado) return;
    setOcupado(true);
    setAviso(null);
    setError(null);
    try {
      const resultado =
        accion === "aprobar"
          ? await api.asistenteAprobar(projectId, propuesta.id)
          : await api.asistenteRechazar(projectId, propuesta.id);
      setAviso(`Propuesta ${ETIQUETA_ESTADO[resultado.estado].toLowerCase()}.`);
      await cargar();
    } catch (reason) {
      setError(textoDeError(reason, "No se pudo registrar la decisión."));
      await cargar();
    } finally {
      setOcupado(false);
    }
  }

  if (cargando) {
    return <p className="ne-meta" role="status">Cargando asistente…</p>;
  }

  const proveedor = estado?.proveedor;
  const mensajes = estado?.mensajes ?? [];
  const pendientes = propuestas.filter((p) => p.estado === "pendiente" || p.estado === "desactualizada");
  const historial = propuestas.filter((p) => p.estado !== "pendiente" && p.estado !== "desactualizada");

  return (
    <section aria-labelledby="asistente-titulo" className="flex flex-col gap-8">
      <div className="flex flex-col gap-2">
        <h2 id="asistente-titulo" className="ne-section-title">
          Asistente de la novela
        </h2>
        {proveedor ? (
          <p className="ne-meta">
            {proveedor.simulado
              ? "Respuestas simuladas, sin IA: sirven para probar el flujo y no consultan ningún modelo."
              : proveedor.externo
                ? `Proveedor externo: ${proveedor.nombre}. Cada envío muestra antes el contenido exacto y exige tu autorización.`
                : `Proveedor: ${proveedor.nombre}.`}
          </p>
        ) : null}
        <p className="ne-meta">Nada cambia en la novela sin tu aprobación.</p>
      </div>

      {error ? (
        <p role="alert" className="ne-notice ne-notice--danger">
          {error}
        </p>
      ) : null}
      {aviso ? (
        <p role="status" className="ne-notice ne-notice--ok">
          {aviso}
        </p>
      ) : null}

      <div className="flex flex-col gap-4">
        <h3 className="ne-label">Conversación</h3>
        {mensajes.length === 0 ? (
          <p className="ne-meta">
            Todavía no hay mensajes. Prueba con: «crea un personaje llamado Lucía». La petición se convierte en una propuesta que
            apruebas o rechazas abajo.
          </p>
        ) : (
          <ol aria-label="Mensajes del chat" className="flex flex-col gap-3">
            {mensajes.map((mensaje) => (
              <li key={mensaje.id} className="flex flex-col gap-1">
                <span className="ne-meta">
                  {ETIQUETA_ROL[mensaje.role]}
                  {mensaje.role === "asistente" && mensaje.simulado ? " · simulado, sin IA" : ""}
                </span>
                <p className="whitespace-pre-wrap">{mensaje.content}</p>
              </li>
            ))}
          </ol>
        )}

        {envioPendiente ? (
          <div role="region" aria-label="Autorización de envío" className="ne-notice flex flex-col gap-3">
            <p>
              Se enviará este contenido a {envioPendiente.vista.proveedor}. Revísalo antes de autorizarlo.
            </p>
            <details>
              <summary className="ne-link cursor-pointer">Ver el contenido exacto que se enviará</summary>
              <pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap text-sm">{envioPendiente.vista.contenido}</pre>
            </details>
            <div className="flex flex-wrap gap-3">
              <button type="button" className="ne-button ne-button--primary" onClick={autorizarEnvio} disabled={ocupado}>
                Autorizar y enviar
              </button>
              <button type="button" className="ne-button" onClick={() => setEnvioPendiente(null)} disabled={ocupado}>
                Cancelar
              </button>
            </div>
          </div>
        ) : null}

        <form onSubmit={enviar} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            <span className="ne-label">Mensaje al asistente</span>
            <textarea
              rows={3}
              maxLength={4000}
              value={texto}
              onChange={(event) => setTexto(event.target.value)}
              className="ne-prose-field"
            />
          </label>
          <div>
            <button type="submit" className="ne-button ne-button--primary" disabled={ocupado || texto.trim() === ""}>
              Enviar
            </button>
          </div>
        </form>
      </div>

      <div className="flex flex-col gap-4">
        <h3 className="ne-label">Propuestas pendientes</h3>
        {pendientes.length === 0 ? (
          <p className="ne-meta">No hay propuestas pendientes.</p>
        ) : (
          <ul className="flex flex-col gap-4">
            {pendientes.map((propuesta) => (
              <PropuestaItem key={propuesta.id} propuesta={propuesta} ocupado={ocupado} onDecidir={decidir} />
            ))}
          </ul>
        )}
      </div>

      {historial.length > 0 ? (
        <div className="flex flex-col gap-4">
          <h3 className="ne-label">Decisiones anteriores</h3>
          <ul className="flex flex-col gap-2">
            {historial.map((propuesta) => (
              <li key={propuesta.id} className="ne-meta">
                {ETIQUETA_ENTIDAD[propuesta.entidad]} · {propuesta.motivo} · <span className="font-medium">{ETIQUETA_ESTADO[propuesta.estado]}</span>
                {propuesta.resultado ? ` · ${propuesta.resultado}` : ""}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="flex flex-col gap-4">
        <h3 className="ne-label">Memoria narrativa</h3>
        {memoria.length === 0 ? (
          <p className="ne-meta">La memoria se llena cuando el asistente propone, confirmas o rechazas algo.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {memoria.map((item) => (
              <li key={item.id} className="text-sm">
                <span className="ne-meta">{ETIQUETA_MEMORIA[item.kind]}: </span>
                {item.texto}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function PropuestaItem({
  propuesta,
  ocupado,
  onDecidir,
}: {
  propuesta: AsistentePropuesta;
  ocupado: boolean;
  onDecidir: (propuesta: AsistentePropuesta, accion: "aprobar" | "rechazar") => void;
}) {
  const campos = Object.keys(propuesta.datos);
  return (
    <li className="ne-notice flex flex-col gap-3">
      <p className="font-medium">
        {propuesta.operacion === "crear" ? "Crear" : "Cambiar"} {ETIQUETA_ENTIDAD[propuesta.entidad].toLowerCase()}
        {propuesta.operacion === "actualizar" ? " existente" : ""}
      </p>
      <p className="ne-meta">Motivo: {propuesta.motivo}</p>
      {propuesta.base_cambiada ? (
        <p className="ne-meta">El elemento ha cambiado desde que se propuso. Al aprobar se revisará de nuevo.</p>
      ) : null}
      <dl className="grid gap-2 text-sm">
        {campos.map((campo) => (
          <div key={campo} className="flex flex-col gap-1">
            <dt className="ne-meta">{campo}</dt>
            {propuesta.operacion === "actualizar" ? (
              <dd>
                <span className="ne-meta">Actual: </span>
                {propuesta.actual[campo] || "(vacío)"}
              </dd>
            ) : null}
            <dd className="whitespace-pre-wrap">
              <span className="ne-meta">{propuesta.operacion === "actualizar" ? "Propuesto: " : ""}</span>
              {propuesta.datos[campo]}
            </dd>
          </div>
        ))}
      </dl>
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          className="ne-button ne-button--primary"
          disabled={ocupado}
          onClick={() => onDecidir(propuesta, "aprobar")}
        >
          Aprobar y aplicar
        </button>
        <button type="button" className="ne-button" disabled={ocupado} onClick={() => onDecidir(propuesta, "rechazar")}>
          Rechazar
        </button>
      </div>
    </li>
  );
}
