"use client";

import { Bell, Search } from "lucide-react";

interface HeaderProps {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}

export default function Header({ title, subtitle, actions }: HeaderProps) {
  return (
    <header className="main-header">
      <div>
        <h1 className="page-title">{title}</h1>
        {subtitle && (
          <p
            style={{
              fontSize: 13,
              color: "var(--text-tertiary)",
              marginTop: 2,
            }}
          >
            {subtitle}
          </p>
        )}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        {/* Search */}
        <div className="search-bar" style={{ width: 280 }}>
          <Search className="search-bar-icon" />
          <input
            className="input"
            placeholder="Search patents, families..."
            style={{ paddingLeft: 40, height: 38 }}
          />
        </div>

        {/* Notifications */}
        <button
          className="btn btn-ghost btn-icon"
          style={{ position: "relative" }}
        >
          <Bell style={{ width: 18, height: 18 }} />
          <span
            style={{
              position: "absolute",
              top: 6,
              right: 6,
              width: 8,
              height: 8,
              background: "var(--error)",
              borderRadius: "50%",
              border: "2px solid var(--bg-secondary)",
            }}
          />
        </button>

        {/* Actions slot */}
        {actions}
      </div>
    </header>
  );
}
