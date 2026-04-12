"use client";

import { useEffect, useState, useRef } from "react";
import Header from "@/components/Header";
import { Patent, PatentUploadResponse } from "@/lib/api";
import { useApi } from "@/hooks/use-api";
import { getErrorMessage } from "@/lib/utils";
import {
  ShieldAlert, Sparkles, Loader2, FileText, Upload, AlertTriangle
} from "lucide-react";

export default function RiskPage() {
  const api = useApi();
  const [patents, setPatents] = useState<Patent[]>([]);
  const [selectedPatentId, setSelectedPatentId] = useState("");
  const [analysisType, setAnalysisType] = useState("invalidity");
  const [productDescription, setProductDescription] = useState("");
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisText, setAnalysisText] = useState("");
  const [uploadingPDF, setUploadingPDF] = useState(false);
  const [uploadResult, setUploadResult] = useState<PatentUploadResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const outputRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.listPatents(1)
      .then((res) => setPatents(res.patents))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  async function handleUploadPDF(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !selectedPatentId) return;
    setUploadingPDF(true);
    try {
      const result = await api.uploadPatentPDF(selectedPatentId, file);
      setUploadResult(result);
    } catch (err: unknown) {
      alert(getErrorMessage(err));
    } finally {
      setUploadingPDF(false);
    }
  }

  const [demographics, setDemographics] = useState("");
  const [targetClaims, setTargetClaims] = useState("");

  if (loading) {
    return (
      <>
        <Header
          title="Risk & Invalidity Analysis"
          subtitle="AI-powered claim charts and element-by-element mapping"
        />
        <div className="page-content">
          <div className="card" style={{ padding: 48, textAlign: "center" }}>
            <Loader2 style={{ width: 32, height: 32, animation: "spin 1s linear infinite" }} />
            <p style={{ marginTop: 16, color: "var(--text-secondary)" }}>Loading patents…</p>
          </div>
        </div>
      </>
    );
  }

  async function handleAnalyze() {
    if (!selectedPatentId) return;
    setAnalyzing(true);
    setAnalysisText("");

    const body: Record<string, unknown> = {
      patent_id: selectedPatentId,
      analysis_type: analysisType,
    };

    if (analysisType === "infringement" && productDescription) {
      body.product_description = productDescription;
      if (demographics) body.product_description += `\nTarget Market: ${demographics}`;
      if (targetClaims) body.target_claims = targetClaims.split(",").map(s => parseInt(s.trim())).filter(n => !isNaN(n));
    }

    try {
      await api.runRiskAnalysis(
        body,
        (chunk) => {
          setAnalysisText((prev) => prev + chunk);
          // Auto-scroll
          if (outputRef.current) {
            outputRef.current.scrollTop = outputRef.current.scrollHeight;
          }
        },
        () => setAnalyzing(false),
      );
    } catch (err: unknown) {
      alert(getErrorMessage(err));
      setAnalyzing(false);
    }
  }

  return (
    <>
      <Header
        title="Risk & Invalidity Analysis"
        subtitle="AI-powered claim charts and element-by-element mapping"
      />
      <div className="page-content">
        {/* Analysis Setup */}
        <div className="card-glass" style={{
          marginBottom: 32,
          background: "linear-gradient(135deg, rgba(99,102,241,0.06), rgba(239,68,68,0.04))",
          border: "1px solid rgba(99,102,241,0.15)",
        }}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>
            <div style={{
              width: 48, height: 48, borderRadius: "var(--radius-lg)",
              background: "linear-gradient(135deg, var(--error), var(--brand-600))",
              display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
            }}>
              <ShieldAlert style={{ width: 24, height: 24, color: "white" }} />
            </div>
            <div style={{ flex: 1 }}>
              <h3 style={{ fontSize: 16, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                AI Risk Analysis
              </h3>
              <p style={{ fontSize: 14, color: "var(--text-secondary)", lineHeight: 1.6, marginBottom: 16 }}>
                Select a patent and analysis type. AI will generate structured claim charts with
                element-by-element mapping, risk scores, and actionable recommendations.
              </p>

              <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
                <div className="form-group" style={{ flex: 2, marginBottom: 0 }}>
                  <label className="label">Select Patent</label>
                  <select className="input" value={selectedPatentId} onChange={(e) => { setSelectedPatentId(e.target.value); setUploadResult(null); }}>
                    <option value="">Choose a patent...</option>
                    {patents.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.patent_number || p.application_number} — {p.title.substring(0, 60)}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
                  <label className="label">Analysis Type</label>
                  <select className="input" value={analysisType} onChange={(e) => setAnalysisType(e.target.value)}>
                    <option value="invalidity">Invalidity</option>
                    <option value="infringement">Infringement</option>
                    <option value="freedom-to-operate">Freedom to Operate</option>
                  </select>
                </div>
              </div>

              {/* Infringement: product description */}
              {analysisType === "infringement" && (
                <div style={{ marginBottom: 16 }}>
                  <div className="form-group" style={{ marginBottom: 12 }}>
                    <label className="label">Product/System Description *</label>
                    <textarea
                      className="input textarea"
                      placeholder="Describe your client's product in detail. Include key technical features, how it works, and which components may read on the patent claims..."
                      style={{ minHeight: 80 }}
                      value={productDescription}
                      onChange={(e) => setProductDescription(e.target.value)}
                    />
                  </div>
                  
                  <div style={{ display: "flex", gap: 12 }}>
                    <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
                      <label className="label">Target Demographics / Market</label>
                      <input
                        className="input"
                        placeholder="e.g. Enterprise Hospitals, Consumer Electronics..."
                        id="target_demographics"
                        value={demographics}
                        onChange={(e) => setDemographics(e.target.value)}
                      />
                    </div>
                    <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
                      <label className="label">Target Claims (Optional)</label>
                      <input
                        className="input"
                        placeholder="e.g. 1, 4, 7-12"
                        id="target_claims"
                        value={targetClaims}
                        onChange={(e) => setTargetClaims(e.target.value)}
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Upload PDF for patent */}
              {selectedPatentId && (
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf"
                    style={{ display: "none" }}
                    onChange={handleUploadPDF}
                  />
                  <button className="btn btn-secondary" onClick={() => fileInputRef.current?.click()} disabled={uploadingPDF}>
                    {uploadingPDF ? <Loader2 style={{ width: 16, height: 16, animation: "spin 1s linear infinite" }} /> : <Upload style={{ width: 16, height: 16 }} />}
                    {uploadingPDF ? "Processing..." : "Upload Patent PDF"}
                  </button>
                  {uploadResult && (
                    <span style={{ fontSize: 13, color: "var(--success)" }}>
                      ✓ Processed: {uploadResult.chunks} chunks, {uploadResult.embeddings_stored} embeddings
                    </span>
                  )}
                </div>
              )}

              <button className="btn btn-primary" onClick={handleAnalyze} disabled={analyzing || !selectedPatentId}>
                {analyzing ? <Loader2 style={{ width: 16, height: 16, animation: "spin 1s linear infinite" }} /> : <Sparkles style={{ width: 16, height: 16 }} />}
                {analyzing ? "Analyzing..." : "Run Analysis"}
              </button>
            </div>
          </div>
        </div>

        {/* Upload Summary */}
        {uploadResult?.summary && !uploadResult.summary.parse_error && (
          <div className="card" style={{ marginBottom: 24 }}>
            <div className="card-header">
              <div className="card-title">📋 AI Patent Summary</div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
              <div style={{ padding: 16, background: "var(--bg-tertiary)", borderRadius: "var(--radius-md)" }}>
                <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginBottom: 4 }}>Quality Score</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: "var(--brand-400)" }}>
                  {uploadResult.summary.overall_quality_score || "—"}/100
                </div>
              </div>
              <div style={{ padding: 16, background: "var(--bg-tertiary)", borderRadius: "var(--radius-md)" }}>
                <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginBottom: 4 }}>Prior Art Vulnerability</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: uploadResult.summary.prior_art_vulnerability === "high" ? "var(--error)" : uploadResult.summary.prior_art_vulnerability === "medium" ? "var(--warning)" : "var(--success)" }}>
                  {uploadResult.summary.prior_art_vulnerability?.toUpperCase() || "—"}
                </div>
              </div>
            </div>
            <div style={{ fontSize: 14, color: "var(--text-secondary)", lineHeight: 1.7 }}>
              <strong>Core Invention:</strong> {uploadResult.summary.core_invention}
            </div>
            {Array.isArray(uploadResult.summary.weaknesses) && uploadResult.summary.weaknesses.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--warning)", marginBottom: 4 }}>
                  <AlertTriangle style={{ width: 14, height: 14, display: "inline" }} /> Weaknesses Found
                </div>
                {uploadResult.summary.weaknesses.map((w, i: number) => (
                  <div key={i} style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 4, paddingLeft: 16 }}>
                    • Claim {w.claim_number}: {w.issue} ({w.severity} severity)
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Analysis Output */}
        {analysisText && (
          <div className="card">
            <div className="card-header">
              <div className="card-title">
                {analyzing ? "⚡ Generating Analysis..." : "✅ Risk Analysis Report"}
              </div>
            </div>
            <div
              ref={outputRef}
              style={{
                whiteSpace: "pre-wrap", fontSize: 13, lineHeight: 1.7,
                color: "var(--text-secondary)", maxHeight: 700, overflowY: "auto",
                fontFamily: "'Inter', sans-serif",
              }}
            >
              {analysisText}
            </div>
          </div>
        )}

        {/* Patent List (idle state) */}
        {!analysisText && !uploadResult && patents.length > 0 && (
          <div className="card">
            <div className="card-header">
              <div className="card-title">Available Patents</div>
              <div className="card-subtitle">{patents.length} in portfolio</div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {patents.map((p) => (
                <div key={p.id} onClick={() => setSelectedPatentId(p.id)} style={{
                  padding: "14px 18px", background: selectedPatentId === p.id ? "rgba(99,102,241,0.08)" : "var(--bg-tertiary)",
                  borderRadius: "var(--radius-md)", border: `1px solid ${selectedPatentId === p.id ? "var(--brand-500)" : "var(--glass-border)"}`,
                  cursor: "pointer", display: "flex", alignItems: "center", gap: 12,
                }}>
                  <FileText style={{ width: 18, height: 18, color: "var(--brand-400)", flexShrink: 0 }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>{p.title}</div>
                    <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>{p.patent_number || p.application_number}</div>
                  </div>
                  <span className={`badge ${p.status === "granted" ? "badge-granted" : p.status === "abandoned" ? "badge-abandoned" : "badge-pending"}`}>
                    {p.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
