"use client";
// Person-app login — mobile hero, email + OTP (with dev bypass).
import "../app.css";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../lib/api";

export default function PersonLogin() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null); setBusy(true);
    try {
      if (!sent) {
        await api("/person/auth/otp/request", { method: "POST", body: { email: email.trim() } });
        setSent(true);
      } else {
        const d = await api<{ profile_complete: boolean }>("/person/auth/otp/verify",
          { method: "POST", body: { email: email.trim(), otp: otp.trim() } });
        // First time here: ask who they are before dropping them on a hub that cannot greet
        // them. Coming back: straight in.
        router.push(d.profile_complete ? "/member" : "/member/profile?welcome=1");
      }
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Sign-in failed");
    } finally { setBusy(false); }
  }

  async function devLogin() {
    setErr(null); setBusy(true);
    try {
      await api("/person/auth/dev-login", { method: "POST", body: { email: email.trim() || "dev@example.com" } });
      router.push("/member");
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Dev sign-in unavailable (enable DEV_LOGIN)");
    } finally { setBusy(false); }
  }

  return (
    <div className="center-screen">
      <div className="inner">
      <div className="hero">
        <div className="logo">B</div>
        <h1 className="app-h1">One app for every<br />place you belong to</h1>
        <p className="app-sub">Set up your face at each place — then walk in with just your face. No cards, no queues.</p>
        <p className="app-sub" style={{ marginTop: 6, opacity: .85 }}>
          New or returning — same door. We email you a code; there is no password to remember.
        </p>
      </div>
      <form className="app-card" onSubmit={submit}>
        <label className="app-label">Email address</label>
        <input className="app-field" type="email" inputMode="email" value={email}
               onChange={(e) => setEmail(e.target.value)} disabled={sent} placeholder="you@email.com" required />
        {sent && (<>
          <label className="app-label">Enter the code we emailed to {email.trim()}</label>
          <input className="app-field" value={otp} onChange={(e) => setOtp(e.target.value)}
                 inputMode="numeric" placeholder="6-digit code" required />
        </>)}
        {err && <div className="app-err">{err}</div>}
        <button className="btn primary" type="submit" disabled={busy}>
          {busy ? "Please wait…" : sent ? "Verify & sign in" : "Send code"}
        </button>
        <button className="btn soft" type="button" disabled={busy} onClick={devLogin}>
          Dev sign in (skip OTP)
        </button>
        <p className="muted-xs">Dev only — disabled in production.</p>
      </form>
      <p className="app-foot">Protected by face verification · you control every place</p>
      </div>
    </div>
  );
}
