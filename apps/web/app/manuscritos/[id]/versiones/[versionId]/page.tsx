"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  api,
  ApiError,
  formatDate,
  manuscriptOps,
  versionOps,
  type ManuscriptOps,
  type ManuscriptSummary,
  type ReviewItemInput,
  type ReviewOut,
  type VersionOut,
  type VersionSummary,
} from "@/lib/api";
import { AnalysisPanel, type ContentSelection } from "@/components/AnalysisPanel";

type Selection = ContentSelection;

/**
 * Una versión concreta: su contenido (solo lectura) y los comentarios vinculados a ella.
 *
 * Los comentarios se crean sobre una selección del contenido. La cita y su
 * posición se toman de ese mismo texto, que es exactamente el de la versión.
 */
export default function VersionPage() {
  const params = useParams<{ id: string; versionId: string }>();
  const manuscriptId = Number(params.id);
  const versionId = Number(params.versionId);

  const [manuscript, setManuscript] = useState<ManuscriptSummary | null>(null);
  const [version, setVersion] = useState<VersionOut | null>(null);
  const [versions, setVersions] = useState<VersionSummary[] | null>(null);
  const [reviews, setReviews] = useState<ReviewOut[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [selection, setSelection] = useState<Selection | null>(null);
  const [selectionError, setSelectionError] = useState<string | null>(null);
  const [kind, setKind] = useState<"observacion" | "inferencia">("observacion");
  const [reviewer, setReviewer] = useState("");
  const [comment, setComment] = useState("");
  const [inferenceBasis, setInferenceBasis] = useState("");
  const [suggestion, setSuggestion] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  const contentRef = useRef<HTMLTextAreaElement>(null);
  const opsRef = useRef<ManuscriptOps | null>(null);
  const [projectId, setProjectId] = useState<number | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        // El manuscrito indica su proyecto; la versión se pide por la ruta acotada a ese proyecto.
        const manuscriptData = await api.getManuscript(manuscriptId);
        const ops = manuscriptOps(manuscriptData.project_id, manuscriptId);
        opsRef.current = ops;
        setProjectId(manuscriptData.project_id);
        const [loaded, versionList] = await Promise.all([ops.getVersion(versionId), ops.listVersions()]);
        const reviewList = await versionOps(manuscriptData.project_id, manuscriptId, versionId).listReviews();
        if (!active) return;
        setVersion(loaded);
        setManuscript(manuscriptData);
        setVersions(versionList);
        setReviews(reviewList);
      } catch (reason) {
        if (active) setLoadError(reason instanceof Error ? reason.message : "Error desconocido.");
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [versionId]);

  /** Selección actual del contenido, o null si no hay ningún fragmento marcado. */
  function readContentSelection(): ContentSelection | null {
    const element = contentRef.current;
    if (!element || element.selectionStart === element.selectionEnd) return null;
    const { selectionStart, selectionEnd, value } = element;
    return { start: selectionStart, end: selectionEnd, quote: value.slice(selectionStart, selectionEnd) };
  }

  function captureSelection() {
    const element = contentRef.current;
    if (!element) return;
    const { selectionStart, selectionEnd, value } = element;
    if (selectionStart === selectionEnd) {
      setSelection(null);
      setSelectionError("Selecciona un fragmento del contenido antes de capturarlo.");
      return;
    }
    setSelectionError(null);
    setSelection({ start: selectionStart, end: selectionEnd, quote: value.slice(selectionStart, selectionEnd) });
  }

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selection || !version) return;
    setSaving(true);
    setSaveError(null);
    setSavedMessage(null);

    const item: ReviewItemInput = {
      kind,
      quote: selection.quote,
      start_offset: selection.start,
      end_offset: selection.end,
      comment,
      ...(kind === "inferencia" ? { inference_basis: inferenceBasis } : {}),
      ...(suggestion.trim() ? { suggestion } : {}),
    };

    try {
      const reviewOps = versionOps(projectId, manuscriptId, version.id);
      await reviewOps.createReview({ reviewer, items: [item] });
      setReviews(await reviewOps.listReviews());
      setVersion(await opsRef.current!.getVersion(version.id));
      setSelection(null);
      setComment("");
      setInferenceBasis("");
      setSuggestion("");
      setSavedMessage(`Comentario guardado en la versión ${version.number}.`);
    } catch (reason) {
      setSaveError(reason instanceof ApiError ? reason.message : "No se pudo guardar el comentario.");
    } finally {
      setSaving(false);
    }
  }

  if (loadError) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-12">
        <p role="alert" className="ne-notice ne-notice--danger">
          {loadError}
        </p>
        <Link href={`/manuscritos/${manuscriptId}`} className="ne-link">
          Volver al manuscrito
        </Link>
      </main>
    );
  }

  const total = versions?.length ?? 0;
  const commentCount = reviews?.reduce((sum, review) => sum + review.items.length, 0) ?? 0;

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-10 px-4 py-12 sm:px-6">
      <header className="flex flex-col gap-2">
        <Link href={`/manuscritos/${manuscriptId}`} className="ne-meta ne-link">
          Versiones de «{manuscript?.title ?? "…"}»
        </Link>
        <p className="ne-kicker">
          Manuscrito: {manuscript?.title ?? "…"}
        </p>
        <h1 className="ne-page-title">
          Versión {version?.number ?? "…"}
          {total ? <span className="ne-title-suffix"> de {total}</span> : null}
        </h1>
        {version ? (
          <p className="ne-meta">
            Creada {formatDate(version.created_at)} · {version.char_count} caracteres
            {version.note ? ` · nota: ${version.note}` : ""}
          </p>
        ) : null}
        {version ? (
          <p className="ne-hash">
            <span className="ne-meta">SHA-256 </span>
            <code>{version.sha256}</code>
          </p>
        ) : null}
      </header>

      <section aria-labelledby="contenido-titulo" className="flex flex-col gap-3">
        <h2 id="contenido-titulo" className="ne-section-title">
          Contenido de esta versión
        </h2>
        <p className="ne-meta">Solo lectura. Este texto no cambia al añadir comentarios.</p>
        <textarea
          ref={contentRef}
          id="contenido-version"
          aria-label={`Contenido de la versión ${version?.number ?? ""}`}
          readOnly
          rows={14}
          value={version?.content ?? ""}
          className="ne-prose-field"
        />
      </section>

      {version ? (
        <AnalysisPanel
          versionId={version.id}
          versionNumber={version.number}
          ops={versionOps(projectId, manuscriptId, version.id)}
          readSelection={readContentSelection}
        />
      ) : null}

      <section aria-labelledby="comentarios-titulo" className="flex flex-col gap-4">
        <h2 id="comentarios-titulo" className="ne-section-title">
          Comentarios vinculados a la versión {version?.number ?? "…"}{" "}
          <span className="ne-meta">({commentCount})</span>
        </h2>
        {reviews?.length === 0 ? (
          <p className="ne-empty">Esta versión no tiene comentarios.</p>
        ) : null}
        {reviews?.map((review) => (
          <article key={review.id} className="flex flex-col gap-4 border-l-2 border-[var(--color-line)] pl-4">
            <p className="ne-meta">
              {review.reviewer} · {formatDate(review.created_at)}
            </p>
            {review.items.map((item) => (
              <div key={item.id} className="flex flex-col gap-2">
                <p className="flex flex-wrap gap-2 text-sm">
                  <span className="ne-badge">
                    {item.kind === "inferencia" ? "Inferencia" : "Observación"}
                  </span>
                  <span className="ne-meta">
                    Línea {item.line_number} · posiciones {item.start_offset}–{item.end_offset}
                  </span>
                </p>
                <blockquote className="whitespace-pre-wrap border-l-4 border-[var(--color-accent)] pl-3 font-serif italic">
                  {item.quote}
                </blockquote>
                <p className="whitespace-pre-wrap">{item.comment}</p>
                {item.inference_basis ? (
                  <p className="whitespace-pre-wrap text-sm">
                    <span className="font-medium">Cadena de inferencia: </span>
                    {item.inference_basis}
                  </p>
                ) : null}
                {item.suggestion ? (
                  <p className="whitespace-pre-wrap text-sm">
                    <span className="font-medium">Sugerencia (no aplicada al texto): </span>
                    {item.suggestion}
                  </p>
                ) : null}
                <p className="ne-hint">
                  Intención del autor: no declarada. Este comentario no atribuye intenciones.
                </p>
              </div>
            ))}
          </article>
        ))}
      </section>

      <section aria-labelledby="nuevo-titulo" className="flex flex-col gap-4">
        <h2 id="nuevo-titulo" className="ne-section-title">
          Añadir comentario a la versión {version?.number ?? "…"}
        </h2>
        <div className="flex flex-col gap-2">
          <button
            type="button"
            onClick={captureSelection}
            className="self-start ne-button"
          >
            Usar la selección del contenido
          </button>
          {selection ? (
            <p className="text-sm">
              Cita seleccionada (posiciones {selection.start}–{selection.end}):{" "}
              <span className="whitespace-pre-wrap font-serif italic">«{selection.quote}»</span>
            </p>
          ) : (
            <p className="ne-meta">Todavía no hay ninguna cita seleccionada.</p>
          )}
          {selectionError ? (
            <p role="alert" className="ne-notice ne-notice--danger">
              {selectionError}
            </p>
          ) : null}
        </div>

        <form onSubmit={handleSave} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1">
            <span className="ne-label">Nombre de quien revisa</span>
            <input
              required
              maxLength={80}
              value={reviewer}
              onChange={(event) => setReviewer(event.target.value)}
              
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="ne-label">Tipo de comentario</span>
            <select
              value={kind}
              onChange={(event) => setKind(event.target.value as "observacion" | "inferencia")}
              
            >
              <option value="observacion">Observación: lo que dice el texto</option>
              <option value="inferencia">Inferencia: una conclusión con su cadena</option>
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="ne-label">Comentario</span>
            <textarea
              required
              maxLength={4000}
              rows={3}
              value={comment}
              onChange={(event) => setComment(event.target.value)}
              
            />
          </label>
          {kind === "inferencia" ? (
            <label className="flex flex-col gap-1">
              <span className="ne-label">Cadena de inferencia (obligatoria)</span>
              <textarea
                required
                maxLength={4000}
                rows={3}
                value={inferenceBasis}
                onChange={(event) => setInferenceBasis(event.target.value)}
                
              />
            </label>
          ) : null}
          <label className="flex flex-col gap-1">
            <span className="ne-label">Sugerencia de revisión (opcional, no se aplica)</span>
            <textarea
              maxLength={4000}
              rows={2}
              value={suggestion}
              onChange={(event) => setSuggestion(event.target.value)}
              
            />
          </label>
          <div>
            <button
              type="submit"
              disabled={saving || !selection}
              className="ne-button ne-button--primary"
            >
              {saving ? "Guardando…" : "Guardar comentario"}
            </button>
          </div>
        </form>
        {saveError ? (
          <p role="alert" className="ne-notice ne-notice--danger">
            {saveError}
          </p>
        ) : null}
        {savedMessage ? <p role="status" className="ne-notice ne-notice--ok">{savedMessage}</p> : null}
      </section>
    </main>
  );
}
