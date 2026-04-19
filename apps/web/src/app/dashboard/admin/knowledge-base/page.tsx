"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/hooks/useAuth";
import {
  Upload,
  BookOpen,
  Globe,
  Trash2,
  ToggleLeft,
  ToggleRight,
  AlertTriangle,
  CheckCircle2,
  FileText,
  RefreshCw,
  ChevronDown,
  Search,
} from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL?.trim().replace(/\/$/, "") || "";

interface LegalSource {
  id: string;
  firm_id: string | null;
  jurisdiction: string;
  doc_type: string;
  title: string;
  version: string | null;
  is_active: boolean;
  chunk_count: number;
  status: "active" | "processing" | "failed";
  source_updated_at: string | null;
  is_stale: boolean;
  created_at: string;
  updated_at: string;
}

const JURISDICTIONS = [
  { code: "USPTO", label: "USPTO", color: "#3b82f6" },
  { code: "EPO", label: "EPO", color: "#8b5cf6" },
  { code: "JPO", label: "JPO", color: "#ef4444" },
  { code: "CNIPA", label: "CNIPA", color: "#f59e0b" },
  { code: "IP_AUSTRALIA", label: "IP Australia", color: "#10b981" },
  { code: "WIPO", label: "WIPO", color: "#06b6d4" },
  { code: "firm", label: "Firm Policy", color: "#f97316" },
];

const DOC_TYPES = [
  { code: "statute", label: "Statute" },
  { code: "rule", label: "Rule / Regulation" },
  { code: "guideline", label: "Guideline (MPEP, etc.)" },
  { code: "firm_policy", label: "Firm Policy" },
  { code: "case_law", label: "Case Law" },
];

export default function KnowledgeBasePage() {
  const { token } = useAuth();
  const [sources, setSources] = useState<LegalSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");
  const [showUpload, setShowUpload] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Upload form state
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadJurisdiction, setUploadJurisdiction] = useState("USPTO");
  const [uploadDocType, setUploadDocType] = useState("guideline");
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadVersion, setUploadVersion] = useState("");
  const [uploadIsGlobal, setUploadIsGlobal] = useState(false);

  const fetchSources = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(
        `${API_URL}/api/v1/knowledge-base/sources?include_inactive=true`,
        { headers: token ? { Authorization: `Bearer ${token}` } : {} }
      );
      if (res.ok) {
        setSources(await res.json());
      }
    } catch {
      setError("Failed to load legal sources");
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  useEffect(() => {
    fetchSources();
  }, [fetchSources]);

  const handleUpload = async () => {
    if (!uploadFile || !uploadTitle.trim()) {
      setError("Please select a PDF file and enter a title");
      return;
    }

    setUploading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", uploadFile);
      formData.append("jurisdiction", uploadJurisdiction);
      formData.append("doc_type", uploadDocType);
      formData.append("title", uploadTitle);
      if (uploadVersion) formData.append("version", uploadVersion);
      formData.append("is_global", String(uploadIsGlobal));

      const res = await fetch(`${API_URL}/api/v1/knowledge-base/sources`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Upload failed" }));
        throw new Error(err.detail || "Upload failed");
      }

      const result = await res.json();
      setSuccess(
        `"${uploadTitle}" upload accepted. Ingestion has started in the background.`
      );
      setShowUpload(false);
      setUploadFile(null);
      setUploadTitle("");
      setUploadVersion("");
      fetchSources();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  };

  const toggleActive = async (source: LegalSource) => {
    try {
      const res = await fetch(
        `${API_URL}/api/v1/knowledge-base/sources/${source.id}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ is_active: !source.is_active }),
        }
      );
      if (res.ok) {
        setSources((prev) =>
          prev.map((s) =>
            s.id === source.id ? { ...s, is_active: !s.is_active } : s
          )
        );
      }
    } catch {
      setError("Failed to toggle source");
    }
  };

  const deleteSource = async (source: LegalSource) => {
    if (!confirm(`Delete "${source.title}" and all its ${source.chunk_count} chunks? This cannot be undone.`)) return;

    try {
      await fetch(`${API_URL}/api/v1/knowledge-base/sources/${source.id}`, {
        method: "DELETE",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setSources((prev) => prev.filter((s) => s.id !== source.id));
      setSuccess(`"${source.title}" deleted`);
    } catch {
      setError("Failed to delete source");
    }
  };

  const filteredSources = sources.filter(
    (s) =>
      !filter ||
      s.title.toLowerCase().includes(filter.toLowerCase()) ||
      s.jurisdiction.toLowerCase().includes(filter.toLowerCase())
  );

  // Group by jurisdiction
  const grouped = JURISDICTIONS.map((j) => ({
    ...j,
    sources: filteredSources.filter((s) => s.jurisdiction === j.code),
  })).filter((g) => g.sources.length > 0);

  const totalChunks = sources.reduce((acc, s) => acc + s.chunk_count, 0);
  const activeSources = sources.filter((s) => s.is_active).length;
  const staleSources = sources.filter((s) => s.is_stale).length;

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1100, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: "var(--text-primary)", margin: 0, display: "flex", alignItems: "center", gap: 10 }}>
            <BookOpen style={{ width: 22, height: 22, color: "var(--brand-400)" }} />
            Legal Knowledge Base
          </h1>
          <p style={{ fontSize: 13, color: "var(--text-tertiary)", margin: "4px 0 0" }}>
            Upload legal sources to ground AI responses in authoritative materials only
          </p>
        </div>
        <button
          onClick={() => setShowUpload(!showUpload)}
          style={{
            display: "flex", alignItems: "center", gap: 6,
            padding: "8px 16px", borderRadius: "var(--radius-md)",
            background: "linear-gradient(135deg, var(--brand-500), var(--brand-600))",
            color: "white", border: "none", cursor: "pointer",
            fontSize: 13, fontWeight: 600,
          }}
        >
          <Upload style={{ width: 14, height: 14 }} />
          Upload Source
        </button>
      </div>

      {/* Stats Bar */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
        {[
          { label: "Total Sources", value: sources.length, icon: FileText, color: "var(--brand-400)" },
          { label: "Active", value: activeSources, icon: CheckCircle2, color: "rgb(16, 185, 129)" },
          { label: "Total Chunks", value: totalChunks.toLocaleString(), icon: BookOpen, color: "var(--accent-400)" },
          { label: "Stale (>12mo)", value: staleSources, icon: AlertTriangle, color: staleSources > 0 ? "rgb(245, 158, 11)" : "var(--text-tertiary)" },
        ].map((stat) => (
          <div key={stat.label} style={{
            padding: "14px 16px", borderRadius: "var(--radius-lg)",
            background: "var(--bg-secondary)", border: "1px solid var(--glass-border)",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
              <stat.icon style={{ width: 14, height: 14, color: stat.color }} />
              <span style={{ fontSize: 11, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                {stat.label}
              </span>
            </div>
            <div style={{ fontSize: 20, fontWeight: 700, color: "var(--text-primary)" }}>{stat.value}</div>
          </div>
        ))}
      </div>

      {/* Alerts */}
      {error && (
        <div style={{ padding: "10px 14px", borderRadius: "var(--radius-md)", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", color: "#ef4444", fontSize: 13, marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
          <AlertTriangle style={{ width: 14, height: 14 }} /> {error}
          <button onClick={() => setError(null)} style={{ marginLeft: "auto", background: "none", border: "none", color: "#ef4444", cursor: "pointer" }}>✕</button>
        </div>
      )}
      {success && (
        <div style={{ padding: "10px 14px", borderRadius: "var(--radius-md)", background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.3)", color: "rgb(16,185,129)", fontSize: 13, marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
          <CheckCircle2 style={{ width: 14, height: 14 }} /> {success}
          <button onClick={() => setSuccess(null)} style={{ marginLeft: "auto", background: "none", border: "none", color: "rgb(16,185,129)", cursor: "pointer" }}>✕</button>
        </div>
      )}

      {/* Upload Form */}
      {showUpload && (
        <div style={{
          padding: 20, borderRadius: "var(--radius-lg)",
          background: "var(--bg-secondary)", border: "1px solid var(--brand-500)40",
          marginBottom: 20,
        }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)", margin: "0 0 14px", display: "flex", alignItems: "center", gap: 8 }}>
            <Upload style={{ width: 14, height: 14, color: "var(--brand-400)" }} />
            Upload Legal Source Document
          </h3>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {/* File */}
            <div style={{ gridColumn: "1 / -1" }}>
              <label style={{ fontSize: 12, color: "var(--text-tertiary)", marginBottom: 4, display: "block" }}>PDF File *</label>
              <input
                type="file"
                accept=".pdf"
                onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                style={{ fontSize: 13, color: "var(--text-primary)", width: "100%" }}
              />
            </div>

            {/* Title */}
            <div style={{ gridColumn: "1 / -1" }}>
              <label style={{ fontSize: 12, color: "var(--text-tertiary)", marginBottom: 4, display: "block" }}>Title *</label>
              <input
                type="text"
                value={uploadTitle}
                onChange={(e) => setUploadTitle(e.target.value)}
                placeholder='e.g. "USPTO MPEP Chapter 2100"'
                style={{
                  width: "100%", padding: "8px 10px", borderRadius: "var(--radius-md)",
                  border: "1px solid var(--glass-border)", background: "var(--bg-tertiary)",
                  color: "var(--text-primary)", fontSize: 13,
                }}
              />
            </div>

            {/* Jurisdiction */}
            <div>
              <label style={{ fontSize: 12, color: "var(--text-tertiary)", marginBottom: 4, display: "block" }}>Jurisdiction *</label>
              <select
                value={uploadJurisdiction}
                onChange={(e) => setUploadJurisdiction(e.target.value)}
                style={{
                  width: "100%", padding: "8px 10px", borderRadius: "var(--radius-md)",
                  border: "1px solid var(--glass-border)", background: "var(--bg-tertiary)",
                  color: "var(--text-primary)", fontSize: 13,
                }}
              >
                {JURISDICTIONS.map((j) => (
                  <option key={j.code} value={j.code}>{j.label}</option>
                ))}
              </select>
            </div>

            {/* Doc Type */}
            <div>
              <label style={{ fontSize: 12, color: "var(--text-tertiary)", marginBottom: 4, display: "block" }}>Document Type *</label>
              <select
                value={uploadDocType}
                onChange={(e) => setUploadDocType(e.target.value)}
                style={{
                  width: "100%", padding: "8px 10px", borderRadius: "var(--radius-md)",
                  border: "1px solid var(--glass-border)", background: "var(--bg-tertiary)",
                  color: "var(--text-primary)", fontSize: 13,
                }}
              >
                {DOC_TYPES.map((d) => (
                  <option key={d.code} value={d.code}>{d.label}</option>
                ))}
              </select>
            </div>

            {/* Version */}
            <div>
              <label style={{ fontSize: 12, color: "var(--text-tertiary)", marginBottom: 4, display: "block" }}>Version</label>
              <input
                type="text"
                value={uploadVersion}
                onChange={(e) => setUploadVersion(e.target.value)}
                placeholder='e.g. "2024.01"'
                style={{
                  width: "100%", padding: "8px 10px", borderRadius: "var(--radius-md)",
                  border: "1px solid var(--glass-border)", background: "var(--bg-tertiary)",
                  color: "var(--text-primary)", fontSize: 13,
                }}
              />
            </div>

            {/* Global toggle */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, paddingTop: 20 }}>
              <button
                onClick={() => setUploadIsGlobal(!uploadIsGlobal)}
                style={{ background: "none", border: "none", cursor: "pointer", display: "flex", alignItems: "center" }}
              >
                {uploadIsGlobal
                  ? <ToggleRight style={{ width: 24, height: 24, color: "var(--brand-400)" }} />
                  : <ToggleLeft style={{ width: 24, height: 24, color: "var(--text-tertiary)" }} />
                }
              </button>
              <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                Global source (all firms)
              </span>
            </div>
          </div>

          {/* Submit */}
          <div style={{ display: "flex", gap: 8, marginTop: 16, justifyContent: "flex-end" }}>
            <button
              onClick={() => setShowUpload(false)}
              style={{
                padding: "8px 16px", borderRadius: "var(--radius-md)",
                background: "var(--bg-tertiary)", border: "1px solid var(--glass-border)",
                color: "var(--text-secondary)", fontSize: 13, cursor: "pointer",
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleUpload}
              disabled={uploading || !uploadFile || !uploadTitle.trim()}
              style={{
                padding: "8px 20px", borderRadius: "var(--radius-md)",
                background: uploading ? "var(--bg-tertiary)" : "linear-gradient(135deg, var(--brand-500), var(--brand-600))",
                color: "white", border: "none", cursor: uploading ? "wait" : "pointer",
                fontSize: 13, fontWeight: 600, opacity: (!uploadFile || !uploadTitle.trim()) ? 0.5 : 1,
              }}
            >
              {uploading ? "Processing..." : "Upload & Index"}
            </button>
          </div>
        </div>
      )}

      {/* Filter */}
      <div style={{ position: "relative", marginBottom: 16 }}>
        <Search style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", width: 14, height: 14, color: "var(--text-tertiary)" }} />
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter sources..."
          style={{
            width: "100%", padding: "8px 10px 8px 32px", borderRadius: "var(--radius-md)",
            border: "1px solid var(--glass-border)", background: "var(--bg-secondary)",
            color: "var(--text-primary)", fontSize: 13,
          }}
        />
      </div>

      {/* Sources grouped by jurisdiction */}
      {loading ? (
        <div style={{ textAlign: "center", padding: 40, color: "var(--text-tertiary)" }}>
          <RefreshCw style={{ width: 20, height: 20, animation: "spin 1s linear infinite" }} />
          <div style={{ marginTop: 8, fontSize: 13 }}>Loading legal sources...</div>
        </div>
      ) : grouped.length === 0 ? (
        <div style={{
          textAlign: "center", padding: 48,
          background: "var(--bg-secondary)", borderRadius: "var(--radius-lg)",
          border: "1px solid var(--glass-border)",
        }}>
          <BookOpen style={{ width: 32, height: 32, color: "var(--text-tertiary)", margin: "0 auto 12px" }} />
          <div style={{ fontSize: 15, fontWeight: 600, color: "var(--text-primary)", marginBottom: 4 }}>
            No legal sources uploaded
          </div>
          <div style={{ fontSize: 13, color: "var(--text-tertiary)", maxWidth: 400, margin: "0 auto" }}>
            Upload MPEP chapters, statutes, and firm drafting standards to enable strict legal grounding.
            Start with USPTO MPEP Chapter 2100 for claim interpretation rules.
          </div>
        </div>
      ) : (
        grouped.map((group) => (
          <div key={group.code} style={{ marginBottom: 20 }}>
            <div style={{
              display: "flex", alignItems: "center", gap: 8,
              marginBottom: 8, paddingBottom: 6,
              borderBottom: "1px solid var(--glass-border)",
            }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: group.color }} />
              <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
                {group.label}
              </span>
              <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
                {group.sources.length} source{group.sources.length !== 1 ? "s" : ""}
              </span>
            </div>

            {group.sources.map((source) => (
              <div
                key={source.id}
                style={{
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                  padding: "10px 14px", borderRadius: "var(--radius-md)",
                  background: "var(--bg-secondary)", border: "1px solid var(--glass-border)",
                  marginBottom: 4, opacity: source.is_active ? 1 : 0.6,
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)" }}>
                      {source.title}
                    </span>
                    {source.version && (
                      <span style={{ fontSize: 10, padding: "1px 5px", borderRadius: 4, background: "var(--bg-tertiary)", color: "var(--text-tertiary)" }}>
                        v{source.version}
                      </span>
                    )}
                    {source.is_stale && (
                      <span style={{ fontSize: 10, padding: "1px 5px", borderRadius: 4, background: "rgba(245,158,11,0.15)", color: "rgb(245,158,11)" }}>
                        ⚠ stale
                      </span>
                    )}
                    {!source.firm_id && (
                      <span style={{ fontSize: 10, padding: "1px 5px", borderRadius: 4, background: "rgba(59,130,246,0.15)", color: "rgb(59,130,246)" }}>
                        global
                      </span>
                    )}
                    <span style={{ fontSize: 10, padding: "1px 5px", borderRadius: 4, background: "var(--bg-tertiary)", color: "var(--text-tertiary)" }}>
                      {source.doc_type}
                    </span>
                    {source.status === "processing" && (
                      <span style={{ 
                        fontSize: 10, padding: "1px 5px", borderRadius: 4, 
                        background: "rgba(59,130,246,0.1)", color: "var(--brand-400)",
                        display: "flex", alignItems: "center", gap: 4
                      }}>
                        <RefreshCw style={{ width: 10, height: 10, animation: "spin 2s linear infinite" }} />
                        indexing...
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 2 }}>
                    {source.chunk_count} chunks · uploaded {new Date(source.created_at).toLocaleDateString()}
                  </div>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <button
                    onClick={() => toggleActive(source)}
                    title={source.is_active ? "Deactivate" : "Activate"}
                    style={{ background: "none", border: "none", cursor: "pointer", display: "flex", alignItems: "center" }}
                  >
                    {source.is_active
                      ? <ToggleRight style={{ width: 22, height: 22, color: "rgb(16,185,129)" }} />
                      : <ToggleLeft style={{ width: 22, height: 22, color: "var(--text-tertiary)" }} />
                    }
                  </button>
                  {source.firm_id && (
                    <button
                      onClick={() => deleteSource(source)}
                      title="Delete source"
                      style={{
                        background: "none", border: "none", cursor: "pointer",
                        display: "flex", alignItems: "center", padding: 4,
                      }}
                    >
                      <Trash2 style={{ width: 14, height: 14, color: "var(--text-tertiary)" }} />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        ))
      )}
    </div>
  );
}
