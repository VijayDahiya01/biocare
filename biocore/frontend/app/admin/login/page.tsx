"use client";
// A1 — Admin login. Email + password.
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../lib/api";

export default function AdminLogin() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null); setBusy(true);
    try {
      await api("/auth/login", {
        method: "POST",
        body: { email: email.trim(), password },
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
        <label>Email</label>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <label>Password</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        {err && <div className="error">{err}</div>}
        <button type="submit" disabled={busy} style={{ width: "100%", marginTop: 18 }}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
