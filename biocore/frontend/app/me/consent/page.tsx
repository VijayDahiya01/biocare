"use client";
// M4 — My consent: view consent records and revoke (DPDP).
import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "../../../lib/api";

type Consent = { consent_ref: string; purpose: string; method: string; active: boolean;
                 given_at: string; revoked_at: string | null };

export default function MyConsent() {
  const [consents, setConsents] = useState<Consent[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const d = await api<{ consents: Consent[] }>("/me/data/export");
      setConsents(d.consents || []);
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Could not load"); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function revoke() {
    setErr(null); setMsg(null);
    if (!confirm("Revoke consent? You may be switched to manual attendance.")) return;
    try {
      await api("/me/consent/revoke", { method: "POST" });
      setMsg("Consent revoked.");
      load();
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Could not revoke"); }
  }

  const hasActive = consents.some((c) => c.active);

  return (
    <div className="container">
      <p className="muted"><a href="/me">← My portal</a></p>
      <h1>My consent</h1>
      {err && <div className="error">{err} — <a href="/me/login">sign in</a></div>}
      {msg && <div className="muted" style={{ color: "#166534" }}>{msg}</div>}
      <div className="card" style={{ marginTop: 12 }}>
        <table>
          <thead><tr><th>Reference</th><th>Purpose</th><th>Method</th><th>Status</th><th>Given</th></tr></thead>
          <tbody>
            {consents.map((c) => (
              <tr key={c.consent_ref}>
                <td>{c.consent_ref}</td>
                <td>{c.purpose}</td>
                <td>{c.method}</td>
                <td><span className={`badge ${c.active ? "green" : "gray"}`}>{c.active ? "active" : "revoked"}</span></td>
                <td>{new Date(c.given_at).toLocaleDateString()}</td>
              </tr>
            ))}
            {consents.length === 0 && <tr><td colSpan={5} className="muted">No consent records.</td></tr>}
          </tbody>
        </table>
        {hasActive && <button style={{ marginTop: 14, background: "#dc2626" }} onClick={revoke}>Revoke consent</button>}
      </div>
    </div>
  );
}
