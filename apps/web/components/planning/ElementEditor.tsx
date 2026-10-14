"use client";

import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError, formatDate, type CanonFields, type NarrativeDecision } from "@/lib/api";
import { CANON_HELP, CANON_LABELS, type FieldDef } from "@/lib/planning";
import { CanonBadge } from "./CanonBadge";
import { ConfirmPanel } from "./ConfirmPanel";
import { useDirty } from "./UnsavedChanges";

export type Item = CanonFields & Record<string, unknown>;

type Props = {
  projectId: number;
  route: string;
  item: Item;
  fields: FieldDef[];
  /** Nombre del tipo para los mensajes («personaje», «escena»…). */
  itemLabel: string;
  /** Se llama tras un cambio confirmado por el servidor. ``archived`` indica que el elemento ya no está activo. */
  onChanged: (message: string, changed?: "archived") => void;
};

const DECISION_TEXT: Record<string, string> = {
  aprobar_canon: "Aprobado como canon",
  modificar_canon: "Cambiado tras la aprobación (con confirmación)",
  archivar: "Archivado",
  aceptar_propuesta: "Propuesta aceptada como provisional",
};

function valuesOf(item: Item, fields: FieldDef[]): Record<string, string> {
  const values: Record<string, string> = {};
  for (const field of fields) {
    const value = item[field.name];
    values[field.name] = value === null || value === undefined ? "" : String(value);
  }
  return values;
}

/** Solo los campos que han cambiado. Un campo vacío se envía como nulo: «no informado». */
function changedBody(values: Record<string, string>, baseline: Record<string, string>, fields: FieldDef[]) {
  const body: Record<string, unknown> = {};
  for (const field of fields) {
    if (values[field.name] === baseline[field.name]) continue;
    const raw = values[field.name].trim();
    if (field.type === "number") body[field.name] = raw === "" ? null : Number(raw);
    else body[field.name] = raw === "" ? null : values[field.name];
  }
  return body;
}

/** Edición de un elemento con sus acciones de canon. Mantiene el texto escrito si una operación falla. */
export function ElementEditor({ projectId, route, item, fields, itemLabel, onChanged }: Props) {
  const [values, setValues] = useState(() => valuesOf(item, fields));
  const [baseline, setBaseline] = useState(() => valuesOf(item, fields));
  const [canonConfirmed, setCanonConfirmed] = useState(false);
  const [panel, setPanel] = useState<null | "approve" | "accept" | "archive">(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [decisions, setDecisions] = useState<NarrativeDecision[] | null>(null);
  const [decisionsError, setDecisionsError] = useState<string | null>(null);

  const archived = item.archived_at !== null;
  const isCanon = item.estado === "canonico";
  const dirty = fields.some((field) => values[field.name] !== baseline[field.name]);
  const canSave = dirty && !busy && (!isCanon || canonConfirmed);
  useDirty(`${route}:${item.id}`, dirty && !archived);

  // Un elemento recargado (tras un cambio confirmado) reemplaza la base de comparación.
  useEffect(() => {
    const fresh = valuesOf(item, fields);
    setValues(fresh);
    setBaseline(fresh);
    setCanonConfirmed(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [item.updated_at, item.id]);

  useEffect(() => {
    let active = true;
    setDecisionsError(null);
    api
      .listDecisions(projectId, route, item.id)
      .then((list) => active && setDecisions(list))
      .catch((reason: unknown) => {
        if (!active) return;
        setDecisions([]);
        setDecisionsError(reason instanceof ApiError ? reason.message : "No se pudo cargar el historial de decisiones.");
      });
    return () => {
      active = false;
    };
  }, [projectId, route, item.id, item.updated_at]);

  function fail(reason: unknown, fallback: string) {
    setError(reason instanceof ApiError ? reason.message : fallback);
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSave) return;
    const body = changedBody(values, baseline, fields);
    if (Object.keys(body).length === 0) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await api.updateElement<Item>(projectId, route, item.id, body, isCanon);
      const fresh = valuesOf(updated, fields);
      setValues(fresh);
      setBaseline(fresh);
      setCanonConfirmed(false);
      const message = isCanon
        ? "Cambio guardado. El elemento vuelve a provisional y se ha registrado una decisión de canon."
        : "Cambios guardados.";
      // El aviso lo muestra el componente padre, que recibe el mensaje en onChanged.
      onChanged(message);
    } catch (reason) {
      // Los valores escritos se conservan: el formulario no se reinicia.
      fail(reason, "No se pudo guardar. Tus cambios siguen en el formulario.");
    } finally {
      setBusy(false);
    }
  }

  async function runCanonAction(kind: "approve" | "accept" | "archive") {
    setBusy(true);
    setError(null);
    try {
      if (kind === "approve") {
        await api.approveElement(projectId, route, item.id);
        setPanel(null);
        onChanged("Aprobado como canon. Se ha registrado una decisión de canon.");
      } else if (kind === "accept") {
        await api.acceptElement(projectId, route, item.id);
        setPanel(null);
        onChanged("Propuesta aceptada como material provisional. No es canon.");
      } else {
        await api.archiveElement(projectId, route, item.id, isCanon);
        setPanel(null);
        onChanged(`«${itemLabel}» archivado. No se ha borrado: puedes verlo activando «Mostrar archivados».`, "archived");
      }
    } catch (reason) {
      // El panel sigue abierto y el formulario no cambia.
      fail(reason, "No se pudo completar la acción.");
    } finally {
      setBusy(false);
    }
  }

  const canApprove = !archived && item.estado !== "canonico";
  const canAccept = !archived && item.estado === "propuesta_ia" && route !== "estructura";

  return (
    <section aria-label={`Editar ${itemLabel}`} className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-2">
        <CanonBadge state={item.estado} origin={item.origen} />
        {archived ? <span className="ne-badge">Archivado</span> : null}
        <span className="ne-meta">{CANON_HELP[item.estado]}</span>
      </div>

      {archived ? (
        <p className="ne-meta">
          Archivado el {formatDate(item.archived_at as string)}. No se puede editar; no se ha borrado nada.
        </p>
      ) : null}

      {isCanon && !archived ? (
        <div className="ne-notice ne-notice--warn flex-col gap-2">
          <p>
            Este elemento es <strong>{CANON_LABELS.canonico.toLowerCase()}</strong>. Guardar un cambio lo devolverá a
            provisional y quedará registrado como decisión de canon, con el texto anterior.
          </p>
          <label className="flex items-start gap-2">
            <input type="checkbox" checked={canonConfirmed} onChange={(event) => setCanonConfirmed(event.target.checked)} />
            <span>Confirmo el cambio al canon</span>
          </label>
        </div>
      ) : null}

      <form onSubmit={save} className="flex flex-col gap-4">
        {fields.map((field) => {
          const id = `${route}-${item.id}-${field.name}`;
          const common = {
            id,
            value: values[field.name],
            disabled: archived || busy,
            onChange: (event: { target: { value: string } }) =>
              setValues((current) => ({ ...current, [field.name]: event.target.value })),
          };
          return (
            <div key={field.name} className="flex flex-col gap-1">
              <label htmlFor={id} className="ne-label">
                {field.label}
              </label>
              {field.options ? (
                <select {...common}>
                  {field.options.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              ) : field.multiline ? (
                <textarea {...common} rows={3} />
              ) : (
                <input {...common} type={field.type === "number" ? "number" : "text"} min={field.type === "number" ? 0 : undefined} />
              )}
              {field.hint ? <span className="ne-hint">{field.hint}</span> : null}
            </div>
          );
        })}
        {!archived ? (
          <div className="flex flex-wrap items-center gap-3">
            <button type="submit" disabled={!canSave} className="ne-button ne-button--primary">
              {busy ? "Guardando…" : "Guardar cambios"}
            </button>
            {dirty ? <span className="ne-meta">Hay cambios sin guardar.</span> : null}
            {isCanon && !canonConfirmed && dirty ? (
              <span className="ne-meta">Confirma el cambio al canon para poder guardar.</span>
            ) : null}
          </div>
        ) : null}
      </form>

      {error ? (
        <p role="alert" className="ne-notice ne-notice--danger">
          {error}
        </p>
      ) : null}

      {!archived ? (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap gap-2">
            {canApprove ? (
              <button type="button" onClick={() => setPanel("approve")} disabled={busy} className="ne-button ne-button--small">
                Aprobar como canon
              </button>
            ) : null}
            {canAccept ? (
              <button type="button" onClick={() => setPanel("accept")} disabled={busy} className="ne-button ne-button--small">
                Aceptar propuesta
              </button>
            ) : null}
            <button type="button" onClick={() => setPanel("archive")} disabled={busy} className="ne-button ne-button--small">
              Archivar
            </button>
          </div>
          {panel === "approve" ? (
            <ConfirmPanel
              message={
                <>
                  Al aprobarlo, <strong>{itemLabel}</strong> pasa a canónico. Cambiarlo después exigirá confirmación y
                  quedará registrado en una decisión de canon.
                </>
              }
              confirmLabel="Aprobar como canon"
              checkboxLabel="Confirmo que este dato es canónico"
              busy={busy}
              onConfirm={() => void runCanonAction("approve")}
              onCancel={() => setPanel(null)}
            />
          ) : null}
          {panel === "accept" ? (
            <ConfirmPanel
              message="Pasará a material provisional. No se convierte en canon."
              confirmLabel="Aceptar como provisional"
              busy={busy}
              onConfirm={() => void runCanonAction("accept")}
              onCancel={() => setPanel(null)}
            />
          ) : null}
          {panel === "archive" ? (
            <ConfirmPanel
              message={
                isCanon ? (
                  <>
                    Archivar <strong>{itemLabel}</strong> es un cambio de canon: quedará registrado. No se borra nada.
                  </>
                ) : (
                  <>
                    Archivar <strong>{itemLabel}</strong>. No se borra: puedes verlo activando «Mostrar archivados».
                  </>
                )
              }
              confirmLabel="Archivar"
              checkboxLabel={isCanon ? "Confirmo el archivado de un elemento canónico" : undefined}
              busy={busy}
              onConfirm={() => void runCanonAction("archive")}
              onCancel={() => setPanel(null)}
            />
          ) : null}
        </div>
      ) : null}

      <div className="flex flex-col gap-2 border-t border-[var(--color-line)] pt-4 text-sm">
        <h3 className="font-medium">Historial de canon</h3>
        {decisions === null ? <p className="ne-meta">Cargando…</p> : null}
        {decisionsError ? (
          <p role="alert" className="ne-notice ne-notice--danger">
            {decisionsError}
          </p>
        ) : null}
        {decisions?.length === 0 && !decisionsError ? (
          <p className="ne-meta">Sin decisiones de canon. Las ediciones de material provisional no se registran.</p>
        ) : null}
        <ol className="flex flex-col gap-1">
          {decisions?.map((decision) => (
            <li key={decision.id} className="ne-meta">
              {formatDate(decision.created_at)} · {DECISION_TEXT[decision.accion] ?? decision.accion}
              {decision.estado_previo && decision.estado_nuevo
                ? ` (${CANON_LABELS[decision.estado_previo]} → ${CANON_LABELS[decision.estado_nuevo]})`
                : ""}
              {decision.actor === "autor" ? " · por el autor" : ""}
            </li>
          ))}
        </ol>
        <p className="ne-hint">
          El historial solo muestra qué ocurrió. Restaurar versiones anteriores no está disponible todavía.
        </p>
      </div>
    </section>
  );
}
