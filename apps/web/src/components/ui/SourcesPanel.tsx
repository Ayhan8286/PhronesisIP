"use client";

import { useState } from "react";
import { CheckCircle2, AlertTriangle, ChevronDown, ChevronUp, ExternalLink } from "lucide-react";

interface SourceUsed {
  title: string;
  section: string;
  jurisdiction: string;
  doc_type: string;
  score: number;
}

interface CitationValidation {
  is_valid: boolean;
  total_citations: number;
  valid_citations: string[];
  invalid_citations: string[];
  uncited_claims: string[];
  attorney_review_items: string[];
  warning: boolean;
}

interface SourcesPanelProps {
  sourcesUsed: SourceUsed[];
  hasLegalAuthority: boolean;
  jurisdiction: string;
  citationValidation?: CitationValidation;
  onViewChunks?: (sourceTitle: string) => void;
}

export default function SourcesPanel({
  sourcesUsed,
  hasLegalAuthority,
  jurisdiction,
  citationValidation,
  onViewChunks,
}: SourcesPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const [showUncited, setShowUncited] = useState(false);

  const reviewCount =
    (citationValidation?.invalid_citations?.length || 0) +
    (citationValidation?.attorney_review_items?.length || 0);

  return (
    <div
      id="sources-panel"
      style={{
        marginTop: 16,
        borderRadius: "var(--radius-lg)",
        border: "1px solid var(--glass-border)",
        background: "var(--bg-secondary)",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 16px",
          background: "transparent",
          border: "none",
          cursor: "pointer",
          color: "var(--text-primary)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {hasLegalAuthority ? (
            <CheckCircle2 style={{ width: 16, height: 16, color: "rgb(16, 185, 129)" }} />
          ) : (
            <AlertTriangle style={{ width: 16, height: 16, color: "rgb(245, 158, 11)" }} />
          )}
          <span style={{ fontSize: 13, fontWeight: 600 }}>
            {hasLegalAuthority
              ? `Generated using ${sourcesUsed.length} legal source${sourcesUsed.length !== 1 ? "s" : ""}`
              : "Generated without legal sources"}
          </span>
          <span
            style={{
              fontSize: 11,
              padding: "2px 6px",
              borderRadius: 4,
              background: "var(--bg-tertiary)",
              color: "var(--text-tertiary)",
            }}
          >
            {jurisdiction}
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {reviewCount > 0 && (
            <span
              style={{
                fontSize: 11,
                padding: "2px 8px",
                borderRadius: 10,
                background: "rgba(245, 158, 11, 0.15)",
                color: "rgb(245, 158, 11)",
                fontWeight: 600,
              }}
            >
              {reviewCount} need{reviewCount === 1 ? "s" : ""} review
            </span>
          )}
          {expanded ? (
            <ChevronUp style={{ width: 14, height: 14, color: "var(--text-tertiary)" }} />
          ) : (
            <ChevronDown style={{ width: 14, height: 14, color: "var(--text-tertiary)" }} />
          )}
        </div>
      </button>

      {/* Expanded Content */}
      {expanded && (
        <div
          style={{
            borderTop: "1px solid var(--glass-border)",
            padding: 16,
          }}
        >
          {/* Source List */}
          {hasLegalAuthority && sourcesUsed.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: "var(--text-tertiary)",
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  marginBottom: 8,
                }}
              >
                Legal Sources Used
              </div>
              {sourcesUsed.map((source, i) => (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "6px 8px",
                    borderRadius: "var(--radius-sm)",
                    background: "var(--bg-tertiary)",
                    marginBottom: 4,
                    fontSize: 12,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <CheckCircle2 style={{ width: 12, height: 12, color: "rgb(16, 185, 129)", flexShrink: 0 }} />
                    <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>
                      {source.title}
                      {source.section && ` — ${source.section}`}
                    </span>
                  </div>
                  {onViewChunks && (
                    <button
                      onClick={() => onViewChunks(source.title)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 4,
                        padding: "2px 6px",
                        borderRadius: 4,
                        border: "1px solid var(--glass-border)",
                        background: "transparent",
                        color: "var(--brand-400)",
                        fontSize: 10,
                        cursor: "pointer",
                      }}
                    >
                      <ExternalLink style={{ width: 10, height: 10 }} />
                      View
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Citation Validation */}
          {citationValidation && (
            <div style={{ marginBottom: 12 }}>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: "var(--text-tertiary)",
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  marginBottom: 8,
                }}
              >
                Citation Validation
              </div>
              <div
                style={{
                  padding: "8px 10px",
                  borderRadius: "var(--radius-sm)",
                  background: citationValidation.is_valid
                    ? "rgba(16, 185, 129, 0.08)"
                    : "rgba(245, 158, 11, 0.08)",
                  border: `1px solid ${
                    citationValidation.is_valid
                      ? "rgba(16, 185, 129, 0.2)"
                      : "rgba(245, 158, 11, 0.2)"
                  }`,
                  fontSize: 12,
                  color: "var(--text-secondary)",
                }}
              >
                <div>
                  {citationValidation.total_citations} citation
                  {citationValidation.total_citations !== 1 ? "s" : ""} found
                  {citationValidation.valid_citations.length > 0 &&
                    ` · ${citationValidation.valid_citations.length} verified`}
                </div>
                {citationValidation.invalid_citations.length > 0 && (
                  <div style={{ color: "rgb(245, 158, 11)", marginTop: 4 }}>
                    ⚠ {citationValidation.invalid_citations.length} citation
                    {citationValidation.invalid_citations.length !== 1 ? "s" : ""} not found
                    in uploaded sources
                  </div>
                )}
                {citationValidation.attorney_review_items.length > 0 && (
                  <div style={{ marginTop: 4, color: "var(--brand-300)" }}>
                    ⚡ {citationValidation.attorney_review_items.length} point
                    {citationValidation.attorney_review_items.length !== 1 ? "s" : ""} flagged
                    for attorney review
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Uncited Claims (expandable) */}
          {citationValidation &&
            citationValidation.uncited_claims.length > 0 && (
              <div>
                <button
                  onClick={() => setShowUncited(!showUncited)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                    background: "transparent",
                    border: "none",
                    color: "rgb(245, 158, 11)",
                    fontSize: 12,
                    cursor: "pointer",
                    padding: 0,
                    marginBottom: 4,
                  }}
                >
                  <AlertTriangle style={{ width: 12, height: 12 }} />
                  {citationValidation.uncited_claims.length} uncited legal statement
                  {citationValidation.uncited_claims.length !== 1 ? "s" : ""}
                  {showUncited ? " ▴" : " ▾"}
                </button>
                {showUncited && (
                  <div
                    style={{
                      fontSize: 11,
                      color: "var(--text-tertiary)",
                      padding: "8px 10px",
                      background: "var(--bg-tertiary)",
                      borderRadius: "var(--radius-sm)",
                      maxHeight: 200,
                      overflowY: "auto",
                    }}
                  >
                    {citationValidation.uncited_claims.map((claim, i) => (
                      <div
                        key={i}
                        style={{
                          padding: "4px 0",
                          borderBottom:
                            i < citationValidation.uncited_claims.length - 1
                              ? "1px solid var(--glass-border)"
                              : "none",
                        }}
                      >
                        &quot;{claim}&quot;
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

          {/* Disclaimer */}
          <div
            style={{
              marginTop: 12,
              padding: "8px 10px",
              borderRadius: "var(--radius-sm)",
              background: "var(--bg-tertiary)",
              fontSize: 10,
              color: "var(--text-tertiary)",
              lineHeight: 1.5,
              fontStyle: "italic",
            }}
          >
            Generated using provided legal sources only. This output requires
            attorney review before use. PhronesisIP and Box Mation accept no
            legal liability for outputs used without professional review.
          </div>
        </div>
      )}
    </div>
  );
}
