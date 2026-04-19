"use client";

import Link from "next/link";
import { 
  Shield, 
  Search, 
  FileText, 
  Zap, 
  CheckCircle2, 
  ArrowRight,
  ChevronRight,
  Globe,
  Scale
} from "lucide-react";
import Header from "@/components/Header";

export default function LandingPage() {
  return (
    <div style={{ background: "var(--bg-primary)", minHeight: "100vh" }}>
      {/* Navigation */}
      <nav style={{ 
        height: "80px", 
        padding: "0 40px", 
        display: "flex", 
        alignItems: "center", 
        justifyContent: "space-between",
        borderBottom: "1px solid var(--glass-border)",
        background: "rgba(10, 10, 15, 0.8)",
        backdropFilter: "blur(12px)",
        position: "sticky",
        top: 0,
        zIndex: 50
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ 
            width: 36, 
            height: 36, 
            background: "linear-gradient(135deg, var(--brand-500), var(--brand-700))",
            borderRadius: "8px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "white",
            fontWeight: "bold"
          }}>P</div>
          <span style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-0.02em" }}>PhronesisIP</span>
        </div>
        <div style={{ display: "flex", gap: 32, alignItems: "center" }}>
          <Link href="#services" style={{ color: "var(--text-secondary)", textDecoration: "none", fontSize: 14, fontWeight: 500 }}>Services</Link>
          <Link href="#why-us" style={{ color: "var(--text-secondary)", textDecoration: "none", fontSize: 14, fontWeight: 500 }}>Methodology</Link>
          <Link href="/dashboard" className="btn btn-secondary btn-sm">Sign In</Link>
          <Link href="/get-started" className="btn btn-primary btn-sm">Order Report</Link>
        </div>
      </nav>

      {/* Hero Section */}
      <section style={{ 
        padding: "120px 40px 80px", 
        textAlign: "center",
        background: "radial-gradient(circle at 50% 10%, rgba(99, 102, 241, 0.15), transparent 60%)"
      }}>
        <div className="animate-in" style={{ maxWidth: 900, margin: "0 auto" }}>
          <div style={{ 
            display: "inline-flex", 
            alignItems: "center", 
            padding: "6px 12px", 
            background: "rgba(99, 102, 241, 0.1)", 
            borderRadius: "20px",
            border: "1px solid rgba(99, 102, 241, 0.2)",
            color: "var(--brand-300)",
            fontSize: 12,
            fontWeight: 600,
            marginBottom: 24,
            gap: 8
          }}>
            <Zap style={{ width: 14, height: 14 }} />
            <span>24-Hour Turnaround for USA Patent Filings</span>
          </div>
          <h1 style={{ 
            fontSize: 64, 
            fontWeight: 800, 
            lineHeight: 1.1, 
            marginBottom: 24,
            background: "linear-gradient(135deg, #fff 0%, #94a3b8 100%)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent"
          }}>
            AI-Powered Patent Intelligence.<br/>
            Attorney-Grade Results.
          </h1>
          <p style={{ 
            fontSize: 20, 
            color: "var(--text-secondary)", 
            maxWidth: 700, 
            margin: "0 auto 40px",
            lineHeight: 1.6
          }}>
            Deep semantic search across 100M+ global patents. Professional reports in 24 hours. Undercut traditional law firm costs without sacrificing technical depth.
          </p>
          <div style={{ display: "flex", gap: 16, justifyContent: "center" }}>
            <Link href="/get-started" className="btn btn-primary btn-lg" style={{ fontSize: 16 }}>
              Start Your Report <ArrowRight style={{ marginLeft: 8 }} />
            </Link>
            <Link href="/dashboard" className="btn btn-secondary btn-lg" style={{ fontSize: 16 }}>
              Explore Platform
            </Link>
          </div>
        </div>
      </section>

      {/* Trust Bar */}
      <section style={{ padding: "40px", textAlign: "center", opacity: 0.6 }}>
        <p style={{ fontSize: 12, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 20 }}>
          Powered by data from across the globe
        </p>
        <div style={{ display: "flex", justifyContent: "center", gap: 40, alignItems: "center", grayscale: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--text-secondary)" }}>
            <Globe style={{ width: 20, height: 20 }} /> USPTO (US)
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--text-secondary)" }}>
            <Globe style={{ width: 20, height: 20 }} /> EPO (Europe)
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--text-secondary)" }}>
            <Globe style={{ width: 20, height: 20 }} /> JPO (Japan)
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--text-secondary)" }}>
            <Globe style={{ width: 20, height: 20 }} /> WIPO
          </div>
        </div>
      </section>

      {/* Services Section */}
      <section id="services" style={{ padding: "100px 40px" }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 64 }}>
            <h2 style={{ fontSize: 40, fontWeight: 700, marginBottom: 16 }}>Premium Service Packages</h2>
            <p style={{ color: "var(--text-secondary)", fontSize: 18 }}>Everything you need to secure your intellectual property.</p>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(350px, 1fr))", gap: 32 }}>
            {/* Package 1 */}
            <div className="card-glass" style={{ padding: 40, display: "flex", flexDirection: "column" }}>
              <div style={{ marginBottom: 32 }}>
                <Search style={{ width: 40, height: 40, color: "var(--brand-400)", marginBottom: 20 }} />
                <h3 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>Prior Art Search</h3>
                <p style={{ color: "var(--text-secondary)", fontSize: 15 }}>Deep semantic search across USPTO + Google Patents. Top 15 threats ranked.</p>
              </div>
              <div style={{ fontSize: 32, fontWeight: 800, marginBottom: 32 }}>
                $599 <span style={{ fontSize: 14, fontWeight: 500, color: "var(--text-muted)" }}>/ report</span>
              </div>
              <ul style={{ listStyle: "none", marginBottom: 40, flex: 1 }}>
                <li style={{ display: "flex", gap: 12, marginBottom: 12, fontSize: 14, color: "var(--text-secondary)" }}>
                  <CheckCircle2 style={{ width: 18, height: 18, color: "var(--success)", flexShrink: 0 }} /> 
                  Comprehensive PDF Report
                </li>
                <li style={{ display: "flex", gap: 12, marginBottom: 12, fontSize: 14, color: "var(--text-secondary)" }}>
                  <CheckCircle2 style={{ width: 18, height: 18, color: "var(--success)", flexShrink: 0 }} /> 
                  Threat Level Ranking
                </li>
                <li style={{ display: "flex", gap: 12, marginBottom: 12, fontSize: 14, color: "var(--text-secondary)" }}>
                  <CheckCircle2 style={{ width: 18, height: 18, color: "var(--success)", flexShrink: 0 }} /> 
                  24-48 Hour Turnaround
                </li>
              </ul>
              <Link href="/get-started?package=prior-art" className="btn btn-secondary w-full">Order Search</Link>
            </div>

            {/* Package 2 */}
            <div className="card-glass" style={{ 
              padding: 40, 
              display: "flex", 
              flexDirection: "column",
              background: "linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(139, 92, 246, 0.05))",
              border: "1px solid rgba(99, 102, 241, 0.3)",
              transform: "scale(1.05)",
              zIndex: 10
            }}>
              <div style={{ 
                position: "absolute", 
                top: -12, 
                right: 20, 
                background: "var(--accent-500)", 
                color: "var(--bg-primary)",
                padding: "2px 12px",
                borderRadius: "20px",
                fontSize: 12,
                fontWeight: 700
              }}>MOST POPULAR</div>
              <div style={{ marginBottom: 32 }}>
                <Shield style={{ width: 40, height: 40, color: "var(--accent-400)", marginBottom: 20 }} />
                <h3 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>Patentability Suite</h3>
                <p style={{ color: "var(--text-secondary)", fontSize: 15 }}>Full search + legal opinion + 3 expert-drafted USPTO claims.</p>
              </div>
              <div style={{ fontSize: 32, fontWeight: 800, marginBottom: 32 }}>
                $1,299 <span style={{ fontSize: 14, fontWeight: 500, color: "var(--text-muted)" }}>/ report</span>
              </div>
              <ul style={{ listStyle: "none", marginBottom: 40, flex: 1 }}>
                <li style={{ display: "flex", gap: 12, marginBottom: 12, fontSize: 14, color: "var(--text-secondary)" }}>
                  <CheckCircle2 style={{ width: 18, height: 18, color: "var(--success)", flexShrink: 0 }} /> 
                  Full Prior Art Search
                </li>
                <li style={{ display: "flex", gap: 12, marginBottom: 12, fontSize: 14, color: "var(--text-secondary)" }}>
                  <CheckCircle2 style={{ width: 18, height: 18, color: "var(--success)", flexShrink: 0 }} /> 
                  Draft Claims in USPTO Format
                </li>
                <li style={{ display: "flex", gap: 12, marginBottom: 12, fontSize: 14, color: "var(--text-secondary)" }}>
                  <CheckCircle2 style={{ width: 18, height: 18, color: "var(--success)", flexShrink: 0 }} /> 
                  Patentability Legal Opinion
                </li>
              </ul>
              <Link href="/get-started?package=patentability" className="btn btn-primary w-full shadow-lg">Order Suite</Link>
            </div>

            {/* Package 3 */}
            <div className="card-glass" style={{ padding: 40, display: "flex", flexDirection: "column" }}>
              <div style={{ marginBottom: 32 }}>
                <Scale style={{ width: 40, height: 40, color: "var(--brand-400)", marginBottom: 20 }} />
                <h3 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>Office Action Response</h3>
                <p style={{ color: "var(--text-secondary)", fontSize: 15 }}>Upload your rejection; we draft a technical and legal response.</p>
              </div>
              <div style={{ fontSize: 32, fontWeight: 800, marginBottom: 32 }}>
                $1,499 <span style={{ fontSize: 14, fontWeight: 500, color: "var(--text-muted)" }}>/ draft</span>
              </div>
              <ul style={{ listStyle: "none", marginBottom: 40, flex: 1 }}>
                <li style={{ display: "flex", gap: 12, marginBottom: 12, fontSize: 14, color: "var(--text-secondary)" }}>
                  <CheckCircle2 style={{ width: 18, height: 18, color: "var(--success)", flexShrink: 0 }} /> 
                  Full Claim Traverse Support
                </li>
                <li style={{ display: "flex", gap: 12, marginBottom: 12, fontSize: 14, color: "var(--text-secondary)" }}>
                  <CheckCircle2 style={{ width: 18, height: 18, color: "var(--success)", flexShrink: 0 }} /> 
                  Technical Rebuttals
                </li>
                <li style={{ display: "flex", gap: 12, marginBottom: 12, fontSize: 14, color: "var(--text-secondary)" }}>
                  <CheckCircle2 style={{ width: 18, height: 18, color: "var(--success)", flexShrink: 0 }} /> 
                  Ready for Attorney Review
                </li>
              </ul>
              <Link href="/get-started?package=office-action" className="btn btn-secondary w-full">Order Draft</Link>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer style={{ 
        padding: "80px 40px", 
        borderTop: "1px solid var(--glass-border)",
        background: "var(--bg-secondary)"
      }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", textAlign: "center" }}>
          <div style={{ marginBottom: 32 }}>
             <span style={{ fontSize: 24, fontWeight: 800 }}>PhronesisIP</span>
             <p style={{ color: "var(--text-tertiary)", marginTop: 8 }}>Premium AI Intellectual Property Intelligence.</p>
          </div>
          <div style={{ color: "var(--text-muted)", fontSize: 12 }}>
            © 2026 PhronesisIP. All reports are attorney work product placeholders. AI assistance provided.
          </div>
        </div>
      </footer>
    </div>
  );
}
