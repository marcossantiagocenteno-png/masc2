/**
 * Cliente HTTP mínimo para el backend de Novel Engine.
 *
 * La URL base sale de NEXT_PUBLIC_API_BASE_URL (por defecto, localhost:8000).
 * Solo se contacta con esa URL; no hay servicios externos ni APIs de IA.
 */

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type ManuscriptSummary = {
  id: number;
  title: string;
  created_at: string;
  version_count: number;
  latest_version_number: number;
};

export type VersionSummary = {
  id: number;
  manuscript_id: number;
  number: number;
  sha256: string;
  char_count: number;
  note: string | null;
  parent_version_id: number | null;
  created_at: string;
};

export type VersionOut = VersionSummary & {
  content: string;
  review_count: number;
};

export type ReviewItemOut = {
  id: number;
  kind: string;
  quote: string;
  start_offset: number;
  end_offset: number;
  line_number: number;
  comment: string;
  inference_basis: string | null;
  suggestion: string | null;
  dimension: string | null;
  intent_status: string;
};

export type ReviewOut = {
  id: number;
  version_id: number;
  reviewer: string;
  created_at: string;
  items: ReviewItemOut[];
};

export type ReviewItemInput = {
  kind: "observacion" | "inferencia";
  quote: string;
  start_offset: number;
  end_offset: number;
  comment: string;
  inference_basis?: string;
  suggestion?: string;
};

export type AnalysisCategory =
  | "problema_verificable"
  | "observacion_literaria"
  | "inferencia_incierta"
  | "preferencia_de_gusto"
  | "elemento_a_preservar";

export type AnalysisFinding = {
  id: number;
  category: AnalysisCategory;
  provenance: "determinista" | "proveedor";
  source_name: string;
  quote: string;
  start_offset: number;
  end_offset: number;
  line_number: number;
  explanation: string;
  effect: string | null;
  certainty: "verificable" | "alta" | "media" | "baja" | "no_aplica";
  justification: string | null;
};

/** Estado del proveedor configurado. No contiene secretos. */
export type AnalysisProviderStatus = {
  configured: boolean;
  name: string | null;
  label: string | null;
  is_simulated: boolean | null;
  is_external: boolean | null;
  model_name: string | null;
  reason: string | null;
};

/** Autorización explícita de envío externo. Viaja en cada petición y no se guarda. */
export type ExternalAuthorization = {
  provider: string;
  scope: "fragmento_seleccionado";
  acknowledged: true;
};

export type AnalysisRun = {
  id: number;
  version_id: number;
  fragment_start: number;
  fragment_end: number;
  fragment_text: string;
  provider_name: string;
  provider_label: string;
  provider_simulated: boolean;
  model_name: string | null;
  sent_external: boolean;
  created_at: string;
  findings: AnalysisFinding[];
};

export type ProjectStatus = "activo" | "archivado";

export type Project = {
  id: number;
  name: string;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
};

export type ProjectDetail = Project & {
  manuscript_count: number;
  last_activity_at: string | null;
};

/** Borrador actual de un manuscrito. ``revision`` es la que debe enviarse en la próxima escritura. */
export type DraftOut = {
  manuscript_id: number;
  revision: number;
  content: string;
  char_count: number;
  sha256: string;
  base_version_id: number | null;
  created_at: string;
  updated_at: string;
};

export type DraftInitOut = { created: boolean; draft: DraftOut };

/** Escritura de una escena. ``sin_escritura``: no tiene manuscrito; ``sin_texto``: tiene manuscrito vacío; ``con_texto``: hay caracteres. */
export type SceneWritingState = "sin_escritura" | "sin_texto" | "con_texto";

export type SceneWriting = {
  node_id: number;
  manuscript_id: number | null;
  state: SceneWritingState;
  draft: DraftOut | null;
  versions_count: number;
};

export type DraftSaveBody = { content: string; base_revision: number; keep_previous: boolean };

export type RecoveryPointReason =
  | "periodico"
  | "significativo"
  | "conflicto"
  | "antes_de_restaurar"
  | "antes_de_sobrescribir";

export type RecoveryPointSummary = {
  id: number;
  manuscript_id: number;
  reason: RecoveryPointReason;
  char_count: number;
  sha256: string;
  draft_revision: number;
  created_at: string;
};

export type RecoveryPointOut = RecoveryPointSummary & { content: string };

export class ApiError extends Error {
  readonly status: number;
  /** Cuerpo JSON completo de la respuesta de error, si lo hubo (p. ej. datos de un conflicto 409). */
  readonly payload: Record<string, unknown> | null;

  constructor(message: string, status: number, payload: Record<string, unknown> | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(`No se pudo conectar con el backend en ${API_BASE_URL}.`, 0);
  }

  if (!response.ok) {
    let message = `Error HTTP ${response.status}.`;
    let payload: Record<string, unknown> | null = null;
    try {
      const body = (await response.json()) as Record<string, unknown>;
      payload = body;
      if (typeof body.detail === "string") {
        message = body.detail;
      } else if (Array.isArray(body.detail)) {
        // Errores de validación de FastAPI: lista de { loc, msg }.
        const messages = (body.detail as Array<{ msg?: unknown }>)
          .map((item) => (typeof item.msg === "string" ? item.msg : null))
          .filter((item): item is string => item !== null);
        if (messages.length > 0) message = messages.join(" ");
      }
    } catch {
      // El cuerpo no es JSON: se usa el mensaje genérico.
    }
    throw new ApiError(message, response.status, payload);
  }

  return (await response.json()) as T;
}

export const api = {
  listManuscripts: () => request<ManuscriptSummary[]>("/manuscripts"),

  getManuscript: (id: number) => request<ManuscriptSummary>(`/manuscripts/${id}`),

  createManuscript: (body: { title: string; content: string; note?: string }) =>
    request<ManuscriptSummary>("/manuscripts", { method: "POST", body: JSON.stringify(body) }),

  listVersions: (manuscriptId: number) =>
    request<VersionSummary[]>(`/manuscripts/${manuscriptId}/versions`),

  createVersion: (
    manuscriptId: number,
    body: { content: string; note?: string; based_on_version_id?: number },
  ) =>
    request<VersionOut>(`/manuscripts/${manuscriptId}/versions`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getVersion: (versionId: number) => request<VersionOut>(`/versions/${versionId}`),

  /** Devuelve el borrador existente o crea uno desde la última versión. Nunca sobrescribe. */
  initDraft: (manuscriptId: number) =>
    request<DraftInitOut>(`/manuscripts/${manuscriptId}/draft`, { method: "POST" }),

  saveDraft: (manuscriptId: number, body: DraftSaveBody) =>
    request<DraftOut>(`/manuscripts/${manuscriptId}/draft`, { method: "PUT", body: JSON.stringify(body) }),

  /**
   * Guardado de último recurso al cerrar la página (pagehide). Es best-effort: no hay
   * respuesta que leer ni reintento posible. ``keepalive`` permite que la petición
   * sobreviva a la descarga de la página.
   */
  saveDraftKeepalive: (manuscriptId: number, body: DraftSaveBody) => {
    void fetch(`${API_BASE_URL}/manuscripts/${manuscriptId}/draft`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      keepalive: true,
    }).catch(() => undefined);
  },

  listRecoveryPoints: (manuscriptId: number) =>
    request<RecoveryPointSummary[]>(`/manuscripts/${manuscriptId}/recovery-points`),

  restoreRecoveryPoint: (manuscriptId: number, pointId: number, baseRevision: number) =>
    request<DraftOut>(`/manuscripts/${manuscriptId}/recovery-points/${pointId}/restore`, {
      method: "POST",
      body: JSON.stringify({ base_revision: baseRevision }),
    }),

  listReviews: (versionId: number) => request<ReviewOut[]>(`/versions/${versionId}/reviews`),

  listAnalyses: (versionId: number) => request<AnalysisRun[]>(`/versions/${versionId}/analyses`),

  getAnalysisProvider: () => request<AnalysisProviderStatus>("/analysis/provider"),

  listProjects: (status: ProjectStatus | "todos" = "activo") =>
    request<Project[]>(`/projects?status_filter=${encodeURIComponent(status)}`),

  getProject: (id: number) => request<ProjectDetail>(`/projects/${id}`),

  createProject: (name: string) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify({ name }) }),

  renameProject: (id: number, name: string) =>
    request<Project>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify({ name }) }),

  archiveProject: (id: number) => request<Project>(`/projects/${id}/archive`, { method: "POST" }),

  restoreProject: (id: number) => request<Project>(`/projects/${id}/restore`, { method: "POST" }),

  listProjectManuscripts: (id: number) => request<ManuscriptSummary[]>(`/projects/${id}/manuscripts`),

  createProjectManuscript: (id: number, body: { title: string; content: string; note?: string }) =>
    request<ManuscriptSummary>(`/projects/${id}/manuscripts`, { method: "POST", body: JSON.stringify(body) }),

  analyzeFragment: (
    versionId: number,
    body: { start_offset: number; end_offset: number; external_authorization?: ExternalAuthorization },
  ) =>
    request<AnalysisRun>(`/versions/${versionId}/analyses`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  createReview: (versionId: number, body: { reviewer: string; items: ReviewItemInput[] }) =>
    request<ReviewOut>(`/versions/${versionId}/reviews`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  /* ---- Planificación ---- */

  getNarrative: (projectId: number) => request<NarrativeData>(`/projects/${projectId}/planificacion/narrativa`),

  updateNarrative: (projectId: number, body: Partial<Omit<NarrativeData, "id" | "name">>) =>
    request<NarrativeData>(`/projects/${projectId}/planificacion/narrativa`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  /** Lista de un tipo de elemento. Los archivados solo aparecen si se piden. */
  listElements: <T,>(projectId: number, route: string, includeArchived = false) =>
    request<T[]>(`/projects/${projectId}/planificacion/${route}?include_archived=${includeArchived}`),

  createElement: <T,>(projectId: number, route: string, body: Record<string, unknown>) =>
    request<T>(`/projects/${projectId}/planificacion/${route}`, { method: "POST", body: JSON.stringify(body) }),

  /** Edición. Si el elemento es canónico, la API exige ``confirmar`` (409 si falta). */
  updateElement: <T,>(projectId: number, route: string, id: number, body: Record<string, unknown>, confirmCanon = false) =>
    request<T>(
      `/projects/${projectId}/planificacion/${route}/${id}${confirmCanon ? "?confirmar_cambio_canon=true" : ""}`,
      { method: "PATCH", body: JSON.stringify(body) },
    ),

  archiveElement: <T,>(projectId: number, route: string, id: number, confirmCanon = false) =>
    request<T>(
      `/projects/${projectId}/planificacion/${route}/${id}/archivar${confirmCanon ? "?confirmar_canon=true" : ""}`,
      { method: "POST" },
    ),

  approveElement: <T,>(projectId: number, route: string, id: number, nota?: string) =>
    request<T>(`/projects/${projectId}/planificacion/${route}/${id}/aprobar`, {
      method: "POST",
      body: JSON.stringify({ confirmar: true, nota: nota || null }),
    }),

  /** Acepta una propuesta como material provisional. No la convierte en canon. Solo tipos con esta ruta en la API. */
  acceptElement: <T,>(projectId: number, route: string, id: number) =>
    request<T>(`/projects/${projectId}/planificacion/${route}/${id}/aceptar-propuesta`, { method: "POST" }),

  listDecisions: (projectId: number, route: string, id: number) =>
    request<NarrativeDecision[]>(`/projects/${projectId}/planificacion/${route}/${id}/decisiones`),

  listStructure: (projectId: number, includeArchived = true) =>
    request<StructureNode[]>(`/projects/${projectId}/planificacion/estructura?include_archived=${includeArchived}`),

  createStructureNode: (projectId: number, body: { kind: StructureKind; parent_id: number | null; title?: string }) =>
    request<StructureNode>(`/projects/${projectId}/planificacion/estructura`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  /** Reordena los hermanos de ``parentId``. ``orden`` debe incluir a todos, archivados incluidos. */
  reorderStructure: (projectId: number, parentId: number | null, orden: number[], confirmCanon = false) =>
    request<StructureNode[]>(`/projects/${projectId}/planificacion/estructura/reordenar`, {
      method: "POST",
      body: JSON.stringify({ parent_id: parentId, orden, confirmar_cambio_canon: confirmCanon }),
    }),

  /** Mueve un nodo a otro padre (o a la raíz) y, opcionalmente, a una posición entre sus hermanos. */
  moveNode: (
    projectId: number,
    nodeId: number,
    body: { parent_id: number | null; posicion?: number | null; confirmar_cambio_canon?: boolean },
  ) =>
    request<StructureNode>(`/projects/${projectId}/planificacion/estructura/${nodeId}/mover`, {
      method: "POST",
      body: JSON.stringify({ posicion: null, confirmar_cambio_canon: false, ...body }),
    }),

  /** Estado de la escritura de una escena y su borrador. Solo accesible dentro de su proyecto. */
  getSceneWriting: (projectId: number, nodeId: number) =>
    request<SceneWriting>(`/projects/${projectId}/planificacion/estructura/${nodeId}/escritura`),

  /** Inicia la escritura de una escena. Idempotente: si ya existe, devuelve la existente. */
  startSceneWriting: (projectId: number, nodeId: number) =>
    request<SceneWriting>(`/projects/${projectId}/planificacion/estructura/${nodeId}/escritura`, { method: "POST" }),

  saveSceneDraft: (projectId: number, nodeId: number, body: DraftSaveBody) =>
    request<DraftOut>(`/projects/${projectId}/planificacion/estructura/${nodeId}/escritura/borrador`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  /** Guardado de último recurso de una escena al cerrar la página. Mismo criterio que ``saveDraftKeepalive``. */
  saveSceneDraftKeepalive: (projectId: number, nodeId: number, body: DraftSaveBody) => {
    void fetch(`${API_BASE_URL}/projects/${projectId}/planificacion/estructura/${nodeId}/escritura/borrador`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      keepalive: true,
    }).catch(() => undefined);
  },

  /** Vínculos de un personaje, lugar, elemento de trama o acontecimiento (incluye los de escenas). */
  listElementLinks: (projectId: number, route: ElementRoute, id: number, includeArchived = false) =>
    request<NarrativeLink[]>(
      `/projects/${projectId}/planificacion/${route}/${id}/vinculos?include_archived=${includeArchived}`,
    ),

  listNodeLinks: (projectId: number, nodeId: number, includeArchived = false) =>
    request<NarrativeLink[]>(
      `/projects/${projectId}/planificacion/estructura/${nodeId}/vinculos?include_archived=${includeArchived}`,
    ),

  createLink: (
    projectId: number,
    body: { origen: { tipo: string; id: number }; destino: { tipo: string; id: number }; relacion: string },
  ) =>
    request<NarrativeLink>(`/projects/${projectId}/planificacion/vinculos`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  archiveLink: (projectId: number, linkId: number, confirmCanon = false) =>
    request<NarrativeLink>(
      `/projects/${projectId}/planificacion/vinculos/${linkId}/archivar${confirmCanon ? "?confirmar_canon=true" : ""}`,
      { method: "POST" },
    ),
};

/* ------------------------------------------------------------------
 * Planificación narrativa (fase 2a/2b). Los campos siguen la respuesta
 * de la API: cada elemento lleva su estado de canon y su origen.
 * ------------------------------------------------------------------ */

export type CanonState = "provisional" | "propuesta_ia" | "canonico";
export type ElementOrigin = "autor" | "ia";
export type PlotKind = "acontecimiento" | "conflicto" | "subtrama" | "misterio" | "pregunta_abierta";
export type StructureKind = "acto" | "capitulo" | "escena";
export type DevelopmentStatus = "idea" | "planificacion" | "escritura" | "revision" | "terminada";

export type CanonFields = {
  id: number;
  project_id: number;
  estado: CanonState;
  origen: ElementOrigin;
  approved_decision_id: number | null;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
};

export type Character = CanonFields & {
  name: string | null;
  description: string | null;
  goals: string | null;
  motivations: string | null;
  conflicts: string | null;
  evolution: string | null;
  notes: string | null;
};

export type Place = CanonFields & {
  name: string | null;
  description: string | null;
  features: string | null;
  notes: string | null;
};

export type PlotElement = CanonFields & {
  kind: PlotKind;
  title: string | null;
  description: string | null;
  notes: string | null;
};

export type TimelineEvent = CanonFields & {
  title: string | null;
  description: string | null;
  narrative_order: number | null;
  story_time: string | null;
  notes: string | null;
};

export type StructureNode = CanonFields & {
  parent_id: number | null;
  kind: StructureKind;
  position: number;
  title: string | null;
  summary: string | null;
  notes: string | null;
  /** Solo en escenas: estado de su escritura (migración 0009). */
  escritura?: SceneWritingState;
};

export type NarrativeLink = CanonFields & {
  source_kind: string;
  source_id: number;
  target_kind: string;
  target_id: number;
  relation: string;
};

export type NarrativeDecision = {
  id: number;
  project_id: number;
  element_kind: string;
  element_id: number;
  accion: string;
  actor: ElementOrigin;
  estado_previo: CanonState | null;
  estado_nuevo: CanonState | null;
  snapshot: string | null;
  resultado: string | null;
  nota: string | null;
  created_at: string;
};

export type NarrativeData = {
  id: number;
  name: string;
  premise: string | null;
  synopsis: string | null;
  genre: string | null;
  theme: string | null;
  tone: string | null;
  development_status: DevelopmentStatus | null;
};

/** Rutas de los tipos de elemento que comparten el mismo contrato CRUD y de canon. */
export type ElementRoute = "personajes" | "lugares" | "elementos-trama" | "acontecimientos";

export const DEVELOPMENT_STATUS_LABELS: Record<DevelopmentStatus, string> = {
  idea: "Idea",
  planificacion: "Planificación",
  escritura: "Escritura",
  revision: "Revisión",
  terminada: "Terminada",
};

/** Fecha legible en español, a partir del texto ISO que devuelve la API (UTC). */
export function formatDate(iso: string): string {
  const date = new Date(iso.endsWith("Z") ? iso : `${iso}Z`);
  return date.toLocaleString("es-ES", { dateStyle: "medium", timeStyle: "short" });
}
