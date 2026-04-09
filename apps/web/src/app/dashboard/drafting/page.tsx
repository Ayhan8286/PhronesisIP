"use client";

import { useEffect, useState, useRef } from "react";
import Header from "@/components/Header";
import { api, Draft } from "@/lib/api";
import {
  Sparkles, Loader2, FileText, Upload, Save, PenTool, Plus
} from "lucide-react";

export default function DraftingPage() {
  const [description, setDescription] = useState("");
  const [techField, setTechField] = useState("");
  const [claimStyle, setClaimStyle] = useState("apparatus");
  const [specContext, setSpecContext] = useState("");

  const [generating, setGenerating] = useState(false);
  const [draftText, setDraftText] = useState("");
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [uploadingSpec, setUploadingSpec] = useState(false);
  const [specUploaded, setSpecUploaded] = useState(false);

  const fileRef = useRef<HTMLInputElement>(null);
  const outputRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.listDrafts().then(setDrafts).catch(console.error);
  }, []);

  async function handleUploadSpec(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingSpec(true);
    try {
      const result = await api.uploadSpec(file);
      setSpecContext(result.extracted_text);
      setSpecUploaded(true);
    } catch (err: any) {
      alert(err.message || "Upload failed");
    } finally {
      setUploadingSpec(false);
    }
  }

  async function handleGenerate() {
    if (!description.trim()) return;
    setGenerating(true);
    setDraftText("");

    try {
      await api.generateDraft(
        {
          description,
          technical_field: techField,
          claim_style: claimStyle,
          spec_context: specContext || undefined,
        },
        (chunk) => {
          setDraftText((prev) => prev + chunk);
          if (outputRef.current) outputRef.current.scrollTop = outputRef.current.scrollHeight;
        },
        () => {
          setGenerating(false);
          // Refresh drafts list
          api.listDrafts().then(setDrafts).catch(console.error);
        },
      );
    } catch (err: any) {
      alert(err.message || "Generation failed");
      setGenerating(false);
    }
  }

  return (
    <>
      <Header
        title="Patent Drafting"
        subtitle="AI-assisted patent application drafting"
        actions={
          <button className="btn btn-secondary">
            <Plus style={{ width: 16, height: 16 }} /> Blank Draft
          </button>
        }
      />
      <div className="page-content">
        {/* Generator */}
        <div className="card-glass" style={{
          marginBottom: 32,
          background: "linear-gradient(135deg, rgba(99,102,241,0.06), rgba(139,92,246,0.04))",
          border: "1px solid rgba(99,102,241,0.15)",
        }}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>
            <div style={{
              width: 48, height: 48, borderRadius: "var(--radius-lg)",
              background: "linear-gradient(135deg, var(--brand-500), var(--accent-500))",
              display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
            }}>
              <PenTool style={{ width: 24, height: 24, color: "white" }} />
            </div>
            <div style={{ flex: 1 }}>
              <h3 style={{ fontSize: 16, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
                AI Patent Draft Generator
              </h3>
              <p style={{ fontSize: 14, color: "var(--text-secondary)", lineHeight: 1.6, marginBottom: 16 }}>
                Describe the invention. Optionally upload engineering specs or prior art.
                AI generates a complete USPTO-format patent application with claims.
              </p>

              <div className="form-group" style={{ marginBottom: 12 }}>
                <label className="label">Invention Description *</label>
                <textarea
                  className="input textarea"
                  placeholder="Describe the invention in detail. What problem does it solve? How does it work? What are the key technical features?"
                  style={{ minHeight: 120 }}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>

              <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
                <div className="form-group" style={{ flex: 2, marginBottom: 0 }}>
                  <label className="label">Technical Field</label>
                  <input className="input" placeholder="e.g. Machine Learning, Medical Devices" value={techField} onChange={(e) => setTechField(e.target.value)} />
                </div>
                <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
                  <label className="label">Claim Style</label>
                  <select className="input" value={claimStyle} onChange={(e) => setClaimStyle(e.target.value)}>
                    <option value="apparatus">Apparatus</option>
                    <option value="method">Method</option>
                    <option value="system">System</option>
                    <option value="composition">Composition</option>
                  </select>
                </div>
              </div>

              {/* Upload Spec */}
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                <input ref={fileRef} type="file" accept=".pdf,.docx" style={{ display: "none" }} onChange={handleUploadSpec} />
                <button className="btn btn-secondary" onClick={() => fileRef.current?.click()} disabled={uploadingSpec}>
                  {uploadingSpec ? <Loader2 style={{ width: 16, height: 16, animation: "spin 1s linear infinite" }} /> : <Upload style={{ width: 16, height: 16 }} />}
                  {uploadingSpec ? "Extracting..." : "Upload Engineering Spec (PDF/Word)"}
                </button>
                {specUploaded && (
                  <span style={{ fontSize: 13, color: "var(--success)" }}>
                    ✓ Spec uploaded ({(specContext.length / 1000).toFixed(0)}K chars extracted)
                  </span>
                )}
              </div>

              <button className="btn btn-primary" onClick={handleGenerate} disabled={generating || !description.trim()}>
                {generating ? <Loader2 style={{ width: 16, height: 16, animation: "spin 1s linear infinite" }} /> : <Sparkles style={{ width: 16, height: 16 }} />}
                {generating ? "Generating..." : "Generate Draft"}
              </button>
            </div>
          </div>
        </div>

        {/* Generated Draft Output */}
        {draftText && (
          <div className="card" style={{ marginBottom: 24, display: "flex", flexDirection: "column" }}>
            <div className="card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div className="card-title">
                {generating ? "⚡ Generating Patent Draft..." : "✅ Patent Draft Ready for Review"}
              </div>
              {!generating && (
                <button 
                  className="btn btn-secondary" 
                  onClick={() => {
                    const blob = new Blob([draftText], { type: "application/msword" });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = "Patent_Application_Draft.doc";
                    a.click();
                    URL.revokeObjectURL(url);
                  }}
                >
                  <Save style={{ width: 16, height: 16 }} /> Download Word (.doc)
                </button>
              )}
            </div>
            <textarea
              ref={outputRef as any}
              style={{
                width: "100%", minHeight: 600, padding: 16, fontSize: 13, lineHeight: 1.7,
                color: "var(--text-primary)", background: "var(--bg-primary)",
                border: "none", resize: "vertical", outline: "none",
                fontFamily: "'Inter', sans-serif",
              }}
              value={draftText}
              onChange={(e) => setDraftText(e.target.value)}
              disabled={generating}
            />
          </div>
        )}

        {/* Saved Drafts */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">Your Drafts</div>
            <div className="card-subtitle">{drafts.length} saved draft{drafts.length !== 1 ? "s" : ""}</div>
          </div>
          {drafts.length === 0 ? (
            <div style={{ textAlign: "center", padding: 32, color: "var(--text-tertiary)" }}>
              <FileText style={{ width: 36, height: 36, margin: "0 auto 8px", opacity: 0.5 }} />
              <p>No drafts yet. Generate your first patent draft above.</p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {drafts.map((d) => (
                <div key={d.id} style={{
                  padding: "14px 18px", background: "var(--bg-tertiary)",
                  borderRadius: "var(--radius-md)", border: "1px solid var(--glass-border)",
                  cursor: "pointer", display: "flex", alignItems: "center", gap: 12,
                }}>
                  <FileText style={{ width: 18, height: 18, color: "var(--brand-400)" }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>{d.title}</div>
                    <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
                      v{d.version} · {d.draft_type} · {new Date(d.created_at).toLocaleDateString()}
                    </div>
                  </div>
                  <span className={`badge ${d.status === "finalized" ? "badge-granted" : "badge-pending"}`}>{d.status}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
