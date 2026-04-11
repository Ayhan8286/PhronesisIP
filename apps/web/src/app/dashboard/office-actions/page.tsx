"use client";

import { useEffect, useMemo, useState, useRef } from "react";
import Header from "@/components/Header";
import { api, OfficeAction, Patent } from "@/lib/api";
import { getErrorMessage } from "@/lib/utils";
import {
  Mail, Upload, Sparkles, Loader2, Clock, AlertTriangle,
  CheckCircle2, FileText, ChevronDown, ChevronUp
} from "lucide-react";

export default function OfficeActionsPage() {
  const [actions, setActions] = useState<OfficeAction[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedOA, setExpandedOA] = useState<string | null>(null);
  const [viewingPDF, setViewingPDF] = useState<string | null>(null);

  // Upload state
  const [uploading, setUploading] = useState(false);
  const [patents, setPatents] = useState<Patent[]>([]);
  const [uploadPatentId, setUploadPatentId] = useState("");
  const [uploadActionType, setUploadActionType] = useState("Non-Final Rejection");
  const [showUpload, setShowUpload] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // AI Response state
  const [generatingFor, setGeneratingFor] = useState<string | null>(null);
  const [responseText, setResponseText] = useState("");
  const now = useMemo(() => Date.now(), []);
  const responseRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    try {
      const [oas, patList] = await Promise.all([
        api.listOfficeActions(),
        api.listPatents(1),
      ]);
      setActions(oas);
      setPatents(patList.patents);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  async function handleUploadOA(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !uploadPatentId) return;
    setUploading(true);
    try {
      const result = await api.uploadOfficeActionPDF(uploadPatentId, file, uploadActionType);
      alert(`Office Action uploaded! ${result.rejections_found} rejections detected.`);
      setShowUpload(false);
      await loadData(); // Refresh list
    } catch (err: unknown) {
      alert(getErrorMessage(err));
    } finally {
      setUploading(false);
    }
  }

  async function handleGenerateResponse(oa: OfficeAction) {
    setGeneratingFor(oa.id);
    setResponseText("");
    setExpandedOA(oa.id);

    try {
      await api.generateOAResponse(
        oa.id,
        { response_strategy: "argue", additional_context: "" },
        (chunk) => {
          setResponseText((prev) => prev + chunk);
          if (responseRef.current) responseRef.current.scrollTop = responseRef.current.scrollHeight;
        },
        () => setGeneratingFor(null),
      );
    } catch (err: unknown) {
      alert(getErrorMessage(err));
      setGeneratingFor(null);
    }
  }

  async function handleViewPDF(patentId: string) {
    setViewingPDF(patentId);
    try {
      const { url } = await api.getDocumentViewUrl(patentId);
      window.open(url, "_blank");
    } catch (err: unknown) {
      alert(getErrorMessage(err));
    } finally {
      setViewingPDF(null);
    }
  }

  const pendingCount = actions.filter((a) => a.status === "pending").length;

  function daysRemaining(deadline: string | null): number | null {
    if (!deadline) return null;
    const diff = new Date(deadline).getTime() - now;
    return Math.ceil(diff / (1000 * 60 * 60 * 24));
  }

  return (
    <>
      <Header
        title="Office Actions"
        subtitle="Track and respond to USPTO office actions"
        actions={
          <button className="btn btn-primary" onClick={() => setShowUpload(!showUpload)}>
            <Upload style={{ width: 16, height: 16 }} /> Upload Office Action
          </button>
        }
      />
      <div className="page-content">
        {/* Upload Panel */}
        {showUpload && (
          <div className="card-glass" style={{
            marginBottom: 24, background: "linear-gradient(135deg, rgba(99,102,241,0.06), rgba(139,92,246,0.04))",
            border: "1px solid rgba(99,102,241,0.15)",
          }}>
            <h3 style={{ fontSize: 16, fontWeight: 600, color: "var(--text-primary)", marginBottom: 12 }}>
              Upload Office Action PDF
            </h3>
            <p style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 16 }}>
              Upload the office action PDF. AI will extract the text, identify all rejections (§102/§103/§112),
              and parse cited prior art references automatically.
            </p>
            <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
              <div className="form-group" style={{ flex: 2, marginBottom: 0 }}>
                <label className="label">Patent</label>
                <select className="input" value={uploadPatentId} onChange={(e) => setUploadPatentId(e.target.value)}>
                  <option value="">Select patent...</option>
                  {patents.map((p) => (
                    <option key={p.id} value={p.id}>{p.application_number} — {p.title.substring(0, 50)}</option>
                  ))}
                </select>
              </div>
              <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
                <label className="label">Action Type</label>
                <select className="input" value={uploadActionType} onChange={(e) => setUploadActionType(e.target.value)}>
                  <option>Non-Final Rejection</option>
                  <option>Final Rejection</option>
                  <option>Restriction Requirement</option>
                  <option>Advisory Action</option>
                </select>
              </div>
            </div>
            <input ref={fileRef} type="file" accept=".pdf" style={{ display: "none" }} onChange={handleUploadOA} />
            <button className="btn btn-primary" onClick={() => fileRef.current?.click()} disabled={uploading || !uploadPatentId}>
              {uploading ? <Loader2 style={{ width: 16, height: 16, animation: "spin 1s linear infinite" }} /> : <Upload style={{ width: 16, height: 16 }} />}
              {uploading ? "Processing PDF..." : "Upload & Parse"}
            </button>
          </div>
        )}

        {/* Alert */}
        {pendingCount > 0 && (
          <div style={{
            padding: "12px 20px", background: "rgba(245,158,11,0.08)",
            border: "1px solid rgba(245,158,11,0.2)", borderRadius: "var(--radius-md)",
            marginBottom: 20, display: "flex", alignItems: "center", gap: 8,
            color: "var(--warning)", fontSize: 14, fontWeight: 500,
          }}>
            <AlertTriangle style={{ width: 18, height: 18 }} />
            {pendingCount} office action{pendingCount > 1 ? "s" : ""} require{pendingCount === 1 ? "s" : ""} attention
          </div>
        )}

        {/* OA List */}
        {loading ? (
          <div style={{ display: "flex", justifyContent: "center", padding: 64 }}>
            <Loader2 style={{ width: 32, height: 32, color: "var(--brand-500)", animation: "spin 1s linear infinite" }} />
          </div>
        ) : actions.length === 0 ? (
          <div className="card" style={{ textAlign: "center", padding: 48 }}>
            <Mail style={{ width: 48, height: 48, color: "var(--text-tertiary)", margin: "0 auto 16px" }} />
            <h3 style={{ color: "var(--text-primary)", marginBottom: 8 }}>No Office Actions</h3>
            <p style={{ color: "var(--text-secondary)" }}>Upload an office action PDF to get started.</p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {actions.map((oa) => {
              const days = daysRemaining(oa.response_deadline);
              const isExpanded = expandedOA === oa.id;
              return (
                <div key={oa.id} className="card" style={{
                  borderLeft: `3px solid ${oa.status === "responded" ? "var(--success)" : days !== null && days < 30 ? "var(--error)" : "var(--warning)"}`,
                }}>
                  {/* Header */}
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      {oa.status === "responded" ? (
                        <div style={{ width: 36, height: 36, borderRadius: "50%", background: "rgba(34,197,94,0.1)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                          <CheckCircle2 style={{ width: 20, height: 20, color: "var(--success)" }} />
                        </div>
                      ) : (
                        <div style={{ width: 36, height: 36, borderRadius: "50%", background: "rgba(239,68,68,0.1)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                          <Mail style={{ width: 20, height: 20, color: "var(--error)" }} />
                        </div>
                      )}
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span className={`badge ${oa.status === "responded" ? "badge-granted" : "badge-pending"}`}>
                            {oa.status}
                          </span>
                          <span style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>
                            {oa.action_type}
                          </span>
                        </div>
                        {oa.rejections && oa.rejections.length > 0 && (
                          <div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 4 }}>
                            {oa.rejections.map((r, i: number) => (
                              <span key={i}>
                                §{r.type} — {r.references?.join(", ") || r.basis || ""}
                                {i < oa.rejections.length - 1 ? " | " : ""}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      {oa.status === "pending" && (
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() => handleGenerateResponse(oa)}
                          disabled={generatingFor === oa.id || !oa.extracted_text}
                        >
                          {generatingFor === oa.id ? (
                            <Loader2 style={{ width: 14, height: 14, animation: "spin 1s linear infinite" }} />
                          ) : (
                            <Sparkles style={{ width: 14, height: 14 }} />
                          )}
                          AI Response
                        </button>
                      )}
                      {oa.patent_id && (
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => handleViewPDF(oa.patent_id)}
                          disabled={viewingPDF === oa.patent_id}
                          title="View Source PDF"
                        >
                          {viewingPDF === oa.patent_id ? (
                            <Loader2 style={{ width: 14, height: 14, animation: "spin 1s linear infinite" }} />
                          ) : (
                            <FileText style={{ width: 14, height: 14 }} />
                          )}
                          Source PDF
                        </button>
                      )}
                      <button className="btn btn-ghost btn-sm" onClick={() => setExpandedOA(isExpanded ? null : oa.id)}>
                        {isExpanded ? <ChevronUp style={{ width: 16, height: 16 }} /> : <ChevronDown style={{ width: 16, height: 16 }} />}
                      </button>
                    </div>
                  </div>

                  {/* Meta */}
                  <div style={{ display: "flex", gap: 16, marginTop: 8, fontSize: 13 }}>
                    {oa.mailing_date && (
                      <span style={{ color: "var(--text-tertiary)" }}>Mailed: {oa.mailing_date}</span>
                    )}
                    {days !== null && (
                      <span style={{ color: days < 30 ? "var(--error)" : "var(--warning)", fontWeight: 600 }}>
                        <Clock style={{ width: 12, height: 12, display: "inline" }} /> {days}d remaining
                      </span>
                    )}
                    {oa.extracted_text && (
                      <span style={{ color: "var(--success)" }}>
                        <FileText style={{ width: 12, height: 12, display: "inline" }} /> Text extracted
                      </span>
                    )}
                    {!oa.extracted_text && (
                      <span style={{ color: "var(--text-tertiary)" }}>
                        ⚠ No PDF uploaded — upload to enable AI response
                      </span>
                    )}
                  </div>

                  {/* Expanded: AI Response */}
                  {isExpanded && responseText && (
                    <div style={{ marginTop: 16, borderTop: "1px solid var(--glass-border)", paddingTop: 16 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                        <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>
                          {generatingFor === oa.id ? "⚡ Generating Response..." : "✅ AI-Generated Response"}
                        </div>
                        {generatingFor !== oa.id && (
                          <button 
                            className="btn btn-secondary btn-sm"
                            onClick={() => {
                              const blob = new Blob([responseText], { type: "application/msword" });
                              const url = URL.createObjectURL(blob);
                              const a = document.createElement("a");
                              a.href = url;
                              a.download = `Office_Action_Response_${oa.action_type}.doc`;
                              a.click();
                              URL.revokeObjectURL(url);
                            }}
                          >
                            Download Word (.doc)
                          </button>
                        )}
                      </div>
                      <textarea
                        ref={responseRef}
                        style={{
                          width: "100%", minHeight: 400, padding: 16, fontSize: 13, lineHeight: 1.7,
                          color: "var(--text-primary)", background: "var(--bg-tertiary)", 
                          borderRadius: "var(--radius-md)", border: "1px solid var(--glass-border)",
                          resize: "vertical", outline: "none",
                          fontFamily: "'Inter', sans-serif",
                        }}
                        value={responseText}
                        onChange={(e) => setResponseText(e.target.value)}
                        disabled={generatingFor === oa.id}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}
