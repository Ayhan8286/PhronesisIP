const API_URL = process.env.NEXT_PUBLIC_API_URL?.trim().replace(/\/$/, "") || "";

export async function apiFetch<T>(
  path: string,
  options: RequestInit & { token?: string } = {}
): Promise<T> {
  const { token, ...fetchOptions } = options;
  const url = `${API_URL}${path}`;
  const res = await fetch(url, {
    ...fetchOptions,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...fetchOptions.headers,
    },
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = error.detail ?? error.message ?? res.statusText;
    const message = typeof detail === "string" ? detail : JSON.stringify(detail);
    throw new Error(message || `API error: ${res.status}`);
  }
  return res.json();
}

export async function apiUpload<T>(
  path: string,
  formData: FormData,
  token?: string
): Promise<T> {
  const url = `${API_URL}${path}`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
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
  onDone?: () => void,
  token?: string,
  onSources?: (data: any) => void,
) {
  const url = `${API_URL}${path}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { 
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
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
        // Handle [SOURCES] metadata event from strict RAG pipeline
        if (data.startsWith("[SOURCES]")) {
          try {
            const sourcesData = JSON.parse(data.slice(9));
            onSources?.(sourcesData);
          } catch {
            // If parse fails, treat as regular chunk
            onChunk(data);
          }
          continue;
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
  draft_metadata?: {
    validation?: {
      is_valid: boolean;
      issues: Array<{
        level: "ERROR" | "WARNING";
        message: string;
        rejection_statute: string;
        suggestion: string;
      }>;
    };
    expert_applied?: boolean;
    model?: string;
  };
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

// API Logic
export const createApi = (token?: string) => ({
  // Patents
  listPatents: (page = 1, search?: string) =>
    apiFetch<PatentListResponse>(
      `/api/v1/patents/?page=${page}${search ? `&search=${encodeURIComponent(search)}` : ""}`,
      { token }
    ),
  getPatent: (id: string) => 
    apiFetch<Patent>(`/api/v1/patents/${id}`, { token }),
  getClaims: (patentId: string) =>
    apiFetch<Array<{ id: string; claim_number: number; claim_text: string; is_independent: boolean }>>(
      `/api/v1/patents/${patentId}/claims`,
      { token }
    ),

  // Portfolio
  getOverview: () => apiFetch<PortfolioOverview>("/api/v1/portfolio/overview", { token }),
  listFamilies: () => apiFetch<PatentFamily[]>("/api/v1/portfolio/families", { token }),

  // Drafts
  listDrafts: () => apiFetch<Draft[]>("/api/v1/drafting/", { token }),
  getDraft: (id: string) => apiFetch<Draft>(`/api/v1/drafting/${id}`, { token }),

  // Office Actions
  listOfficeActions: () => apiFetch<OfficeAction[]>("/api/v1/office-actions/", { token }),
  getOAResponseDraft: (oaId: string, draftId: string) => 
    apiFetch<Draft>(`/api/v1/office-actions/${oaId}/drafts/${draftId}`, { token }),

  // Local Search
  searchPatents: (query: string, type = "hybrid", topK = 20) =>
    apiFetch<{ results: SearchResult[]; query: string; total: number }>(
      "/api/v1/search/",
      {
        method: "POST",
        body: JSON.stringify({ query, search_type: type, top_k: topK }),
        token,
      }
    ),

  // External USPTO Search
  searchUSPTO: (query: string, assignee?: string, patentNumber?: string) =>
    apiFetch<{ patents: ExternalPatent[]; total: number }>(
      "/api/v1/search/external",
      {
        method: "POST",
        body: JSON.stringify({ query, assignee, patent_number: patentNumber, max_results: 25 }),
        token,
      }
    ),

  getExternalPatentDetail: (patentNumber: string) =>
    apiFetch<PatentDetail>(`/api/v1/search/external/${encodeURIComponent(patentNumber)}/detail`, { token }),

  importPatent: (patentNumber: string) =>
    apiFetch<{ message: string; patent_id: string; title: string; claims_imported: number }>(
      "/api/v1/search/import",
      { method: "POST", body: JSON.stringify({ patent_number: patentNumber }), token }
    ),

  // Google Patents (International)
  searchGooglePatents: (query: string, assignee?: string, country?: string) =>
    apiFetch<{ patents: ExternalPatent[]; total: number }>(
      "/api/v1/search/google-patents",
      {
        method: "POST",
        body: JSON.stringify({ query, assignee, country, max_results: 20 }),
        token,
      }
    ),

  // Documents
  uploadZip: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiUpload<ZipUploadResponse>(
      "/api/v1/documents/upload-zip",
      formData,
      token
    );
  },

  uploadPatentPDF: (patentId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("patent_id", patentId);
    return apiUpload<PatentUploadResponse>(
      "/api/v1/documents/upload-patent",
      formData,
      token
    );
  },

  uploadOfficeActionPDF: (patentId: string, file: File, actionType = "Non-Final Rejection") => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("patent_id", patentId);
    formData.append("action_type", actionType);
    return apiUpload<OfficeActionUploadResponse>(
      "/api/v1/documents/upload-office-action",
      formData,
      token
    );
  },

  uploadSpec: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiUpload<{ message: string; text_length: number; extracted_text: string }>(
      "/api/v1/documents/upload-spec",
      formData,
      token
    );
  },

  getPatentSummary: (patentId: string) =>
    apiFetch<{ patent_id: string; title: string; summary: PatentSummary }>(
      `/api/v1/documents/${patentId}/summary`,
      { token }
    ),

  getDocumentViewUrl: (patentId: string) =>
    apiFetch<{ url: string; expires_in: number }>(
      `/api/v1/documents/${patentId}/view-url`,
      { token }
    ),

  // AI Jobs (Async)
  generateDraft: (body: object) =>
    apiFetch<Draft>("/api/v1/drafting/generate", {
      method: "POST",
      body: JSON.stringify(body),
      token,
    }),

  generateOAResponse: (oaId: string, body: object) =>
    apiFetch<Draft>(`/api/v1/office-actions/${oaId}/generate-response`, {
      method: "POST",
      body: JSON.stringify(body),
      token,
    }),

  runRiskAnalysis: (body: object, onChunk: (t: string) => void, onDone?: () => void, onSources?: (data: any) => void) =>
    apiStream("/api/v1/prior-art/risk-analysis", body, onChunk, onDone, token, onSources),

  runPriorArtAnalysis: (body: object, onChunk: (t: string) => void, onDone?: () => void, onSources?: (data: any) => void) =>
    apiStream("/api/v1/prior-art/analyze", body, onChunk, onDone, token, onSources),

  generateDueDiligence: (body: object, onChunk: (t: string) => void, onDone?: () => void, onSources?: (data: any) => void) =>
    apiStream("/api/v1/prior-art/due-diligence", body, onChunk, onDone, token, onSources),

  exportOAResponse: async (oaId: string, draftText: string) => {
    const url = `${API_URL}/api/v1/export/office-action/${oaId}`;
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ draft_text: draftText }),
    });
    if (!res.ok) throw new Error("Export failed");
    return res.blob();
  },

  saveOAResponseDraft: async (oaId: string, draftContent: string) =>
    apiFetch<Draft>(`/api/v1/office-actions/${oaId}/drafts`, {
      method: "POST",
      body: JSON.stringify({ draft_content: draftContent }),
      token,
    }),

  // Legal Knowledge Base
  listLegalSources: (jurisdiction?: string, includeInactive = false) =>
    apiFetch<any[]>(
      `/api/v1/knowledge-base/sources?include_inactive=${includeInactive}${jurisdiction ? `&jurisdiction=${jurisdiction}` : ""}`,
      { token }
    ),

  uploadLegalSource: (formData: FormData) => {
    const url = `${API_URL}/api/v1/knowledge-base/sources`;
    return fetch(url, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    }).then(async (res) => {
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Upload failed" }));
        throw new Error(err.detail || "Upload failed");
      }
      return res.json();
    });
  },

  toggleLegalSource: (sourceId: string, isActive: boolean) =>
    apiFetch<any>(`/api/v1/knowledge-base/sources/${sourceId}`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: isActive }),
      token,
    }),

  deleteLegalSource: (sourceId: string) =>
    apiFetch<void>(`/api/v1/knowledge-base/sources/${sourceId}`, {
      method: "DELETE",
      token,
    }),

  getJurisdictions: () =>
    apiFetch<Array<{ jurisdiction: string; source_count: number; total_chunks: number }>>(
      "/api/v1/knowledge-base/jurisdictions",
      { token }
    ),

  getJurisdictionStatus: (code: string) =>
    apiFetch<{
      jurisdiction: string;
      source_count: number;
      total_chunks: number;
      has_sources: boolean;
      is_stale: boolean;
      oldest_source_date: string | null;
    }>(`/api/v1/knowledge-base/jurisdictions/${code}/status`, { token }),
    
  exportPriorArtReport: async (data: { client_name: string; invention_title: string; results: any[] }) => {
    const url = `${API_URL}/api/v1/export/prior-art`;
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Export failed");
    return res.blob();
  },

  exportPatentabilityReport: async (data: { client_name: string; invention_title: string; analysis: string; claims: string[]; prior_art: any[] }) => {
    const url = `${API_URL}/api/v1/export/patentability`;
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Export failed");
    return res.blob();
  },
});

// Original api object kept for compatibility with any existing static imports, but empty/null token
export const api = createApi();
