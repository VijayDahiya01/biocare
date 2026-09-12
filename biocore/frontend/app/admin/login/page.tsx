"use client";
// A1 — Admin login. Email + password + mandatory TOTP 2FA.
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../lib/api";

export default function AdminLogin() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totp, setTotp] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null); setBusy(true);
    try {
      await api("/auth/login", {
        method: "POST",
        body: { email: email.trim(), password, totp_code: totp.trim() || null },
      });
      router.push("/admin/dashboard");
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Login failed");
    } finally { setBusy(false); }
  }

  return (
    <div className="center">
      <form className="card narrow" onSubmit={submit}>
        <h1>Admin sign in</h1>
        <p className="muted">Two-factor authentication is required.</p>
        <label>Email</label>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <label>Password</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        <label>2FA code</label>
        <input value={totp} onChange={(e) => setTotp(e.target.value)} inputMode="numeric"
               placeholder="123456" required />
        {err && <div className="error">{err}</div>}
        <button type="submit" disabled={busy} style={{ width: "100%", marginTop: 18 }}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
