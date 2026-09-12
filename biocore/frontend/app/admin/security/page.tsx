"use client";
// Phase 4 — Security analytics: zone-movement trail + anomalies, PPE violations.
import { useState } from "react";
import { ApiError, api } from "../../../lib/api";

type Movement = {
  trail: { zone_id: string; event: string; at: string }[];
  dwell_seconds_by_zone: Record<string, number>;
  anomalies: { type: string; at: string; from?: string; to?: string; zone_id?: string }[];
};
type Violation = { user_id: string | null; zone_id: string | null; at: string };

export default function Security() {
  const [userId, setUserId] = useState("");
  const [range, setRange] = useState({ from: "", to: "" });
  const [mv, setMv] = useState<Movement | null>(null);
  const [violations, setViolations] = useState<Violation[]>([]);
  const [err, setErr] = useState<string | null>(null);

  async function runMovement(e: React.FormEvent) {
    e.preventDefault(); setErr(null); setMv(null);
    try {
      setMv(await api<Movement>(`/security/movement?user_id=${userId}&from=${range.from}&to=${range.to}`));
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Failed"); }
  }

  async function loadViolations() {
    setErr(null);
    const today = new Date().toISOString().slice(0, 10);
    const from = range.from || today;
    const to = range.to || today;
    try { setViolations((await api<{ items: Violation[] }>(`/security/ppe-violations?from=${from}&to=${to}`)).items); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Failed"); }
  }

  return (
    <div>
      <h1>Security analytics</h1>

      <form className="card" style={{ marginTop: 16, display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }} onSubmit={runMovement}>
        <div style={{ flex: 1, minWidth: 200 }}><label>User ID</label><input value={userId} onChange={(e) => setUserId(e.target.value)} placeholder="user uuid" required /></div>
        <div style={{ width: 160 }}><label>From</label><input type="date" value={range.from} onChange={(e) => setRange({ ...range, from: e.target.value })} required /></div>
        <div style={{ width: 160 }}><label>To</label><input type="date" value={range.to} onChange={(e) => setRange({ ...range, to: e.target.value })} required /></div>
        <button type="submit">Trace movement</button>
        <button type="button" className="secondary" onClick={loadViolations}>PPE violations</button>
      </form>
      {err && <div className="error">{err}</div>}

      {mv && (
        <div className="grid" style={{ gridTemplateColumns: "2fr 1fr", marginTop: 16 }}>
          <div className="card">
            <h2>Movement trail</h2>
            <table>
              <thead><tr><th>#</th><th>Zone</th><th>Event</th><th>At</th></tr></thead>
              <tbody>
                {mv.trail.map((t, i) => (
                  <tr key={i}><td>{i + 1}</td><td>{t.zone_id.slice(0, 8)}</td><td>{t.event}</td><td>{new Date(t.at).toLocaleString()}</td></tr>
                ))}
                {mv.trail.length === 0 && <tr><td colSpan={4} className="muted">No zoned events.</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="card">
            <h2>Anomalies</h2>
            {mv.anomalies.length === 0 && <p className="muted">None detected.</p>}
            {mv.anomalies.map((a, i) => (
              <div key={i} style={{ marginBottom: 8 }}>
                <span className="badge red">{a.type}</span>
                <div className="muted" style={{ fontSize: 12 }}>{new Date(a.at).toLocaleString()}</div>
              </div>
            ))}
            <h2 style={{ marginTop: 16 }}>Dwell (s)</h2>
            {Object.entries(mv.dwell_seconds_by_zone).map(([z, s]) => (
              <div key={z} className="muted" style={{ fontSize: 13 }}>{z.slice(0, 8)}: {s}s</div>
            ))}
          </div>
        </div>
      )}

      {violations.length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <h2>PPE violations</h2>
          <table>
            <thead><tr><th>User</th><th>Zone</th><th>At</th></tr></thead>
            <tbody>
              {violations.map((v, i) => (
                <tr key={i}><td>{v.user_id?.slice(0, 8) || "—"}</td><td>{v.zone_id?.slice(0, 8) || "—"}</td><td>{new Date(v.at).toLocaleString()}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
