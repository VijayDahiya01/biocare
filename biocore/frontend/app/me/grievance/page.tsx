"use client";
// M7 — Grievance: members raise a DPDP grievance and see their past ones.
import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "../../../lib/api";

type G = { grievance_id: string; subject: string | null; message: string;
           status: string; resolution: string | null; created_at: string };

export default function Grievance() {
  const [items, setItems] = useState<G[]>([]);
  const [form, setForm] = useState({ subject: "", message: "" });
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setItems((await api<{ items: G[] }>("/grievances")).items); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Could not load"); }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr(null); setMsg(null);
    try {
      await api("/grievance", { method: "POST", body: { subject: form.subject || null, message: form.message } });
      setMsg("Grievance submitted. The Data Protection Officer will review it.");
      setForm({ subject: "", message: "" }); load();
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Failed"); }
  }

  return (
    <div className="container">
      <p className="muted"><a href="/me">← My portal</a></p>
      <h1>Raise a grievance</h1>
      <p className="muted">Report a data-protection concern. This is the DPDP grievance mechanism.</p>
      {err && <div className="error">{err} — <a href="/me/login">sign in</a></div>}

      <div className="grid" style={{ gridTemplateColumns: "1fr 2fr", marginTop: 12 }}>
        <form className="card" onSubmit={submit}>
          <label>Subject (optional)</label>
          <input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} />
          <label>Message</label>
          <textarea value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })}
                    required rows={5} style={{ width: "100%", padding: 10, borderRadius: 8, border: "1px solid #cbd5e1" }} />
          {msg && <div className="muted" style={{ color: "#166534", marginTop: 8 }}>{msg}</div>}
          <button type="submit" style={{ width: "100%", marginTop: 12 }}>Submit</button>
        </form>

        <div className="card">
          <h2>My grievances</h2>
          <table>
            <thead><tr><th>Subject</th><th>Status</th><th>Resolution</th><th>Filed</th></tr></thead>
            <tbody>
              {items.map((g) => (
                <tr key={g.grievance_id}>
                  <td>{g.subject || g.message.slice(0, 30)}</td>
                  <td><span className={`badge ${g.status === "resolved" ? "green" : "amber"}`}>{g.status}</span></td>
                  <td>{g.resolution || "—"}</td>
                  <td>{new Date(g.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
              {items.length === 0 && <tr><td colSpan={4} className="muted">No grievances filed.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
