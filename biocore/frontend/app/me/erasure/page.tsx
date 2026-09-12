"use client";
// M6 — Request erasure (DPDP right to erasure). Explainer -> OTP re-auth -> verified
// cascade -> certificate.
import { useEffect, useState } from "react";
import { ApiError, api } from "../../../lib/api";

type Step = "explain" | "otp" | "done";
type Result = { erasure_ref: string; stores_cleared: string[]; certificate_url: string };

export default function Erasure() {
  const [step, setStep] = useState<Step>("explain");
  const [email, setEmail] = useState<string | null>(null);
  const [otp, setOtp] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);

  useEffect(() => {
    api<{ email: string }>("/auth/me").then((d) => setEmail(d.email))
      .catch(() => setErr("Please sign in first."));
  }, []);

  async function beginReauth() {
    setErr(null); setBusy(true);
    try {
      await api("/auth/otp/request", { method: "POST", body: { email } });
      setStep("otp");
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Could not send code"); }
    finally { setBusy(false); }
  }

  async function confirmErasure(e: React.FormEvent) {
    e.preventDefault(); setErr(null); setBusy(true);
    try {
      const data = await api<Result>("/me/data/erasure", { method: "POST", body: { otp: otp.trim() } });
      setResult(data); setStep("done");
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Erasure failed");
    } finally { setBusy(false); }
  }

  return (
    <div className="center">
      <div className="card narrow">
        {step === "explain" && (
          <>
            <h1>Request erasure</h1>
            <p className="muted">This permanently destroys your biometric data:</p>
            <ul className="muted" style={{ fontSize: 13 }}>
              <li>Face vector (Milvus) and any image (MinIO) — deleted &amp; verified</li>
              <li>Your profile records and sessions — removed</li>
            </ul>
            <p className="muted" style={{ fontSize: 13 }}>
              Attendance logs may be retained where labour law requires, but are
              de-linked from your biometric identity. The erasure itself is logged.
            </p>
            {err && <div className="error">{err}</div>}
            <button disabled={!email || busy} onClick={beginReauth} style={{ width: "100%", marginTop: 14, background: "#dc2626" }}>
              {busy ? "…" : "Begin erasure"}
            </button>
          </>
        )}

        {step === "otp" && (
          <form onSubmit={confirmErasure}>
            <h1>Confirm it&apos;s you</h1>
            <p className="muted">Enter the code sent to {email} to authorise erasure.</p>
            <label>Code</label>
            <input value={otp} onChange={(e) => setOtp(e.target.value)} inputMode="numeric" required />
            {err && <div className="error">{err}</div>}
            <button type="submit" disabled={busy} style={{ width: "100%", marginTop: 14, background: "#dc2626" }}>
              {busy ? "Erasing…" : "Permanently erase my data"}
            </button>
          </form>
        )}

        {step === "done" && result && (
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 40 }}>🗑️</div>
            <h1>Erasure complete</h1>
            <p className="muted">Reference: <code>{result.erasure_ref}</code></p>
            <p className="muted">Cleared: {result.stores_cleared.join(", ")}</p>
            <a href={result.certificate_url}><button className="secondary" style={{ marginTop: 12 }}>Download certificate</button></a>
          </div>
        )}
      </div>
    </div>
  );
}
