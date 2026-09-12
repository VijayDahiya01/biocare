"use client";
// M2 (minimal) — member landing: my recent attendance. Full self-service
// (leave, consent, data export, erasure) lands in Phase 2/3.
import { useEffect, useState } from "react";
import { ApiError, api } from "../../lib/api";

type Row = { event_type: string; timestamp: string };

export default function MePage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api<{ items: Row[] }>("/attendance?page_size=20")
      .then((d) => setRows(d.items))
      .catch((e) => setErr(e instanceof ApiError ? e.message : "Could not load"));
  }, []);

  return (
    <div className="container">
      <h1>My attendance</h1>
      <div style={{ display: "flex", gap: 14, margin: "8px 0 4px" }}>
        <a href="/me/leave">My leave</a>
        <a href="/me/consent">My consent</a>
        <a href="/me/data">My data</a>
        <a href="/me/erasure">Request erasure</a>
        <a href="/me/grievance">Grievance</a>
      </div>
      {err && <div className="error">{err} — <a href="/me/login">sign in</a></div>}
      <div className="card" style={{ marginTop: 16 }}>
        <table>
          <thead><tr><th>Event</th><th>Time</th></tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td>{r.event_type}</td>
                <td>{new Date(r.timestamp).toLocaleString()}</td>
              </tr>
            ))}
            {rows.length === 0 && !err && <tr><td colSpan={2} className="muted">No records yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
