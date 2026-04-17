"use client";

import { useState, useEffect } from "react";
import { Globe, AlertTriangle, CheckCircle2 } from "lucide-react";

interface JurisdictionSelectorProps {
  value: string | null;
  onChange: (jurisdiction: string | null) => void;
  firmId?: string;
  token?: string;
  compact?: boolean;
}

interface JurisdictionInfo {
  jurisdiction: string;
  source_count: number;
  total_chunks: number;
}

const ALL_JURISDICTIONS = [
  { code: "USPTO", label: "USPTO (United States)" },
  { code: "EPO", label: "EPO (European)" },
  { code: "JPO", label: "JPO (Japan)" },
  { code: "CNIPA", label: "CNIPA (China)" },
  { code: "IP_AUSTRALIA", label: "IP Australia" },
  { code: "WIPO", label: "WIPO (International)" },
];

const API_URL = process.env.NEXT_PUBLIC_API_URL?.trim().replace(/\/$/, "") || "";

export default function JurisdictionSelector({
  value,
  onChange,
  token,
  compact = false,
}: JurisdictionSelectorProps) {
  const [availableJurisdictions, setAvailableJurisdictions] = useState<JurisdictionInfo[]>([]);
  const [status, setStatus] = useState<{
    source_count: number;
    total_chunks: number;
    has_sources: boolean;
    is_stale: boolean;
  } | null>(null);
  const [loading, setLoading] = useState(false);

  // Fetch available jurisdictions on mount
  useEffect(() => {
    async function fetchJurisdictions() {
      try {
        const res = await fetch(`${API_URL}/api/v1/knowledge-base/jurisdictions`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (res.ok) {
          const data = await res.json();
          setAvailableJurisdictions(data);
        }
      } catch {
        // Silently fail — selector still works without source counts
      }
    }
    fetchJurisdictions();
  }, [token]);

  // Fetch status when jurisdiction changes
  useEffect(() => {
    if (!value) {
      setStatus(null);
      return;
    }

    async function fetchStatus() {
      setLoading(true);
      try {
        const res = await fetch(
          `${API_URL}/api/v1/knowledge-base/jurisdictions/${value}/status`,
          { headers: token ? { Authorization: `Bearer ${token}` } : {} }
        );
        if (res.ok) {
          setStatus(await res.json());
        }
      } catch {
        setStatus(null);
      } finally {
        setLoading(false);
      }
    }
    fetchStatus();
  }, [value, token]);

  const getSourceCount = (code: string): number => {
    const j = availableJurisdictions.find((j) => j.jurisdiction === code);
    return j?.source_count ?? 0;
  };

  return (
    <div
      id="jurisdiction-selector"
      style={{
        display: "flex",
        alignItems: compact ? "center" : "flex-start",
        gap: compact ? 8 : 12,
        flexDirection: compact ? "row" : "column",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, width: compact ? "auto" : "100%" }}>
        <Globe style={{ width: 16, height: 16, color: "var(--brand-400)", flexShrink: 0 }} />
        <select
          id="jurisdiction-dropdown"
          value={value || ""}
          onChange={(e) => onChange(e.target.value || null)}
          style={{
            flex: 1,
            padding: "6px 10px",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--glass-border)",
            background: "var(--bg-tertiary)",
            color: "var(--text-primary)",
            fontSize: 13,
            cursor: "pointer",
            minWidth: compact ? 160 : 200,
          }}
        >
          <option value="">No jurisdiction (unrestricted AI)</option>
          {ALL_JURISDICTIONS.map((j) => {
            const count = getSourceCount(j.code);
            return (
              <option key={j.code} value={j.code}>
                {j.label} {count > 0 ? `(${count} sources)` : ""}
              </option>
            );
          })}
        </select>
      </div>

      {/* Status indicator */}
      {value && !loading && status && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            fontSize: 12,
            padding: "4px 8px",
            borderRadius: "var(--radius-sm)",
            background: status.has_sources
              ? "rgba(16, 185, 129, 0.1)"
              : "rgba(245, 158, 11, 0.1)",
            border: `1px solid ${
              status.has_sources
                ? "rgba(16, 185, 129, 0.3)"
                : "rgba(245, 158, 11, 0.3)"
            }`,
            color: status.has_sources
              ? "rgb(16, 185, 129)"
              : "rgb(245, 158, 11)",
            whiteSpace: "nowrap",
          }}
        >
          {status.has_sources ? (
            <>
              <CheckCircle2 style={{ width: 12, height: 12 }} />
              <span>
                {status.source_count} source{status.source_count !== 1 ? "s" : ""} active
                {status.is_stale && " ⚠ stale"}
              </span>
            </>
          ) : (
            <>
              <AlertTriangle style={{ width: 12, height: 12 }} />
              <span>No sources — AI is unrestricted</span>
            </>
          )}
        </div>
      )}
    </div>
  );
}
