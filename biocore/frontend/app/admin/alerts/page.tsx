"use client";
// A14 — Alerts: list active, filter by priority, dismiss.
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../lib/api";

type Alert = { alert_id: string; type: string; priority: string; message: string; created_at: string };

const prClass = (p: string) => (p === "critical" ? "red" : p === "high" ? "amber" : "gray");

export default function Alerts() {
  const router = useRouter();
  const [items, setItems] = useState<Alert[]>([]);
  const [priority, setPriority] = useState("");

  const load = useCallback(async () => {
    const q = priority ? `?priority=${priority}` : "";
    try { setItems((await api<{ items: Alert[] }>(`/alerts${q}`)).items); }
    catch (e) { if (e instanceof ApiError && e.status === 401) router.push("/admin/login"); }
  }, [priority, router]);

  useEffect(() => { load(); }, [load]);

  async function dismiss(id: string) {
    await api(`/alerts/${id}/dismiss`, { method: "POST" }).catch(() => {});
    load();
  }

  return (
    <div>
      <h1>Alerts</h1>
      <div className="card" style={{ marginTop: 16, maxWidth: 240 }}>
        <label>Priority</label>
        <select value={priority} onChange={(e) => setPriority(e.target.value)}>
          <option value="">All</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
        </select>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <table>
          <thead><tr><th>Priority</th><th>Type</th><th>Message</th><th>When</th><th></th></tr></thead>
          <tbody>
            {items.map((a) => (
              <tr key={a.alert_id}>
                <td><span className={`badge ${prClass(a.priority)}`}>{a.priority}</span></td>
                <td>{a.type}</td>
                <td>{a.message}</td>
                <td>{new Date(a.created_at).toLocaleString()}</td>
                <td><button className="ghost" onClick={() => dismiss(a.alert_id)}>Dismiss</button></td>
              </tr>
            ))}
            {items.length === 0 && <tr><td colSpan={5} className="muted">No active alerts.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
