"use client";

import { useEffect, useState, useRef } from "react";
import Header from "@/components/Header";
import { Patent } from "@/lib/api";
import { useApi } from "@/hooks/use-api";
import { getErrorMessage } from "@/lib/utils";
import {
  Scale, Sparkles, Loader2, FileText, BarChart3, TrendingUp, CheckSquare, Square
} from "lucide-react";

export default function DueDiligencePage() {
  const api = useApi();
  const [patents, setPatents] = useState<Patent[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [context, setContext] = useState("");
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [reportText, setReportText] = useState("");
  const outputRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.listPatents(1)
      .then((res) => {
        setPatents(res.patents);
        // Select all by default
        setSelectedIds(new Set(res.patents.map((p) => p.id)));
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  function togglePatent(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  function selectAll() {
    setSelectedIds(new Set(patents.map((p) => p.id)));
  }

  function selectNone() {
    setSelectedIds(new Set());
  }

  async function handleGenerate() {
    if (selectedIds.size === 0) return;
    setAnalyzing(true);
    setReportText("");

    try {
      await api.generateDueDiligence(
        {
          patent_ids: Array.from(selectedIds),
          context: context || undefined,
        },
        (chunk: string) => {
          setReportText((prev) => prev + chunk);
          if (outputRef.current) outputRef.current.scrollTop = outputRef.current.scrollHeight;
        },
        () => setAnalyzing(false),
      );
    } catch (err: unknown) {
      alert(getErrorMessage(err));
      setAnalyzing(false);
    }
  }

  const [uploadingZip, setUploadingZip] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (loading) {
    return (
      <>
        <Header
          title="Licensing Due Diligence"
          subtitle="AI-generated portfolio assessment and risk scoring"
        />
        <div className="page-content">
          <div className="card" style={{ padding: 48, textAlign: "center" }}>
            <Loader2 style={{ width: 32, height: 32, animation: "spin 1s linear infinite" }} />
            <p style={{ marginTop: 16, color: "var(--text-secondary)" }}>Loading portfolio...</p>
          </div>
        </div>
      </>
    );
  }

  async function handleZipUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingZip(true);
    try {
      const res = await api.uploadZip(file);
      alert(res.message);
      // Refresh patents
      const pats = await api.listPatents(1);
      setPatents(pats.patents);
    } catch (err: unknown) {
      alert(getErrorMessage(err));
    } finally {
      setUploadingZip(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  const grantedCount = patents.filter((p) => p.status === "granted").length;
  const pendingCount = patents.filter((p) => p.status === "pending").length;

  return (
    <>
      <Header
        title="Licensing Due Diligence"
        subtitle="AI-generated portfolio assessment and risk scoring"
      />
      <div className="page-content">
        {/* Stats */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginBottom: 24 }}>
          <div className="stat-card">
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
              <FileText style={{ width: 18, height: 18, color: "var(--brand-400)" }} />
              <span className="stat-label" style={{ marginBottom: 0 }}>Portfolio Size</span>
            </div>
            <div className="stat-value">{patents.length}</div>
            <div className="stat-change positive">Total patents</div>
          </div>
          <div className="stat-card">
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
              <BarChart3 style={{ width: 18, height: 18, color: "var(--success)" }} />
              <span className="stat-label" style={{ marginBottom: 0 }}>Granted</span>
            </div>
            <div className="stat-value">{grantedCount}</div>
            <div className="stat-change positive">Ready for licensing</div>
          </div>
          <div className="stat-card">
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
              <TrendingUp style={{ width: 18, height: 18, color: "var(--warning)" }} />
              <span className="stat-label" style={{ marginBottom: 0 }}>Pending</span>
            </div>
            <div className="stat-value">{pendingCount}</div>
            <div className="stat-change positive">In prosecution</div>
          </div>
        </div>

        {/* Report Generator */}
        <div className="card-glass" style={{
          marginBottom: 24,
          background: "linear-gradient(135deg, rgba(99,102,241,0.06), rgba(139,92,246,0.04))",
          border: "1px solid rgba(99,102,241,0.15)",
        }}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>
            <div style={{
              width: 48, height: 48, borderRadius: "var(--radius-lg)",
              background: "linear-gradient(135deg, var(--brand-500), var(--accent-500))",
              display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
            }}>
              <Scale style={{ width: 24, height: 24, color: "white" }} />
            </div>
            <div style={{ flex: 1 }}>
              <h3 style={{ fontSize: 16, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                AI Due Diligence Report
              </h3>
              <p style={{ fontSize: 14, color: "var(--text-secondary)", lineHeight: 1.6, marginBottom: 16 }}>
                Select patents to include. AI will analyze each patent&apos;s claim strength, prior art risk,
                remaining life, and produce a scored portfolio assessment with actionable recommendations.
              </p>

              {/* Patent Selection */}
              <div style={{ marginBottom: 16 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <label className="label" style={{ marginBottom: 0 }}>Select Patents ({selectedIds.size}/{patents.length})</label>
                  <div style={{ display: "flex", gap: 8 }}>
                    <input
                      type="file"
                      accept=".zip"
                      style={{ display: "none" }}
                      ref={fileInputRef}
                      onChange={handleZipUpload}
                    />
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={uploadingZip}
                    >
                      {uploadingZip ? <Loader2 style={{ width: 14, height: 14, animation: "spin 1s linear infinite" }} /> : null}
                      {uploadingZip ? "Uploading..." : "Upload Bulk Zip"}
                    </button>
                    <button className="btn btn-ghost btn-sm" onClick={selectAll}>Select All</button>
                    <button className="btn btn-ghost btn-sm" onClick={selectNone}>Clear</button>
                  </div>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 200, overflowY: "auto" }}>
                  {patents.map((p) => (
                    <div key={p.id} onClick={() => togglePatent(p.id)} style={{
                      padding: "10px 14px", background: selectedIds.has(p.id) ? "rgba(99,102,241,0.08)" : "var(--bg-tertiary)",
                      borderRadius: "var(--radius-sm)", border: `1px solid ${selectedIds.has(p.id) ? "var(--brand-500)" : "var(--glass-border)"}`,
                      cursor: "pointer", display: "flex", alignItems: "center", gap: 10, fontSize: 13,
                    }}>
                      {selectedIds.has(p.id) ? (
                        <CheckSquare style={{ width: 16, height: 16, color: "var(--brand-400)" }} />
                      ) : (
                        <Square style={{ width: 16, height: 16, color: "var(--text-tertiary)" }} />
                      )}
                      <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>{p.patent_number || p.application_number}</span>
                      <span style={{ color: "var(--text-secondary)", flex: 1 }}>{p.title.substring(0, 50)}...</span>
                      <span className={`badge ${p.status === "granted" ? "badge-granted" : "badge-pending"}`}>{p.status}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Context */}
              <div className="form-group" style={{ marginBottom: 16 }}>
                <label className="label">Deal Context (optional)</label>
                <textarea
                  className="input textarea"
                  placeholder="e.g. Target company is being acquired for $40M. Buyer needs IP due diligence report by Friday."
                  style={{ minHeight: 60 }}
                  value={context}
                  onChange={(e) => setContext(e.target.value)}
                />
              </div>

              <button className="btn btn-primary" onClick={handleGenerate} disabled={analyzing || selectedIds.size === 0}>
                {analyzing ? <Loader2 style={{ width: 16, height: 16, animation: "spin 1s linear infinite" }} /> : <Sparkles style={{ width: 16, height: 16 }} />}
                {analyzing ? "Generating Report..." : `Generate Report (${selectedIds.size} patents)`}
              </button>
            </div>
          </div>
        </div>

        {/* Report Output */}
        {reportText && (
          <div className="card">
            <div className="card-header">
              <div className="card-title">
                {analyzing ? "⚡ Generating Due Diligence Report..." : "✅ Due Diligence Report"}
              </div>
            </div>
            <div
              ref={outputRef}
              style={{
                whiteSpace: "pre-wrap", fontSize: 13, lineHeight: 1.7,
                color: "var(--text-secondary)", maxHeight: 800, overflowY: "auto",
                fontFamily: "'Inter', sans-serif",
              }}
            >
              {reportText}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
