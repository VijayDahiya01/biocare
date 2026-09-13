"use client";
// Join a business by org code (mobile).
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../lib/api";

export default function Join() {
  const router = useRouter();
  const [code, setCode] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null); setBusy(true);
    try {
      await api("/person/businesses/join", { method: "POST", body: { org_code: code.trim() } });
      router.push("/member");
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not join");
    } finally { setBusy(false); }
  }

  return (
    <div>
      <a className="app-back" href="/member">← Home</a>
      <h1 className="app-h1">Join a business</h1>
      <p className="app-sub">Enter the organisation code your business gave you.</p>
      <form className="app-card" style={{ marginTop: 14 }} onSubmit={submit}>
        <label className="app-label">Organisation code</label>
        <input className="app-field" value={code} onChange={(e) => setCode(e.target.value)}
               placeholder="ACME-2026" autoCapitalize="characters" required />
        {err && <div className="app-err">{err}</div>}
        <button className="btn primary" type="submit" disabled={busy}>{busy ? "Joining…" : "Join"}</button>
      </form>
    </div>
  );
}
