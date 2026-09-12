"use client";
// A19 — Emergency headcount: trigger a muster snapshot, see who is inside.
import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "../../../lib/api";

type Person = { user_id: string; name: string; since?: string };

export default function Emergency() {
  const [people, setPeople] = useState<Person[]>([]);
  const [count, setCount] = useState(0);
  const [triggered, setTriggered] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const status = useCallback(async () => {
    try {
      const d = await api<{ inside_count: number; people: Person[] }>("/emergency/status");
      setCount(d.inside_count); setPeople(d.people);
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Could not load"); }
  }, []);

  useEffect(() => { status(); }, [status]);

  async function trigger() {
    setErr(null);
    if (!confirm("Trigger emergency muster? This snapshots everyone currently inside.")) return;
    try {
      const d = await api<{ inside_count: number; people: Person[] }>("/emergency/trigger", { method: "POST", body: {} });
      setCount(d.inside_count); setPeople(d.people); setTriggered(true);
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Failed"); }
  }

  return (
    <div>
      <h1>Emergency headcount</h1>
      <div className="card" style={{ marginTop: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ fontSize: 36, fontWeight: 700 }}>{count}</div>
          <div className="muted">people currently inside</div>
        </div>
        <div>
          <button className="secondary" onClick={status} style={{ marginRight: 8 }}>Refresh</button>
          <button style={{ background: "#dc2626" }} onClick={trigger}>Trigger muster</button>
        </div>
      </div>
      {triggered && <div className="muted" style={{ color: "#166534", margin: "8px 0" }}>Muster snapshot recorded.</div>}
      {err && <div className="error">{err}</div>}

      <div className="card" style={{ marginTop: 16 }}>
        <table>
          <thead><tr><th>Name</th><th>Inside since</th></tr></thead>
          <tbody>
            {people.map((p) => (
              <tr key={p.user_id}><td>{p.name}</td><td>{p.since ? new Date(p.since).toLocaleString() : "—"}</td></tr>
            ))}
            {people.length === 0 && <tr><td colSpan={2} className="muted">Nobody inside.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
