const API_URL = process.env.NEXT_PUBLIC_API_URL?.trim().replace(/\/$/, "") || "";

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_URL}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export async function apiUpload<T>(
  path: string,
  formData: FormData,
): Promise<T> {
  const url = `${API_URL}${path}`;
  const res = await fetch(url, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `Upload error: ${res.status}`);
  }
  return res.json();
}

export async function apiStream(
  path: string,
  body: object,
  onChunk: (text: string) => void,
  onDone?: () => void
) {
  const url = `${API_URL}${path}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API error: ${res.status}`);
  }

  const reader = res.body?.getReader();
  const decoder = new TextDecoder();

  if (!reader) return;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split("\n");

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const data = line.slice(6);
        if (data === "[DONE]") {
          onDone?.();
          return;
        }
        onChunk(data);
      }
    }
  }
  onDone?.();
}

// API Types
export interface Patent {
  id: string;
  application_number: string;
  patent_number: string | null;
  title: string;
  abstract: string | null;
  status: string;
  filing_date: string | null;
  grant_date: string | null;
  priority_date: string | null;
  inventors: Array<{ first_name: string; last_name: string }>;
  assignee: string | null;
  classification: Record<string, string>;
  firm_id: string;
  family_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface PatentListResponse {
  patents: Patent[];
  total: number;
  page: number;
  page_size: number;
}

export interface PortfolioOverview {
  total_patents: number;
  status_breakdown: Record<string, number>;
  patent_families: number;
  urgent_deadlines: number;
  deadline_window_days: number;
}

export interface PatentFamily {
  id: string;
  family_name: string;
  family_external_id: string | null;
  description: string | null;
  firm_id: string;
  created_at: string;
  patents: Patent[];
}

export interface OfficeAction {
  id: string;
  patent_id: string;
  action_type: string;
  mailing_date: string | null;
  response_deadline: string | null;
  status: string;
  r2_file_key: string | null;
  extracted_text: string | null;
  rejections: Array<{
    type: string;
    claims: number[];
    references: string[];
    basis?: string;
  }>;
  created_at: string;
}

export interface Draft {
  id: string;
  title: string;
  content: string;
  draft_type: string;
  patent_id: string | null;
  firm_id: string;
  created_by: string;
  ai_model_used: string | null;
  version: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface SearchResult {
  patent_id: string;
  title: string;
  application_number: string;
  score: number;
  matched_text: string;
  status: string;
}

export interface ExternalPatent {
  patent_number: string;
  title: string;
  abstract: string;
  date: string;
  type: string;
  num_claims: number;
  assignee?: string;
  source?: string;
}

export interface PatentDetail {
  patent_number: string;
  title: string;
  abstract: string;
  grant_date: string;
  type: string;
  num_claims: number;
  claims: Array<{ number: number; text: string; is_independent: boolean }>;
  inventors: Array<{ first_name: string; last_name: string }>;
  assignee: string;
  source: string;
}

export interface PatentSummary {
  core_invention: string;
  technical_field?: string;
  independent_claims_count?: number;
  dependent_claims_count?: number;
  claims_breakdown?: Array<{
    claim_number: number;
    type: string;
    summary: string;
    key_elements: string[];
    breadth: string;
  }>;
  weaknesses?: Array<{
    claim_number: number;
    issue: string;
    severity: string;
    exploitation_angle: string;
  }>;
  strongest_claim?: { claim_number: number; reason: string };
  prior_art_vulnerability?: string;
  overall_quality_score?: number;
  parse_error?: boolean;
}

export interface ZipUploadResponse {
  message: string;
  patents: Patent[];
}

export interface OfficeActionUploadResponse {
  message: string;
  office_action_id: string;
  rejections_found: number;
  rejections: OfficeAction['rejections'];
}

export interface PatentUploadResponse {
  message: string;
  text_length: number;
  chunks: number;
  embeddings_stored?: number;
  summary: PatentSummary;
}

// API Functions
export const api = {
  // Patents
  listPatents: (page = 1, search?: string) =>
    apiFetch<PatentListResponse>(
      `/api/v1/patents/?page=${page}${search ? `&search=${encodeURIComponent(search)}` : ""}`
    ),
  getPatent: (id: string) => apiFetch<Patent>(`/api/v1/patents/${id}`),
  getClaims: (patentId: string) =>
    apiFetch<Array<{ id: string; claim_number: number; claim_text: string; is_independent: boolean }>>(
      `/api/v1/patents/${patentId}/claims`
    ),

  // Portfolio
  getOverview: () => apiFetch<PortfolioOverview>("/api/v1/portfolio/overview"),
  listFamilies: () => apiFetch<PatentFamily[]>("/api/v1/portfolio/families"),

  // Office Actions
  listOfficeActions: () => apiFetch<OfficeAction[]>("/api/v1/office-actions/"),

  // Drafts
  listDrafts: () => apiFetch<Draft[]>("/api/v1/drafting/"),

  // Local Search
  searchPatents: (query: string, type = "hybrid", topK = 20) =>
    apiFetch<{ results: SearchResult[]; query: string; total: number }>(
      "/api/v1/search/",
      {
        method: "POST",
        body: JSON.stringify({ query, search_type: type, top_k: topK }),
      }
    ),

  // External USPTO Search
  searchUSPTO: (query: string, assignee?: string, patentNumber?: string) =>
    apiFetch<{ patents: ExternalPatent[]; total: number }>(
      "/api/v1/search/external",
      {
        method: "POST",
        body: JSON.stringify({ query, assignee, patent_number: patentNumber, max_results: 25 }),
      }
    ),

  getExternalPatentDetail: (patentNumber: string) =>
    apiFetch<PatentDetail>(`/api/v1/search/external/${encodeURIComponent(patentNumber)}/detail`),

  importPatent: (patentNumber: string) =>
    apiFetch<{ message: string; patent_id: string; title: string; claims_imported: number }>(
      "/api/v1/search/import",
      { method: "POST", body: JSON.stringify({ patent_number: patentNumber }) }
    ),

  // Google Patents (International)
  searchGooglePatents: (query: string, assignee?: string, country?: string) =>
    apiFetch<{ patents: ExternalPatent[]; total: number }>(
      "/api/v1/search/google-patents",
      {
        method: "POST",
        body: JSON.stringify({ query, assignee, country, max_results: 20 }),
      }
    ),

  // Documents
  uploadZip: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiUpload<ZipUploadResponse>(
      "/api/v1/documents/upload-zip",
      formData
    );
  },

  uploadPatentPDF: (patentId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("patent_id", patentId);
    return apiUpload<PatentUploadResponse>(
      "/api/v1/documents/upload-patent",
      formData
    );
  },

  uploadOfficeActionPDF: (patentId: string, file: File, actionType = "Non-Final Rejection") => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("patent_id", patentId);
    formData.append("action_type", actionType);
    return apiUpload<OfficeActionUploadResponse>(
      "/api/v1/documents/upload-office-action",
      formData
    );
  },

  uploadSpec: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiUpload<{ message: string; text_length: number; extracted_text: string }>(
      "/api/v1/documents/upload-spec",
      formData
    );
  },

  getPatentSummary: (patentId: string) =>
    apiFetch<{ patent_id: string; title: string; summary: PatentSummary }>(
      `/api/v1/documents/${patentId}/summary`
    ),

  getDocumentViewUrl: (patentId: string) =>
    apiFetch<{ url: string; expires_in: number }>(
      `/api/v1/documents/${patentId}/view-url`
    ),

  // AI Streaming
  generateDraft: (body: object, onChunk: (t: string) => void, onDone?: () => void) =>
    apiStream("/api/v1/drafting/generate", body, onChunk, onDone),

  generateOAResponse: (oaId: string, body: object, onChunk: (t: string) => void, onDone?: () => void) =>
    apiStream(`/api/v1/office-actions/${oaId}/generate-response`, body, onChunk, onDone),

  runRiskAnalysis: (body: object, onChunk: (t: string) => void, onDone?: () => void) =>
    apiStream("/api/v1/prior-art/risk-analysis", body, onChunk, onDone),

  runPriorArtAnalysis: (body: object, onChunk: (t: string) => void, onDone?: () => void) =>
    apiStream("/api/v1/prior-art/analyze", body, onChunk, onDone),

  generateDueDiligence: (body: object, onChunk: (t: string) => void, onDone?: () => void) =>
    apiStream("/api/v1/prior-art/due-diligence", body, onChunk, onDone),
};
