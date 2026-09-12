"use client";
// M1 — Member sign in (email + OTP, no password).
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../lib/api";

export default function MemberLogin() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function requestOtp(e: React.FormEvent) {
    e.preventDefault();
    setErr(null); setBusy(true);
    try {
      await api("/auth/otp/request", { method: "POST", body: { email: email.trim() } });
      setSent(true);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not send code");
    } finally { setBusy(false); }
  }

  async function verify(e: React.FormEvent) {
    e.preventDefault();
    setErr(null); setBusy(true);
    try {
      await api("/auth/otp/verify", { method: "POST", body: { email: email.trim(), otp: otp.trim() } });
      router.push("/me");
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Invalid code");
    } finally { setBusy(false); }
  }

  return (
    <div className="center">
      <form className="card narrow" onSubmit={sent ? verify : requestOtp}>
        <h1>Member sign in</h1>
        <p className="muted">We&apos;ll email you a one-time code.</p>
        <label>Email</label>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
               disabled={sent} required />
        {sent && (
          <>
            <label>Code</label>
            <input value={otp} onChange={(e) => setOtp(e.target.value)} inputMode="numeric"
                   placeholder="123456" required />
          </>
        )}
        {err && <div className="error">{err}</div>}
        <button type="submit" disabled={busy} style={{ width: "100%", marginTop: 16 }}>
          {busy ? "…" : sent ? "Sign in" : "Send code"}
        </button>
      </form>
    </div>
  );
}
