"use client";

import Header from "@/components/Header";

export default function HelpPage() {
  return (
    <>
      <Header title="Help & Docs" subtitle="Guides, FAQs, and support" />
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
            Add documentation links, onboarding, and contact/support details here.
          </div>
        </div>
      </div>
    </>
  );
}

