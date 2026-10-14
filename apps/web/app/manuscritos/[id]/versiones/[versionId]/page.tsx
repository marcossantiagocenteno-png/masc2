"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  api,
  ApiError,
  formatDate,
  manuscriptOps,
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

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        // El manuscrito indica su proyecto; la versión se pide por la ruta acotada a ese proyecto.
        const manuscriptData = await api.getManuscript(manuscriptId);
        const ops = manuscriptOps(manuscriptData.project_id, manuscriptId);
        opsRef.current = ops;
        const [loaded, versionList, reviewList] = await Promise.all([
          ops.getVersion(versionId),
          ops.listVersions(),
          api.listReviews(versionId),
        ]);
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
      await api.createReview(version.id, { reviewer, items: [item] });
      setReviews(await api.listReviews(version.id));
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
        <p role="alert" className="text-red-700">
          {loadError}
        </p>
        <Link href={`/manuscritos/${manuscriptId}`} className="underline">
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
        <Link href={`/manuscritos/${manuscriptId}`} className="text-sm text-[var(--color-muted)] underline">
          Versiones de «{manuscript?.title ?? "…"}»
        </Link>
        <p className="text-sm uppercase tracking-widest text-[var(--color-muted)]">
          Manuscrito: {manuscript?.title ?? "…"}
        </p>
        <h1 className="text-3xl font-semibold">
          Versión {version?.number ?? "…"}
          {total ? <span className="text-xl font-normal text-[var(--color-muted)]"> de {total}</span> : null}
        </h1>
        {version ? (
          <p className="text-sm text-[var(--color-muted)]">
            Creada {formatDate(version.created_at)} · {version.char_count} caracteres · SHA-256 {version.sha256}
            {version.note ? ` · nota: ${version.note}` : ""}
          </p>
        ) : null}
      </header>

      <section aria-labelledby="contenido-titulo" className="flex flex-col gap-3">
        <h2 id="contenido-titulo" className="text-xl font-medium">
          Contenido de esta versión
        </h2>
        <p className="text-sm text-[var(--color-muted)]">Solo lectura. Este texto no cambia al añadir comentarios.</p>
        <textarea
          ref={contentRef}
          id="contenido-version"
          aria-label={`Contenido de la versión ${version?.number ?? ""}`}
          readOnly
          rows={14}
          value={version?.content ?? ""}
          className="rounded border border-[var(--color-muted)]/60 bg-transparent px-3 py-2 font-serif leading-relaxed"
        />
      </section>

      {version ? <AnalysisPanel versionId={version.id} readSelection={readContentSelection} /> : null}

      <section aria-labelledby="comentarios-titulo" className="flex flex-col gap-4">
        <h2 id="comentarios-titulo" className="text-xl font-medium">
          Comentarios vinculados a la versión {version?.number ?? "…"}{" "}
          <span className="text-base font-normal text-[var(--color-muted)]">({commentCount})</span>
        </h2>
        {reviews?.length === 0 ? (
          <p className="text-[var(--color-muted)]">Esta versión no tiene comentarios.</p>
        ) : null}
        {reviews?.map((review) => (
          <article key={review.id} className="flex flex-col gap-4 border-l-2 border-[var(--color-muted)]/50 pl-4">
            <p className="text-sm text-[var(--color-muted)]">
              {review.reviewer} · {formatDate(review.created_at)}
            </p>
            {review.items.map((item) => (
              <div key={item.id} className="flex flex-col gap-2">
                <p className="flex flex-wrap gap-2 text-sm">
                  <span className="rounded bg-[var(--color-muted)]/20 px-2 py-0.5 font-medium">
                    {item.kind === "inferencia" ? "Inferencia" : "Observación"}
                  </span>
                  <span className="text-[var(--color-muted)]">
                    Línea {item.line_number} · posiciones {item.start_offset}–{item.end_offset}
                  </span>
                </p>
                <blockquote className="whitespace-pre-wrap border-l-4 border-[var(--color-muted)]/60 pl-3 font-serif italic">
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
                <p className="text-xs text-[var(--color-muted)]">
                  Intención del autor: no declarada. Este comentario no atribuye intenciones.
                </p>
              </div>
            ))}
          </article>
        ))}
      </section>

      <section aria-labelledby="nuevo-titulo" className="flex flex-col gap-4">
        <h2 id="nuevo-titulo" className="text-xl font-medium">
          Añadir comentario a la versión {version?.number ?? "…"}
        </h2>
        <div className="flex flex-col gap-2">
          <button
            type="button"
            onClick={captureSelection}
            className="self-start rounded border border-[var(--color-ink)] px-4 py-2"
          >
            Usar la selección del contenido
          </button>
          {selection ? (
            <p className="text-sm">
              Cita seleccionada (posiciones {selection.start}–{selection.end}):{" "}
              <span className="whitespace-pre-wrap font-serif italic">«{selection.quote}»</span>
            </p>
          ) : (
            <p className="text-sm text-[var(--color-muted)]">Todavía no hay ninguna cita seleccionada.</p>
          )}
          {selectionError ? (
            <p role="alert" className="text-sm text-red-700">
              {selectionError}
            </p>
          ) : null}
        </div>

        <form onSubmit={handleSave} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium">Nombre de quien revisa</span>
            <input
              required
              maxLength={80}
              value={reviewer}
              onChange={(event) => setReviewer(event.target.value)}
              className="rounded border border-[var(--color-muted)] bg-transparent px-3 py-2"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium">Tipo de comentario</span>
            <select
              value={kind}
              onChange={(event) => setKind(event.target.value as "observacion" | "inferencia")}
              className="rounded border border-[var(--color-muted)] bg-transparent px-3 py-2"
            >
              <option value="observacion">Observación: lo que dice el texto</option>
              <option value="inferencia">Inferencia: una conclusión con su cadena</option>
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium">Comentario</span>
            <textarea
              required
              maxLength={4000}
              rows={3}
              value={comment}
              onChange={(event) => setComment(event.target.value)}
              className="rounded border border-[var(--color-muted)] bg-transparent px-3 py-2"
            />
          </label>
          {kind === "inferencia" ? (
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium">Cadena de inferencia (obligatoria)</span>
              <textarea
                required
                maxLength={4000}
                rows={3}
                value={inferenceBasis}
                onChange={(event) => setInferenceBasis(event.target.value)}
                className="rounded border border-[var(--color-muted)] bg-transparent px-3 py-2"
              />
            </label>
          ) : null}
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium">Sugerencia de revisión (opcional, no se aplica)</span>
            <textarea
              maxLength={4000}
              rows={2}
              value={suggestion}
              onChange={(event) => setSuggestion(event.target.value)}
              className="rounded border border-[var(--color-muted)] bg-transparent px-3 py-2"
            />
          </label>
          <div>
            <button
              type="submit"
              disabled={saving || !selection}
              className="rounded bg-[var(--color-ink)] px-4 py-2 text-[var(--color-paper)] disabled:opacity-50"
            >
              {saving ? "Guardando…" : "Guardar comentario"}
            </button>
          </div>
        </form>
        {saveError ? (
          <p role="alert" className="text-red-700">
            {saveError}
          </p>
        ) : null}
        {savedMessage ? <p role="status" className="text-green-800">{savedMessage}</p> : null}
      </section>
    </main>
  );
}
