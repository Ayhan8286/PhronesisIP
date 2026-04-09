"use client";

import { useEffect, useState } from "react";
import Header from "@/components/Header";
import { api, Patent, PortfolioOverview, OfficeAction } from "@/lib/api";
import {
  FileText,
  CheckCircle2,
  Clock,
  AlertTriangle,
  ArrowUpRight,
  ArrowDownRight,
  Sparkles,
  FolderTree,
  Mail,
  Loader2,
} from "lucide-react";

const statusColors: Record<string, string> = {
  pending: "badge-pending",
  granted: "badge-granted",
  abandoned: "badge-abandoned",
  draft: "badge-draft",
};

export default function DashboardPage() {
  const [overview, setOverview] = useState<PortfolioOverview | null>(null);
  const [patents, setPatents] = useState<Patent[]>([]);
  const [officeActions, setOfficeActions] = useState<OfficeAction[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [ov, pl, oa] = await Promise.all([
          api.getOverview(),
          api.listPatents(1),
          api.listOfficeActions(),
        ]);
        setOverview(ov);
        setPatents(pl.patents);
        setOfficeActions(oa);
      } catch (err) {
        console.error("Failed to load dashboard:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <>
        <Header title="Dashboard" subtitle="Loading..." />
        <div
          className="page-content"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            minHeight: 400,
          }}
        >
          <Loader2
            style={{
              width: 32,
              height: 32,
              color: "var(--brand-500)",
              animation: "spin 1s linear infinite",
            }}
          />
        </div>
      </>
    );
  }

  const stats = [
    {
      label: "Total Patents",
      value: overview?.total_patents ?? 0,
      change: `${overview?.status_breakdown?.pending ?? 0} pending`,
      positive: true,
      icon: FileText,
      color: "var(--brand-500)",
    },
    {
      label: "Granted",
      value: overview?.status_breakdown?.granted ?? 0,
      change: "Issued patents",
      positive: true,
      icon: CheckCircle2,
      color: "var(--success)",
    },
    {
      label: "Patent Families",
      value: overview?.patent_families ?? 0,
      change: "Active families",
      positive: true,
      icon: FolderTree,
      color: "var(--info)",
    },
    {
      label: "Urgent Deadlines",
      value: overview?.urgent_deadlines ?? 0,
      change: `Next ${overview?.deadline_window_days ?? 30} days`,
      positive: (overview?.urgent_deadlines ?? 0) === 0,
      icon: AlertTriangle,
      color: "var(--error)",
    },
  ];

  const pendingOAs = officeActions.filter((oa) => oa.status === "pending");

  return (
    <>
      <Header
        title="Dashboard"
        subtitle="Patent portfolio overview &amp; key metrics"
        actions={
          <a href="/dashboard/drafting" className="btn btn-primary">
            <Sparkles style={{ width: 16, height: 16 }} />
            New Draft
          </a>
        }
      />

      <div className="page-content">
        {/* Stats Grid */}
        <div className="stats-grid stagger-children">
          {stats.map((stat) => (
            <div key={stat.label} className="stat-card">
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: 12,
                }}
              >
                <span className="stat-label">{stat.label}</span>
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: "var(--radius-md)",
                    background: `${stat.color}15`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <stat.icon
                    style={{ width: 18, height: 18, color: stat.color }}
                  />
                </div>
              </div>
              <div className="stat-value">{stat.value}</div>
              <div
                className={`stat-change ${stat.positive ? "positive" : "negative"}`}
              >
                {stat.positive ? (
                  <ArrowUpRight style={{ width: 14, height: 14 }} />
                ) : (
                  <ArrowDownRight style={{ width: 14, height: 14 }} />
                )}
                {stat.change}
              </div>
            </div>
          ))}
        </div>

        {/* Two-column layout */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 380px",
            gap: 24,
          }}
        >
          {/* Recent Patents Table */}
          <div className="card animate-in">
            <div className="card-header">
              <div>
                <div className="card-title">Recent Patents</div>
                <div className="card-subtitle">
                  Latest activity across your portfolio
                </div>
              </div>
              <a href="/dashboard/portfolio" className="btn btn-secondary btn-sm">
                View All
              </a>
            </div>

            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>Application</th>
                    <th>Title</th>
                    <th>Assignee</th>
                    <th>Status</th>
                    <th>Filed</th>
                  </tr>
                </thead>
                <tbody>
                  {patents.map((patent) => (
                    <tr key={patent.id} style={{ cursor: "pointer" }}>
                      <td>
                        <span
                          style={{
                            fontWeight: 600,
                            color: "var(--brand-300)",
                            fontSize: 13,
                          }}
                        >
                          {patent.application_number}
                        </span>
                      </td>
                      <td>
                        <span
                          style={{
                            color: "var(--text-primary)",
                            fontSize: 13,
                            display: "-webkit-box",
                            WebkitLineClamp: 1,
                            WebkitBoxOrient: "vertical",
                            overflow: "hidden",
                            maxWidth: 300,
                          }}
                        >
                          {patent.title}
                        </span>
                      </td>
                      <td style={{ fontSize: 13 }}>
                        {patent.assignee || "—"}
                      </td>
                      <td>
                        <span
                          className={`badge ${statusColors[patent.status] || "badge-pending"}`}
                        >
                          {patent.status}
                        </span>
                      </td>
                      <td style={{ fontSize: 13 }}>
                        {patent.filing_date || "—"}
                      </td>
                    </tr>
                  ))}
                  {patents.length === 0 && (
                    <tr>
                      <td colSpan={5} style={{ textAlign: "center", padding: 32, color: "var(--text-tertiary)" }}>
                        No patents yet. Add your first patent to get started.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Upcoming Deadlines */}
          <div className="card animate-in" style={{ animationDelay: "100ms" }}>
            <div className="card-header">
              <div>
                <div className="card-title">Pending Office Actions</div>
                <div className="card-subtitle">
                  {pendingOAs.length} requiring response
                </div>
              </div>
              <Mail
                style={{
                  width: 18,
                  height: 18,
                  color: "var(--text-tertiary)",
                }}
              />
            </div>

            <div
              style={{ display: "flex", flexDirection: "column", gap: 12 }}
            >
              {pendingOAs.map((oa) => {
                const daysLeft = oa.response_deadline
                  ? Math.ceil(
                      (new Date(oa.response_deadline).getTime() - new Date().getTime()) /
                        (1000 * 60 * 60 * 24)
                    )
                  : null;

                return (
                  <div
                    key={oa.id}
                    style={{
                      padding: "14px 16px",
                      background: "var(--bg-tertiary)",
                      borderRadius: "var(--radius-md)",
                      border: "1px solid var(--glass-border)",
                      cursor: "pointer",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        marginBottom: 6,
                      }}
                    >
                      <span
                        style={{
                          fontSize: 13,
                          fontWeight: 600,
                          color: "var(--brand-300)",
                        }}
                      >
                        {oa.action_type}
                      </span>
                      {daysLeft !== null && (
                        <span
                          style={{
                            fontSize: 12,
                            fontWeight: 600,
                            color:
                              daysLeft <= 14
                                ? "var(--error)"
                                : daysLeft <= 30
                                  ? "var(--warning)"
                                  : "var(--text-secondary)",
                            background:
                              daysLeft <= 14
                                ? "rgba(239,68,68,0.1)"
                                : daysLeft <= 30
                                  ? "rgba(245,158,11,0.1)"
                                  : "var(--bg-hover)",
                            padding: "2px 8px",
                            borderRadius: 8,
                          }}
                        >
                          {daysLeft}d left
                        </span>
                      )}
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        color: "var(--text-tertiary)",
                      }}
                    >
                      Due: {oa.response_deadline || "Not set"}
                    </div>
                  </div>
                );
              })}
              {pendingOAs.length === 0 && (
                <div style={{ textAlign: "center", padding: 24, color: "var(--text-tertiary)", fontSize: 13 }}>
                  No pending office actions
                </div>
              )}
            </div>

            <a
              href="/dashboard/office-actions"
              className="btn btn-secondary"
              style={{ width: "100%", marginTop: 16 }}
            >
              View All Office Actions
            </a>
          </div>
        </div>
      </div>
    </>
  );
}
