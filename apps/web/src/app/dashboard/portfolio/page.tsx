"use client";

import { useEffect, useState } from "react";
import Header from "@/components/Header";
import { api, PatentFamily, Patent, OfficeAction } from "@/lib/api";
import {
  FolderTree, Plus, Download, ChevronRight, FileText,
  Loader2, ShieldCheck, AlertTriangle, Clock, TrendingUp,
  ChevronDown
} from "lucide-react";

export default function PortfolioPage() {
  const [families, setFamilies] = useState<PatentFamily[]>([]);
  const [patents, setPatents] = useState<Patent[]>([]);
  const [upcomingDeadlinesState, setUpcomingDeadlinesState] = useState<Array<OfficeAction & { daysRemaining: number }>>([]);
  const [loading, setLoading] = useState(true);
  const [expandedFamily, setExpandedFamily] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.listFamilies(),
      api.listPatents(1),
      api.listOfficeActions(),
    ])
      .then(([f, p, oa]) => {
        setFamilies(f);
        setPatents(p.patents);
        const now = Date.now();
        setUpcomingDeadlinesState(
          oa
            .filter((item) => item.response_deadline && item.status === "pending")
            .map((item) => ({
              ...item,
              daysRemaining: Math.ceil(
                (new Date(item.response_deadline!).getTime() - now) / (1000 * 60 * 60 * 24)
              ),
            }))
            .filter((item) => item.daysRemaining > 0)
            .sort((a, b) => a.daysRemaining - b.daysRemaining)
        );
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const totalPatents = patents.length;
  const grantedCount = patents.filter((p) => p.status === "granted").length;
  const pendingCount = patents.filter((p) => p.status === "pending").length;

  // Calculate upcoming deadlines
  const upcomingDeadlines = upcomingDeadlinesState;

  // Unfiled patents (not in any family)
  const familiedPatentIds = new Set(
    families.flatMap((f) => (f.patents || []).map((p) => p.id))
  );
  const unfiledPatents = patents.filter((p) => !familiedPatentIds.has(p.id));

  return (
    <>
      <Header
        title="Portfolio"
        subtitle="Manage patent families, track deadlines, and monitor portfolio health"
        actions={
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-secondary btn-sm">
              <Download style={{ width: 14, height: 14 }} />
              Export
            </button>
            <button className="btn btn-primary btn-sm">
              <Plus style={{ width: 14, height: 14 }} />
              New Family
            </button>
          </div>
        }
      />

      <div className="page-content">
        {/* Stats Grid */}
        <div className="stats-grid stagger-children" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
          <div className="stat-card">
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
              <FileText style={{ width: 18, height: 18, color: "var(--brand-400)" }} />
              <span className="stat-label" style={{ marginBottom: 0 }}>Total Patents</span>
            </div>
            <div className="stat-value">{totalPatents}</div>
            <div className="stat-change positive">{families.length} families</div>
          </div>
          <div className="stat-card">
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
              <ShieldCheck style={{ width: 18, height: 18, color: "var(--success)" }} />
              <span className="stat-label" style={{ marginBottom: 0 }}>Granted</span>
            </div>
            <div className="stat-value">{grantedCount}</div>
            <div className="stat-change positive">
              {totalPatents > 0 ? Math.round((grantedCount / totalPatents) * 100) : 0}% of portfolio
            </div>
          </div>
          <div className="stat-card">
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
              <TrendingUp style={{ width: 18, height: 18, color: "var(--warning)" }} />
              <span className="stat-label" style={{ marginBottom: 0 }}>Pending</span>
            </div>
            <div className="stat-value">{pendingCount}</div>
            <div className="stat-change positive">In prosecution</div>
          </div>
          <div className="stat-card">
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
              <Clock style={{ width: 18, height: 18, color: "var(--error)" }} />
              <span className="stat-label" style={{ marginBottom: 0 }}>Upcoming Deadlines</span>
            </div>
            <div className="stat-value">{upcomingDeadlines.length}</div>
            <div className="stat-change negative">
              {upcomingDeadlines.length > 0
                ? `Next in ${upcomingDeadlines[0].daysRemaining}d`
                : "None"}
            </div>
          </div>
        </div>

        {/* Deadlines Alert */}
        {upcomingDeadlines.length > 0 && (
          <div className="card" style={{ marginBottom: 24 }}>
            <div className="card-header">
              <div className="card-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <AlertTriangle style={{ width: 18, height: 18, color: "var(--warning)" }} />
                Upcoming Deadlines
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {upcomingDeadlines.slice(0, 5).map((oa) => (
                <div key={oa.id} style={{
                  padding: "12px 16px", background: "var(--bg-tertiary)",
                  borderRadius: "var(--radius-md)",
                  borderLeft: `3px solid ${oa.daysRemaining < 30 ? "var(--error)" : "var(--warning)"}`,
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                }}>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>
                      {oa.action_type}
                    </div>
                    <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
                      Due: {oa.response_deadline}
                    </div>
                  </div>
                  <span style={{
                    padding: "4px 12px", borderRadius: 20, fontSize: 13, fontWeight: 700,
                    background: oa.daysRemaining < 30 ? "rgba(239,68,68,0.1)" : "rgba(245,158,11,0.1)",
                    color: oa.daysRemaining < 30 ? "var(--error)" : "var(--warning)",
                  }}>
                    {oa.daysRemaining}d remaining
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {loading ? (
          <div style={{ display: "flex", justifyContent: "center", padding: 64 }}>
            <Loader2 style={{ width: 32, height: 32, color: "var(--brand-500)", animation: "spin 1s linear infinite" }} />
          </div>
        ) : (
          <>
            {/* Patent Families */}
            <div className="card" style={{ marginBottom: 24 }}>
              <div className="card-header">
                <div className="card-title">Patent Families</div>
                <div className="card-subtitle">{families.length} families</div>
              </div>

              {families.length === 0 ? (
                <div style={{ textAlign: "center", padding: 48, color: "var(--text-tertiary)" }}>
                  <FolderTree style={{ width: 36, height: 36, margin: "0 auto 8px", opacity: 0.5 }} />
                  <p>No patent families yet. Create one to organize your patents.</p>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  {families.map((family) => {
                    const isExpanded = expandedFamily === family.id;
                    return (
                      <div key={family.id} style={{
                        background: "var(--bg-tertiary)", borderRadius: "var(--radius-md)",
                        border: `1px solid ${isExpanded ? "var(--brand-500)" : "var(--glass-border)"}`,
                        overflow: "hidden",
                      }}>
                        <div
                          onClick={() => setExpandedFamily(isExpanded ? null : family.id)}
                          style={{
                            padding: "16px 20px", cursor: "pointer",
                            display: "flex", alignItems: "center", gap: 12,
                          }}
                        >
                          <div style={{
                            width: 40, height: 40, borderRadius: "var(--radius-md)",
                            background: "rgba(99,102,241,0.1)",
                            display: "flex", alignItems: "center", justifyContent: "center",
                          }}>
                            <FolderTree style={{ width: 20, height: 20, color: "var(--brand-400)" }} />
                          </div>
                          <div style={{ flex: 1 }}>
                            <div style={{ fontSize: 15, fontWeight: 600, color: "var(--text-primary)" }}>
                              {family.family_name}
                            </div>
                            <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 2 }}>
                              {family.patents?.length || 0} patents · Created {new Date(family.created_at).toLocaleDateString()}
                            </div>
                          </div>
                          <span className="badge badge-granted">active</span>
                          {isExpanded ? (
                            <ChevronDown style={{ width: 18, height: 18, color: "var(--text-muted)" }} />
                          ) : (
                            <ChevronRight style={{ width: 18, height: 18, color: "var(--text-muted)" }} />
                          )}
                        </div>

                        {/* Expanded: show family patents */}
                        {isExpanded && family.patents && family.patents.length > 0 && (
                          <div style={{ padding: "0 20px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
                            {family.patents.map((p) => (
                              <div key={p.id} style={{
                                padding: "10px 14px", background: "var(--bg-secondary)",
                                borderRadius: "var(--radius-sm)", display: "flex", alignItems: "center", gap: 10,
                              }}>
                                <FileText style={{ width: 14, height: 14, color: "var(--brand-400)" }} />
                                <span style={{ fontSize: 13, fontWeight: 600, color: "var(--brand-300)" }}>
                                  {p.patent_number || p.application_number}
                                </span>
                                <span style={{ fontSize: 13, color: "var(--text-secondary)", flex: 1 }}>
                                  {p.title}
                                </span>
                                <span className={`badge ${p.status === "granted" ? "badge-granted" : p.status === "abandoned" ? "badge-abandoned" : "badge-pending"}`}>
                                  {p.status}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Unfiled Patents */}
            {unfiledPatents.length > 0 && (
              <div className="card">
                <div className="card-header">
                  <div className="card-title">Unfiled Patents</div>
                  <div className="card-subtitle">
                    {unfiledPatents.length} patents not assigned to a family
                  </div>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {unfiledPatents.map((p) => (
                    <div key={p.id} style={{
                      padding: "12px 16px", background: "var(--bg-tertiary)",
                      borderRadius: "var(--radius-md)", display: "flex", alignItems: "center", gap: 10,
                    }}>
                      <FileText style={{ width: 16, height: 16, color: "var(--text-tertiary)" }} />
                      <span style={{ fontSize: 13, fontWeight: 600, color: "var(--brand-300)" }}>
                        {p.patent_number || p.application_number}
                      </span>
                      <span style={{ fontSize: 13, color: "var(--text-secondary)", flex: 1 }}>
                        {p.title}
                      </span>
                      <span className={`badge ${p.status === "granted" ? "badge-granted" : p.status === "abandoned" ? "badge-abandoned" : "badge-pending"}`}>
                        {p.status}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}
