"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";
import { CollectionConfig, labelOf } from "@/lib/planning";
import { CanonBadge } from "./CanonBadge";
import { ElementEditor, type Item } from "./ElementEditor";
import { RelatedScenes } from "./RelatedScenes";
import { useUnsavedChanges } from "./UnsavedChanges";

type Props = { projectId: number; config: CollectionConfig };

/** Lista de un tipo de elemento con creación mínima (solo un nombre) y edición detallada. */
export function ElementCollection({ projectId, config }: Props) {
  const { isDirty } = useUnsavedChanges();
  const [items, setItems] = useState<Item[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [createValue, setCreateValue] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  // Elemento que llega desde otra sección con ?seleccionado=id. Puede estar archivado: entonces se muestra la lista con archivados.
  const requestedId = useRef<number | null>(null);

  useEffect(() => {
    const raw = new URLSearchParams(window.location.search).get("seleccionado");
    const id = raw === null ? NaN : Number(raw);
    if (Number.isInteger(id) && id > 0) {
      requestedId.current = id;
      setShowArchived(true);
    }
  }, []);

  const load = useCallback(async () => {
    setListError(null);
    try {
      const list = await api.listElements<Item>(projectId, config.route, showArchived);
      setItems(list);
      const target = requestedId.current;
      if (target !== null && list.some((item) => item.id === target)) {
        requestedId.current = null;
        setSelectedId(target);
      }
    } catch (reason) {
      setListError(reason instanceof ApiError ? reason.message : "No se pudo cargar la lista.");
    }
  }, [projectId, config.route, showArchived]);

  useEffect(() => {
    setItems(null);
    void load();
  }, [load]);

  const selected = items?.find((item) => item.id === selectedId) ?? null;

  function select(id: number) {
    if (id === selectedId) return;
    // Cambiar de elemento no puede descartar un texto que el autor todavía no ha guardado.
    if (selectedId !== null && isDirty(`${config.route}:${selectedId}`)) {
      if (!window.confirm("Hay cambios sin guardar en este elemento. ¿Descartarlos y abrir otro?")) return;
    }
    setNotice(null);
    setSelectedId(id);
  }

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = createValue.trim();
    if (!value) {
      setCreateError(`Escribe ${config.titleLabel === "Nombre" ? "un nombre" : "un título"} para crear el ${config.singular}.`);
      return;
    }
    setCreating(true);
    setCreateError(null);
    try {
      const created = await api.createElement<Item>(projectId, config.route, {
        ...config.createDefaults,
        [config.titleField]: value,
      });
      setCreateValue("");
      setNotice(`${capitalize(config.singular)} creado. Puedes completar el resto cuando quieras.`);
      setSelectedId(created.id);
      await load();
    } catch (reason) {
      // El texto escrito se conserva para corregirlo y volver a intentarlo.
      setCreateError(reason instanceof ApiError ? reason.message : `No se pudo crear el ${config.singular}.`);
    } finally {
      setCreating(false);
    }
  }

  function changed(message: string, kind?: "archived") {
    setNotice(message);
    if (kind === "archived") setSelectedId(null);
    void load();
  }

  const fields = config.fields;

  return (
    <div className="grid grid-cols-1 gap-8 md:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
      <div className="flex flex-col gap-5">
        <form onSubmit={create} className="flex flex-col gap-2" aria-label={`Crear ${config.singular}`}>
          <label htmlFor={`nuevo-${config.route}`} className="ne-label">
            {config.titleLabel} del nuevo {config.singular}
          </label>
          <div className="flex gap-2">
            <input
              id={`nuevo-${config.route}`}
              value={createValue}
              onChange={(event) => setCreateValue(event.target.value)}
              maxLength={200}
              className="min-w-0 flex-1"
            />
            <button type="submit" disabled={creating} className="ne-button ne-button--primary ne-button--small">
              {creating ? "Creando…" : `Crear ${config.singular}`}
            </button>
          </div>
          {createError ? (
            <p role="alert" className="ne-notice ne-notice--danger">
              {createError}
            </p>
          ) : null}
        </form>

        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={showArchived} onChange={(event) => setShowArchived(event.target.checked)} />
          Mostrar archivados
        </label>

        {items === null && !listError ? <p className="ne-meta">Cargando…</p> : null}
        {listError ? (
          <p role="alert" className="ne-notice ne-notice--danger">
            {listError}
          </p>
        ) : null}
        {items?.length === 0 ? <p className="ne-empty">{config.emptyText}</p> : null}

        <ul className="ne-list">
          {items?.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                onClick={() => select(item.id)}
                aria-current={item.id === selectedId ? "true" : undefined}
                className={`flex w-full flex-wrap items-center justify-between gap-2 py-3 text-left ${
                  item.id === selectedId ? "font-medium underline" : ""
                }`}
              >
                <span>
                  {labelOf(item, config.titleField)}
                </span>
                <span className="flex items-center gap-2">
                  {item.archived_at ? <span className="ne-hint">Archivado</span> : null}
                  <CanonBadge state={item.estado} origin={item.origen} />
                </span>
              </button>
            </li>
          ))}
        </ul>
        {notice ? (
          <p role="status" className="ne-notice ne-notice--ok">
            {notice}
          </p>
        ) : null}
      </div>

      <div className="min-w-0">
        {selected ? (
          <div className="flex flex-col gap-10">
            <ElementEditor
              key={selected.id}
              projectId={projectId}
              route={config.route}
              item={selected}
              fields={fields}
              itemLabel={labelOf(selected, config.titleField)}
              onChanged={changed}
            />
            <RelatedScenes projectId={projectId} route={config.route} elementId={selected.id} includeArchived={showArchived} />
          </div>
        ) : (
          <p className="ne-empty">Selecciona un elemento de la lista para verlo y editarlo.</p>
        )}
      </div>
    </div>
  );
}

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}
