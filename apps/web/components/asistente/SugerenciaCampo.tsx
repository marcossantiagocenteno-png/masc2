"use client";

import { useState } from "react";
import {
  api,
  ApiError,
  type AsistenteCompletarCuerpo,
  type AsistenteEntidad,
  type AsistenteVistaPrevia,
} from "@/lib/api";

/**
 * Sugerencia del asistente para un único campo. Nunca guarda: la sugerencia entra en el campo del formulario, sin
 * guardar, y la persona autora la guarda con el botón del propio formulario. Usa la misma autorización que el chat.
 */

/** Límite del backend para el texto actual enviado al proveedor. */
const MAX_ACTUAL = 4000;

type Fase = "cerrado" | "autorizando" | "revisando";

type Props = {
  projectId: number;
  entidad: AsistenteEntidad;
  campo: string;
  entidadId: number | null;
  valorActual: string;
  /** Nombre del campo para el texto accesible («Sugerir para Descripción»). */
  etiqueta: string;
  disabled?: boolean;
  onAceptar: (texto: string) => void;
};

export function SugerenciaCampo({ projectId, entidad, campo, entidadId, valorActual, etiqueta, disabled, onAceptar }: Props) {
  const [fase, setFase] = useState<Fase>("cerrado");
  const [vista, setVista] = useState<AsistenteVistaPrevia | null>(null);
  const [borrador, setBorrador] = useState("");
  const [simulado, setSimulado] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cuerpo: AsistenteCompletarCuerpo = {
    entidad,
    campo,
    entidad_id: entidadId,
    actual: valorActual.slice(0, MAX_ACTUAL),
    instruccion: null,
  };

  function cerrar() {
    setFase("cerrado");
    setVista(null);
    setBorrador("");
    setError(null);
  }

  async function generar(autorizacionHash?: string) {
    const sugerencia = await api.asistenteCompletar(projectId, { ...cuerpo, autorizacion_hash: autorizacionHash });
    setBorrador(sugerencia.texto);
    setSimulado(sugerencia.simulado);
    setVista(null);
    setFase("revisando");
  }

  async function pedir() {
    setOcupado(true);
    setError(null);
    try {
      const previa = await api.asistenteCompletarVistaPrevia(projectId, cuerpo);
      if (previa.externo) {
        // Con proveedor externo no se envía nada hasta que la persona autora vea el contenido exacto.
        setVista(previa);
        setFase("autorizando");
      } else {
        await generar();
      }
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "No se pudo generar la sugerencia.");
    } finally {
      setOcupado(false);
    }
  }

  async function autorizar() {
    if (!vista) return;
    setOcupado(true);
    setError(null);
    try {
      await generar(vista.huella);
    } catch (reason) {
      // Un 409 significa que el contenido cambió tras la vista previa: se vuelve a revisar desde cero.
      cerrar();
      setError(reason instanceof ApiError ? reason.message : "No se pudo generar la sugerencia.");
    } finally {
      setOcupado(false);
    }
  }

  if (fase === "cerrado") {
    return (
      <div className="flex flex-col gap-1">
        <div>
          <button
            type="button"
            className="ne-link text-sm"
            onClick={pedir}
            disabled={disabled || ocupado}
          >
            {ocupado ? "Generando sugerencia…" : `Sugerir para ${etiqueta}`}
          </button>
        </div>
        {error ? (
          <p role="alert" className="ne-notice ne-notice--danger">
            {error}
          </p>
        ) : null}
      </div>
    );
  }

  if (fase === "autorizando" && vista) {
    return (
      <div role="region" aria-label={`Autorización para sugerir ${etiqueta}`} className="ne-notice flex flex-col gap-3">
        <p>Se enviará este contenido a {vista.proveedor}. Revísalo antes de autorizarlo.</p>
        <details>
          <summary className="ne-link cursor-pointer">Ver el contenido exacto que se enviará</summary>
          <pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap text-sm">{vista.contenido}</pre>
        </details>
        <div className="flex flex-wrap gap-3">
          <button type="button" className="ne-button ne-button--primary" onClick={autorizar} disabled={ocupado}>
            Autorizar y generar
          </button>
          <button type="button" className="ne-button" onClick={cerrar} disabled={ocupado}>
            Cancelar
          </button>
        </div>
      </div>
    );
  }

  return (
    <div role="region" aria-label={`Sugerencia para ${etiqueta}`} className="ne-notice flex flex-col gap-3">
      <p className="ne-meta">
        {simulado ? "Sugerencia simulada, sin IA. " : ""}Revísala, edítala si hace falta y acéptala o descártala. Aceptarla
        solo la pone en el campo: no se guarda hasta que guardes el formulario.
      </p>
      <label className="flex flex-col gap-1">
        <span className="ne-label">Texto sugerido</span>
        <textarea
          rows={4}
          value={borrador}
          maxLength={4000}
          onChange={(event) => setBorrador(event.target.value)}
          className="ne-prose-field"
        />
      </label>
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          className="ne-button ne-button--primary"
          disabled={borrador.trim() === ""}
          onClick={() => {
            onAceptar(borrador.trim());
            cerrar();
          }}
        >
          Aceptar en el campo
        </button>
        <button type="button" className="ne-button" onClick={cerrar}>
          Descartar
        </button>
      </div>
    </div>
  );
}
