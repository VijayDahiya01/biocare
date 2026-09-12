"use client";
// K2 — Self-registration form. Creates a pending account and triggers an email OTP.
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    org_code: "", first_name: "", last_name: "", email: "", department: "",
  });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [k]: e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await api("/register", {
        method: "POST",
        body: {
          org_code: form.org_code.trim(),
          first_name: form.first_name.trim(),
          last_name: form.last_name.trim() || null,
          email: form.email.trim(),
          department: form.department.trim() || null,
        },
      });
      router.push(`/register/verify?email=${encodeURIComponent(form.email.trim())}`);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="center">
      <form className="card narrow" onSubmit={submit}>
        <h1>Create your account</h1>
        <p className="muted">Enter your organisation code and details to begin.</p>

        <label>Organisation code</label>
        <input value={form.org_code} onChange={set("org_code")} placeholder="ACME-2026" required />
        <label>First name</label>
        <input value={form.first_name} onChange={set("first_name")} required />
        <label>Last name</label>
        <input value={form.last_name} onChange={set("last_name")} />
        <label>Work email</label>
        <input type="email" value={form.email} onChange={set("email")} required />
        <label>Department (optional)</label>
        <input value={form.department} onChange={set("department")} />

        {err && <div className="error">{err}</div>}
        <button type="submit" disabled={busy} style={{ width: "100%", marginTop: 18 }}>
          {busy ? "Sending code…" : "Continue"}
        </button>
      </form>
    </div>
  );
}
