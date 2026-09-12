"use client";
// K3 — Email verification. Verifying the OTP creates the member session, after
// which the registrant proceeds to consent + face capture.
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ApiError, api } from "../../../lib/api";

function Verify() {
  const router = useRouter();
  const params = useSearchParams();
  const email = params.get("email") || "";
  const [otp, setOtp] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [resent, setResent] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await api("/auth/otp/verify", { method: "POST", body: { email, otp: otp.trim() } });
      router.push("/enroll");
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Verification failed");
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    setErr(null);
    try {
      await api("/auth/otp/request", { method: "POST", body: { email } });
      setResent(true);
    } catch {
      setErr("Could not resend code");
    }
  }

  return (
    <div className="center">
      <form className="card narrow" onSubmit={submit}>
        <h1>Verify your email</h1>
        <p className="muted">We sent a 6-digit code to <b>{email}</b>. It expires in 10 minutes.</p>
        <label>Verification code</label>
        <input value={otp} onChange={(e) => setOtp(e.target.value)} inputMode="numeric"
               placeholder="123456" maxLength={8} required />
        {err && <div className="error">{err}</div>}
        {resent && <div className="muted" style={{ marginTop: 8 }}>A new code has been sent.</div>}
        <button type="submit" disabled={busy} style={{ width: "100%", marginTop: 18 }}>
          {busy ? "Verifying…" : "Verify"}
        </button>
        <button type="button" className="ghost" onClick={resend} style={{ width: "100%", marginTop: 8 }}>
          Resend code
        </button>
      </form>
    </div>
  );
}

export default function VerifyPage() {
  return (
    <Suspense fallback={<div className="center"><div className="card narrow">Loading…</div></div>}>
      <Verify />
    </Suspense>
  );
}
