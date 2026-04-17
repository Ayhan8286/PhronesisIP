"use client";

import { AlertTriangle } from "lucide-react";

interface CitationWarningBannerProps {
  invalidCount: number;
  uncitedCount: number;
}

/**
 * Yellow warning banner shown above AI output when citation validation fails.
 * Displayed when the LLM references sources not in the uploaded materials
 * or makes legal assertions without citations.
 */
export default function CitationWarningBanner({
  invalidCount,
  uncitedCount,
}: CitationWarningBannerProps) {
  if (invalidCount === 0 && uncitedCount === 0) return null;

  return (
    <div
      id="citation-warning-banner"
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 10,
        padding: "10px 14px",
        borderRadius: "var(--radius-md)",
        background: "rgba(245, 158, 11, 0.1)",
        border: "1px solid rgba(245, 158, 11, 0.3)",
        marginBottom: 12,
      }}
    >
      <AlertTriangle
        style={{
          width: 16,
          height: 16,
          color: "rgb(245, 158, 11)",
          flexShrink: 0,
          marginTop: 1,
        }}
      />
      <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>
        {invalidCount > 0 && (
          <div>
            <strong style={{ color: "rgb(245, 158, 11)" }}>
              {invalidCount} citation{invalidCount !== 1 ? "s" : ""}
            </strong>{" "}
            reference sources not found in your uploaded legal materials.
          </div>
        )}
        {uncitedCount > 0 && (
          <div style={{ marginTop: invalidCount > 0 ? 4 : 0 }}>
            <strong style={{ color: "rgb(245, 158, 11)" }}>
              {uncitedCount} legal statement{uncitedCount !== 1 ? "s" : ""}
            </strong>{" "}
            detected without source citations.
          </div>
        )}
        <div style={{ marginTop: 4, color: "var(--text-tertiary)", fontStyle: "italic" }}>
          Attorney review required before use.
        </div>
      </div>
    </div>
  );
}
