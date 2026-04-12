"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useUser, useClerk, OrganizationSwitcher, useOrganization } from "@clerk/nextjs";
import {
  LayoutDashboard,
  Search,
  Mail,
  ShieldAlert,
  FolderTree,
  PenTool,
  Scale,
  Settings,
  HelpCircle,
  LogOut,
  Building2,
  ShieldCheck
} from "lucide-react";

const navigation = [
  {
    section: "Overview",
    items: [
      { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
      { name: "Portfolio", href: "/dashboard/portfolio", icon: FolderTree },
    ],
  },
  {
    section: "Prosecution",
    items: [
      { name: "Patent Drafting", href: "/dashboard/drafting", icon: PenTool },
      {
        name: "Office Actions",
        href: "/dashboard/office-actions",
        icon: Mail,
        badge: 3,
      },
      {
        name: "Prior Art Search",
        href: "/dashboard/prior-art",
        icon: Search,
      },
    ],
  },
  {
    section: "Intelligence",
    items: [
      {
        name: "Risk Analysis",
        href: "/dashboard/risk",
        icon: ShieldAlert,
      },
      {
        name: "Due Diligence",
        href: "/dashboard/due-diligence",
        icon: Scale,
      },
    ],
  },
  {
    section: "System",
    items: [
      { name: "Settings", href: "/dashboard/settings", icon: Settings },
      { name: "Help & Docs", href: "/dashboard/help", icon: HelpCircle },
    ],
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user } = useUser();
  const { signOut } = useClerk();
  const { organization } = useOrganization();

  // Show Admin link if the active organization is "box mation"
  const isAdmin = organization?.name?.toLowerCase().includes("box mation");

  const initials = user?.firstName && user?.lastName
    ? `${user.firstName[0]}${user.lastName[0]}`
    : user?.emailAddresses?.[0]?.emailAddress?.substring(0, 2).toUpperCase() || "??";
  const displayName = user?.fullName || user?.emailAddresses?.[0]?.emailAddress || "User";

  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="sidebar-header">
        <div className="sidebar-logo">IQ</div>
        <span className="sidebar-title">PatentIQ</span>
      </div>

      {/* Organization Switcher */}
      <div style={{ padding: "0 12px 20px", borderBottom: "1px solid var(--glass-border)", marginBottom: 12 }}>
        <OrganizationSwitcher
          hidePersonal
          afterCreateOrganizationUrl="/dashboard"
          afterSelectOrganizationUrl="/dashboard"
          appearance={{
            elements: {
              rootBox: { width: "100%", display: "flex", justifyContent: "center", alignItems: "center" },
              organizationSwitcherTrigger: {
                width: "100%",
                padding: "8px 12px",
                borderRadius: "var(--radius-md)",
                background: "var(--bg-tertiary)",
                border: "1px solid var(--glass-border)",
                color: "var(--text-primary)",
                "&:hover": {
                  background: "var(--bg-hover)",
                },
              },
              organizationPreviewTextContainer: {
                color: "var(--text-primary)",
              },
              organizationSwitcherTriggerIcon: {
                color: "var(--text-tertiary)",
              },
            },
          }}
        />
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        {navigation.map((section) => (
          <div key={section.section} className="nav-section">
            <div className="nav-section-label">{section.section}</div>
            {section.items.map((item) => {
              const isActive =
                pathname === item.href ||
                (item.href !== "/dashboard" &&
                  pathname.startsWith(item.href));

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`nav-item ${isActive ? "active" : ""}`}
                >
                  <item.icon className="nav-item-icon" />
                  <span>{item.name}</span>
                  {item.badge && (
                    <span className="nav-badge">{item.badge}</span>
                  )}
                </Link>
              );
            })}
          </div>
        ))}

        {/* Admin Section (Conditional) */}
        {isAdmin && (
          <div className="nav-section" style={{ marginTop: 20 }}>
            <div className="nav-section-label" style={{ color: "var(--brand-400)" }}>Platform Management</div>
            <Link
              href="/dashboard/admin"
              className={`nav-item ${pathname === "/dashboard/admin" ? "active" : ""}`}
              style={{ background: pathname === "/dashboard/admin" ? "var(--brand-500)20" : "transparent" }}
            >
              <ShieldCheck className="nav-item-icon" style={{ color: "var(--brand-400)" }} />
              <span style={{ color: "var(--brand-200)" }}>Admin Control</span>
            </Link>
          </div>
        )}
      </nav>

      {/* Bottom section */}
      <div
        style={{
          padding: "16px 12px",
          borderTop: "1px solid var(--glass-border)",
        }}
      >
        <div
          className="nav-item"
          style={{
            background: "var(--bg-tertiary)",
            borderRadius: "var(--radius-md)",
          }}
        >
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: "50%",
              background:
                "linear-gradient(135deg, var(--brand-500), var(--accent-500))",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 13,
              fontWeight: 600,
              color: "white",
              flexShrink: 0,
            }}
          >
            {initials}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontSize: 13,
                fontWeight: 600,
                color: "var(--text-primary)",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {displayName}
            </div>
            <div
              style={{
                fontSize: 11,
                color: "var(--text-tertiary)",
              }}
            >
              Patent Attorney
            </div>
          </div>
          <button
            onClick={() => signOut()}
            className="btn btn-ghost btn-icon"
            style={{ flexShrink: 0, width: 28, height: 28 }}
            title="Sign out"
          >
            <LogOut style={{ width: 14, height: 14 }} />
          </button>
        </div>
      </div>
    </aside>
  );
}
