"use client";
// Retention rules (§11.4 / §13.3) — configure per-category retention + expiry triggers,
// and run the expiry sweep.
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../lib/api";

type Policy = { id: string; data_category: string; retention_period: string | null; expiry_trigger: string | null; legal_hold_allowed: boolean; deletion_method: string };

export default function Retention() {
  const router = useRouter();
  const [items, setItems] = useState<Policy[]>([]);
  const [f, setF] = useState({ data_category: "face_credential", retention_period: "", expiry_trigger: "", deletion_method: "hard_delete" });
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { const d = await api<{ items: Policy[] }>("/retention/policies"); setItems(d.items); }
    catch (e) { if (e instanceof ApiError && e.status === 401) router.push("/admin/login"); }
  }, [router]);
  useEffect(() => { load(); }, [load]);

  async function save(e: React.FormEvent) {
    e.preventDefault(); setErr(null); setMsg(null);
    try {
      await api("/retention/policies", { method: "POST", body: {
        ...f, retention_period: f.retention_period.trim() || null, expiry_trigger: f.expiry_trigger.trim() || null,
      } });
      setMsg("Policy saved."); load();
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Failed"); }
  }

  async function sweep() {
    setErr(null); setMsg(null);
    try { const d = await api<{ expired: number }>("/retention/sweep", { method: "POST", body: {} }); setMsg(`Sweep complete — ${d.expired} credential(s) expired.`); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Failed"); }
  }

  return (
    <div>
      <h1>Retention rules</h1>
      <p className="muted">Per-category retention drives credential expiry. Vertical triggers (event end, checkout, employment end, visit end) call the sweep/erasure when those lifecycle events fire.</p>
      {err && <div className="error">{err}</div>}
      {msg && <div className="card" style={{ background: "#ecfdf5", borderColor: "#a7f3d0" }}>{msg}</div>}

      <form className="card" style={{ marginTop: 16, display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))", gap: 12, alignItems: "flex-end" }} onSubmit={save}>
        <div><label>Data category</label>
          <select value={f.data_category} onChange={(e) => setF({ ...f, data_category: e.target.value })}>
            <option value="face_credential">Face credential</option>
            <option value="verification">Verification</option>
            <option value="entry_log">Entry log</option>
          </select>
        </div>
        <div><label>Retention period</label><input value={f.retention_period} onChange={(e) => setF({ ...f, retention_period: e.target.value })} placeholder="30d, 1y, 8h" /></div>
        <div><label>Expiry trigger</label><input value={f.expiry_trigger} onChange={(e) => setF({ ...f, expiry_trigger: e.target.value })} placeholder="event_end, checkout…" /></div>
        <div><label>Deletion</label>
          <select value={f.deletion_method} onChange={(e) => setF({ ...f, deletion_method: e.target.value })}>
            <option value="hard_delete">Hard delete</option>
            <option value="zeroize">Zeroize</option>
          </select>
        </div>
        <button type="submit">Save policy</button>
      </form>

      <div style={{ marginTop: 12 }}>
        <button className="ghost" onClick={sweep}>Run expiry sweep now</button>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <table>
          <thead><tr><th>Category</th><th>Retention</th><th>Trigger</th><th>Deletion</th><th>Legal hold</th></tr></thead>
          <tbody>
            {items.map((p) => (
              <tr key={p.id}>
                <td>{p.data_category}</td><td>{p.retention_period || "—"}</td><td>{p.expiry_trigger || "—"}</td>
                <td>{p.deletion_method}</td><td>{p.legal_hold_allowed ? "allowed" : "no"}</td>
              </tr>
            ))}
            {items.length === 0 && <tr><td colSpan={5} className="muted">No retention policies set.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
