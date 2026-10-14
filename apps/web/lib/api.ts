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

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
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
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") {
        message = body.detail;
      }
    } catch {
      // El cuerpo no es JSON: se usa el mensaje genérico.
    }
    throw new ApiError(message, response.status);
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
};

/** Fecha legible en español, a partir del texto ISO que devuelve la API (UTC). */
export function formatDate(iso: string): string {
  const date = new Date(iso.endsWith("Z") ? iso : `${iso}Z`);
  return date.toLocaleString("es-ES", { dateStyle: "medium", timeStyle: "short" });
}
