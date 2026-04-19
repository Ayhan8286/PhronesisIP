"use client";

import { useState, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { 
  Zap, 
  ArrowRight, 
  CheckCircle2, 
  Shield, 
  FileText, 
  Search,
  Upload,
  Loader2,
  Mail,
  User,
  AlertCircle
} from "lucide-react";
import Link from "next/link";

export default function GetStartedPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialPackage = searchParams.get("package") || "prior_art";

  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedPackage, setSelectedPackage] = useState(initialPackage);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const packages = [
    { id: "prior_art", name: "Prior Art Search", price: "$599", icon: Search },
    { id: "patentability", name: "Patentability Suite", price: "$1,299", icon: Shield },
    { id: "office_action", name: "Office Action Response", price: "$1,499", icon: FileText },
  ];

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "";
      const res = await fetch(`${apiUrl}/api/v1/public/services/intake`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_email: email,
          client_name: name,
          service_package: selectedPackage,
          description: description,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Submission failed");
      }

      setSubmitted(true);
      // In a real app, we'd redirect to Stripe here.
      // For now, we'll show a success state.
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <div style={{ 
        background: "var(--bg-primary)", 
        minHeight: "100vh", 
        display: "flex", 
        alignItems: "center", 
        justifyContent: "center",
        padding: 40
      }}>
        <div className="card-glass animate-in" style={{ maxWidth: 600, textAlign: "center", padding: 60 }}>
          <div style={{ 
            width: 80, height: 80, background: "rgba(34, 197, 94, 0.1)", 
            borderRadius: "50%", display: "flex", alignItems: "center", 
            justifyContent: "center", margin: "0 auto 32px" 
          }}>
            <CheckCircle2 style={{ width: 40, height: 40, color: "var(--success)" }} />
          </div>
          <h1 style={{ fontSize: 32, fontWeight: 800, marginBottom: 16 }}>Order Submitted</h1>
          <p style={{ color: "var(--text-secondary)", fontSize: 18, marginBottom: 40, lineHeight: 1.6 }}>
            We've received your request for a <b>{packages.find(p => p.id === selectedPackage)?.name}</b>. 
            An invoice has been sent to <b>{email}</b>. Our team will begin the analysis once payment is confirmed.
          </p>
          <div style={{ display: "flex", gap: 16, justifyContent: "center" }}>
            <Link href="/" className="btn btn-secondary">Return Home</Link>
            {/* Placeholder for Stripe Redirect */}
            <button className="btn btn-primary" onClick={() => window.location.href = "https://stripe.com/pay/" + selectedPackage}>
              Proceed to Payment <ArrowRight style={{ marginLeft: 8 }} />
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ background: "var(--bg-primary)", minHeight: "100vh", padding: "60px 40px" }}>
      <div style={{ maxWidth: 1000, margin: "0 auto" }}>
        <Link href="/" style={{ 
          display: "inline-flex", alignItems: "center", gap: 8, 
          color: "var(--text-secondary)", textDecoration: "none", 
          fontSize: 14, marginBottom: 48 
        }}>
          <ArrowRight style={{ width: 14, height: 14, transform: "rotate(180deg)" }} /> Back to Home
        </Link>

        <div style={{ display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: 64 }}>
          {/* Left: Form */}
          <div className="animate-in">
            <h1 style={{ fontSize: 40, fontWeight: 800, marginBottom: 16 }}>Start Your Patent Report</h1>
            <p style={{ color: "var(--text-secondary)", fontSize: 18, marginBottom: 48 }}>
              Complete the details below to initialize our AI-powered analysis engine.
            </p>

            <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 32 }}>
              {/* Package Selection */}
              <div className="form-group">
                <label className="label">Select Service Package</label>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
                  {packages.map((pkg) => {
                    const Icon = pkg.icon;
                    return (
                      <div 
                        key={pkg.id}
                        onClick={() => setSelectedPackage(pkg.id)}
                        style={{
                          padding: 16,
                          borderRadius: "var(--radius-lg)",
                          border: `2px solid ${selectedPackage === pkg.id ? "var(--brand-500)" : "var(--glass-border)"}`,
                          background: selectedPackage === pkg.id ? "rgba(99, 102, 241, 0.05)" : "var(--bg-secondary)",
                          cursor: "pointer",
                          transition: "all 0.2s ease",
                          textAlign: "center"
                        }}
                      >
                        <Icon style={{ 
                          width: 24, height: 24, 
                          color: selectedPackage === pkg.id ? "var(--brand-400)" : "var(--text-tertiary)",
                          marginBottom: 8,
                          margin: "0 auto 8px"
                        }} />
                        <div style={{ fontSize: 13, fontWeight: 700, color: selectedPackage === pkg.id ? "var(--text-primary)" : "var(--text-secondary)" }}>{pkg.name}</div>
                        <div style={{ fontSize: 12, color: selectedPackage === pkg.id ? "var(--brand-300)" : "var(--text-muted)" }}>{pkg.price}</div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Client Info */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
                <div className="form-group">
                  <label className="label">Full Name</label>
                  <div className="search-bar" style={{ maxWidth: "100%" }}>
                    <User className="search-bar-icon" />
                    <input 
                      className="input" 
                      placeholder="e.g. John Doe" 
                      required 
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label className="label">Work Email</label>
                  <div className="search-bar" style={{ maxWidth: "100%" }}>
                    <Mail className="search-bar-icon" />
                    <input 
                      type="email" 
                      className="input" 
                      placeholder="email@company.com" 
                      required 
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                    />
                  </div>
                </div>
              </div>

              {/* Invention Details */}
              <div className="form-group">
                <label className="label">
                  {selectedPackage === "office_action" ? "Summary of Rejection" : "Invention Description"}
                </label>
                <textarea 
                  className="input textarea" 
                  placeholder={selectedPackage === "office_action" ? "Paste the independent claim rejection from your office action..." : "Describe your invention concept in detail. The more info we have, the better our semantic search results."}
                  style={{ minHeight: 180 }}
                  required
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>

              {/* File Upload (Placeholder) */}
              <div style={{ 
                padding: 32, 
                border: "2px dashed var(--glass-border)", 
                borderRadius: "var(--radius-lg)",
                textAlign: "center",
                color: "var(--text-secondary)"
              }}>
                <Upload style={{ width: 32, height: 32, margin: "0 auto 12px", opacity: 0.5 }} />
                <p style={{ fontSize: 14 }}>Upload Invention Disclosure or Office Action PDF (Optional)</p>
                <p style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 4 }}>Max size 10MB. .PDF, .DOCX</p>
              </div>

              {error && (
                <div style={{ 
                  padding: "12px 16px", 
                  background: "rgba(239, 68, 68, 0.1)", 
                  border: "1px solid rgba(239, 68, 68, 0.2)",
                  borderRadius: "var(--radius-md)",
                  color: "var(--error)",
                  fontSize: 14,
                  display: "flex",
                  alignItems: "center",
                  gap: 10
                }}>
                  <AlertCircle style={{ width: 16, height: 16 }} /> {error}
                </div>
              )}

              <button className="btn btn-primary btn-lg" disabled={isSubmitting} style={{ width: "100%", paddingY: 20, fontSize: 16 }}>
                {isSubmitting ? <Loader2 className="animate-spin" /> : <>Initialize Report & Proceed <ArrowRight style={{ marginLeft: 8 }} /></>}
              </button>
            </form>
          </div>

          {/* Right: Info/Testimonials */}
          <div style={{ paddingTop: 40 }}>
            <div className="card" style={{ background: "rgba(99, 102, 241, 0.05)", padding: 40, position: "sticky", top: 120 }}>
              <div style={{ marginBottom: 32 }}>
                <div style={{ 
                  width: 48, height: 48, background: "var(--brand-500)", 
                  borderRadius: "12px", display: "flex", alignItems: "center", 
                  justifyContent: "center", color: "white", marginBottom: 20
                }}>
                  <Zap style={{ width: 24, height: 24 }} />
                </div>
                <h4 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>What happens next?</h4>
                <p style={{ color: "var(--text-secondary)", fontSize: 14, lineHeight: 1.6 }}>
                  Once you order, our AI engine begins a deep semantic crawl. A patent expert reviews all findings to ensure 100% accuracy before delivery.
                </p>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
                <div style={{ display: "flex", gap: 16 }}>
                  <div style={{ width: 44, height: 44, borderRadius: "50%", background: "var(--bg-tertiary)", flexShrink: 0 }}></div>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 700 }}>"Cutting edge results."</div>
                    <div style={{ fontSize: 12, color: "var(--text-muted)" }}>US Solo Inventor</div>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 16 }}>
                  <div style={{ width: 44, height: 44, borderRadius: "50%", background: "var(--bg-tertiary)", flexShrink: 0 }}></div>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 700 }}>"Saved us weeks of search time."</div>
                    <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Patent Agent, CA</div>
                  </div>
                </div>
              </div>

              <div style={{ marginTop: 48, paddingTop: 32, borderTop: "1px solid var(--glass-border)" }}>
                 <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                   <Shield style={{ width: 20, height: 20, color: "var(--success)" }} />
                   <span style={{ fontSize: 13, fontWeight: 500 }}>Secure Data Handling Policy</span>
                 </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
