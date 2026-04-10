"use client";

import Header from "@/components/Header";

export default function SettingsPage() {
  return (
    <>
      <Header
        title="Settings"
        subtitle="Manage your account and workspace preferences"
      />
      <div className="page-content">
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Coming soon</div>
              <div className="card-subtitle">
                This page is a placeholder so the route exists in production.
              </div>
            </div>
          </div>
          <div style={{ padding: 20, color: "var(--text-secondary)", fontSize: 13 }}>
            Add settings panels here (profile, firm, integrations, API keys, billing).
          </div>
        </div>
      </div>
    </>
  );
}

