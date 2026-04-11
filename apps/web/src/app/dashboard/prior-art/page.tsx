"use client";

import { useState } from "react";
import Header from "@/components/Header";
import { api, SearchResult, ExternalPatent } from "@/lib/api";
import { getErrorMessage } from "@/lib/utils";
import {
  Search, Loader2, Globe, Database,
  Download, CheckCircle2, BookOpen, MapPin
} from "lucide-react";

type SearchMode = "local" | "uspto" | "google";

export default function PriorArtPage() {
  const [query, setQuery] = useState("");
  const [assignee, setAssignee] = useState("");
  const [patentNumber, setPatentNumber] = useState("");
  const [country, setCountry] = useState("");
  const [searchMode, setSearchMode] = useState<SearchMode>("uspto");
  const [searchType, setSearchType] = useState("keyword");

  const [localResults, setLocalResults] = useState<SearchResult[]>([]);
  const [externalResults, setExternalResults] = useState<ExternalPatent[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [importing, setImporting] = useState<string | null>(null);
  const [importedPatents, setImportedPatents] = useState<Set<string>>(new Set());

  async function handleSearch() {
    if (!query.trim() && !patentNumber.trim() && !assignee.trim()) return;
    setSearching(true);
    setSearched(true);

    try {
      if (searchMode === "uspto") {
        const res = await api.searchUSPTO(query, assignee || undefined, patentNumber || undefined);
        setExternalResults(res.patents);
        setLocalResults([]);
      } else if (searchMode === "google") {
        const res = await api.searchGooglePatents(query, assignee || undefined, country || undefined);
        setExternalResults(res.patents);
        setLocalResults([]);
      } else {
        const res = await api.searchPatents(query, searchType, 20);
        setLocalResults(res.results);
        setExternalResults([]);
      }
    } catch (err: unknown) {
      console.error("Search failed:", err);
      alert(getErrorMessage(err));
    } finally {
      setSearching(false);
    }
  }

  async function handleImport(patentNum: string) {
    setImporting(patentNum);
    try {
      await api.importPatent(patentNum);
      setImportedPatents((prev) => new Set(prev).add(patentNum));
    } catch (err: unknown) {
      alert(getErrorMessage(err));
    } finally {
      setImporting(null);
    }
  }

  return (
    <>
      <Header
        title="Prior Art Search"
        subtitle="Search across USPTO, Google Patents, and your portfolio"
      />
      <div className="page-content">
        {/* Search Mode Tabs */}
        <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
          <button
            className={`btn ${searchMode === "uspto" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setSearchMode("uspto")}
          >
            <Globe style={{ width: 16, height: 16 }} /> USPTO (US)
          </button>
          <button
            className={`btn ${searchMode === "google" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setSearchMode("google")}
          >
            <MapPin style={{ width: 16, height: 16 }} /> Google Patents (Intl)
          </button>
          <button
            className={`btn ${searchMode === "local" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setSearchMode("local")}
          >
            <Database style={{ width: 16, height: 16 }} /> My Portfolio
          </button>
        </div>

        {/* Search Box */}
        <div className="card-glass" style={{
          marginBottom: 32,
          background: "linear-gradient(135deg, rgba(99,102,241,0.06), rgba(139,92,246,0.04))",
          border: "1px solid rgba(99,102,241,0.15)",
        }}>
          <div style={{ marginBottom: 16 }}>
            <h3 style={{ fontSize: 16, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
              {searchMode === "uspto" ? "USPTO Patent Search" : searchMode === "google" ? "Google Patents — International" : "Portfolio Semantic Search"}
            </h3>
            <p style={{ fontSize: 13, color: "var(--text-secondary)" }}>
              {searchMode === "uspto"
                ? "Search the US Patent and Trademark Office database. Find any US patent by keywords, patent number, or assignee."
                : searchMode === "google"
                ? "Search Google Patents for international patents — covers US, EU, JP, WO, CN, KR, and 100+ patent offices worldwide."
                : "Search your imported portfolio using AI-powered semantic similarity (voyage-law-2 embeddings)."}
            </p>
          </div>

          <div className="form-group" style={{ marginBottom: 12 }}>
            <textarea
              className="input textarea"
              placeholder={
                searchMode === "local"
                  ? "Describe the invention concept for semantic search..."
                  : "Search by keywords: voice assistant natural language processing..."
              }
              style={{ minHeight: 100, fontSize: 14, lineHeight: 1.6 }}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && e.ctrlKey) handleSearch(); }}
            />
          </div>

          {(searchMode === "uspto" || searchMode === "google") && (
            <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
              {searchMode === "uspto" && (
                <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
                  <label className="label">Patent Number (optional)</label>
                  <input
                    className="input"
                    placeholder="e.g. 8977255 or US 8,977,255"
                    value={patentNumber}
                    onChange={(e) => setPatentNumber(e.target.value)}
                  />
                </div>
              )}
              <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
                <label className="label">Assignee (optional)</label>
                <input
                  className="input"
                  placeholder="e.g. Apple Inc."
                  value={assignee}
                  onChange={(e) => setAssignee(e.target.value)}
                />
              </div>
              {searchMode === "google" && (
                <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
                  <label className="label">Country Code (optional)</label>
                  <input
                    className="input"
                    placeholder="e.g. US, EP, JP, WO, CN"
                    value={country}
                    onChange={(e) => setCountry(e.target.value)}
                  />
                </div>
              )}
            </div>
          )}

          {searchMode === "local" && (
            <div style={{ marginBottom: 12 }}>
              <select className="input" style={{ width: 200 }} value={searchType} onChange={(e) => setSearchType(e.target.value)}>
                <option value="keyword">Keyword</option>
                <option value="semantic">Semantic</option>
                <option value="hybrid">Hybrid</option>
              </select>
            </div>
          )}

          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button className="btn btn-primary" onClick={handleSearch} disabled={searching}>
              {searching ? <Loader2 style={{ width: 16, height: 16, animation: "spin 1s linear infinite" }} /> : <Search style={{ width: 16, height: 16 }} />}
              {searching
                ? "Searching..."
                : searchMode === "local"
                ? "Search Portfolio"
                : searchMode === "google"
                ? "Search Google Patents"
                : "Search USPTO"}
            </button>
            <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--text-tertiary)" }}>Ctrl+Enter to search</span>
          </div>
        </div>

        {/* External Results (USPTO or Google Patents) */}
        {searched && (searchMode === "uspto" || searchMode === "google") && (
          <div className="card">
            <div className="card-header">
              <div>
                <div className="card-title">
                  {searchMode === "uspto" ? "USPTO Results" : "Google Patents Results"}
                </div>
                <div className="card-subtitle">
                  {searching ? "Searching..." : `${externalResults.length} patents found`}
                </div>
              </div>
            </div>

            {searching ? (
              <div style={{ display: "flex", justifyContent: "center", padding: 48 }}>
                <Loader2 style={{ width: 32, height: 32, color: "var(--brand-500)", animation: "spin 1s linear infinite" }} />
              </div>
            ) : externalResults.length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                {externalResults.map((p, idx) => (
                  <div key={`${p.patent_number}-${idx}`} style={{
                    padding: 20, background: "var(--bg-tertiary)", borderRadius: "var(--radius-md)",
                    border: "1px solid var(--glass-border)",
                  }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                        <BookOpen style={{ width: 16, height: 16, color: "var(--brand-400)" }} />
                        <span style={{ fontSize: 14, fontWeight: 700, color: "var(--brand-300)" }}>
                          {p.patent_number.startsWith("US") ? p.patent_number : `${p.patent_number}`}
                        </span>
                        <span className="badge badge-granted">{p.type || "utility"}</span>
                        {p.num_claims > 0 && (
                          <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>{p.num_claims} claims</span>
                        )}
                        {p.assignee && (
                          <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>· {p.assignee}</span>
                        )}
                        {p.source === "google_patents" && (
                          <span style={{
                            fontSize: 10, padding: "2px 6px", borderRadius: 8,
                            background: "rgba(34,197,94,0.1)", color: "var(--success)",
                          }}>Google Patents</span>
                        )}
                      </div>
                      <div style={{ display: "flex", gap: 8 }}>
                        {importedPatents.has(p.patent_number) ? (
                          <button className="btn btn-ghost btn-sm" disabled>
                            <CheckCircle2 style={{ width: 14, height: 14, color: "var(--success)" }} /> Imported
                          </button>
                        ) : (
                          <button
                            className="btn btn-primary btn-sm"
                            onClick={() => handleImport(p.patent_number)}
                            disabled={importing === p.patent_number}
                          >
                            {importing === p.patent_number ? (
                              <Loader2 style={{ width: 14, height: 14, animation: "spin 1s linear infinite" }} />
                            ) : (
                              <Download style={{ width: 14, height: 14 }} />
                            )}
                            Import
                          </button>
                        )}
                      </div>
                    </div>

                    <div style={{ fontSize: 15, fontWeight: 600, color: "var(--text-primary)", marginBottom: 8 }}>
                      {p.title || "Untitled Patent"}
                    </div>

                    {p.abstract && (
                      <div style={{
                        fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.6,
                        padding: "10px 14px", background: "var(--bg-secondary)",
                        borderRadius: "var(--radius-sm)", borderLeft: "3px solid var(--brand-500)",
                      }}>
                        {p.abstract.substring(0, 400)}{p.abstract.length > 400 ? "..." : ""}
                      </div>
                    )}

                    <div style={{ marginTop: 8, fontSize: 12, color: "var(--text-tertiary)" }}>
                      {p.date ? `Date: ${p.date}` : ""}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ textAlign: "center", padding: 48, color: "var(--text-tertiary)" }}>
                No patents found. Try different keywords or search by patent number.
              </div>
            )}
          </div>
        )}

        {/* Local Portfolio Results */}
        {searched && searchMode === "local" && (
          <div className="card">
            <div className="card-header">
              <div>
                <div className="card-title">Portfolio Results</div>
                <div className="card-subtitle">
                  {searching ? "Searching..." : `${localResults.length} matches found`}
                </div>
              </div>
            </div>
            {searching ? (
              <div style={{ display: "flex", justifyContent: "center", padding: 48 }}>
                <Loader2 style={{ width: 32, height: 32, color: "var(--brand-500)", animation: "spin 1s linear infinite" }} />
              </div>
            ) : localResults.length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                {localResults.map((r, idx) => (
                  <div key={`${r.patent_id}-${idx}`} style={{
                    padding: 20, background: "var(--bg-tertiary)",
                    borderRadius: "var(--radius-md)", border: "1px solid var(--glass-border)",
                  }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--brand-300)" }}>{r.application_number}</span>
                        <span className={`badge ${r.status === "granted" ? "badge-granted" : r.status === "abandoned" ? "badge-abandoned" : "badge-pending"}`}>
                          {r.status}
                        </span>
                      </div>
                      <div style={{
                        padding: "4px 10px", borderRadius: 20, fontSize: 13, fontWeight: 700,
                        background: r.score >= 0.9 ? "rgba(239,68,68,0.1)" : r.score >= 0.5 ? "rgba(245,158,11,0.1)" : "rgba(34,197,94,0.1)",
                        color: r.score >= 0.9 ? "var(--error)" : r.score >= 0.5 ? "var(--warning)" : "var(--success)",
                      }}>
                        {(r.score * 100).toFixed(0)}% match
                      </div>
                    </div>
                    <div style={{ fontSize: 15, fontWeight: 600, color: "var(--text-primary)", marginBottom: 8 }}>{r.title}</div>
                    {r.matched_text && (
                      <div style={{
                        fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.6,
                        fontStyle: "italic", padding: "10px 14px", background: "var(--bg-secondary)",
                        borderRadius: "var(--radius-sm)", borderLeft: "3px solid var(--brand-500)",
                      }}>
                        {r.matched_text}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ textAlign: "center", padding: 48, color: "var(--text-tertiary)" }}>
                No matches found in your portfolio.
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}
