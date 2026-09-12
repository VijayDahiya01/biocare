"use client";
// Admin/DPO grievance queue: review and resolve.
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../lib/api";

type G = { grievance_id: string; user_name: string; subject: string | null;
           message: string; status: string; resolution: string | null; created_at: string };

export default function AdminGrievances() {
  const router = useRouter();
  const [items, setItems] = useState<G[]>([]);
  const [status, setStatus] = useState("open");

  const load = useCallback(async () => {
    const q = status ? `?status=${status}` : "";
    try { setItems((await api<{ items: G[] }>(`/grievances${q}`)).items); }
    catch (e) { if (e instanceof ApiError && e.status === 401) router.push("/admin/login"); }
  }, [status, router]);
  useEffect(() => { load(); }, [load]);

  async function resolve(id: string) {
    const resolution = window.prompt("Resolution note:");
    if (!resolution) return;
    await api(`/grievances/${id}/resolve`, { method: "POST", body: { resolution } }).catch(() => {});
    load();
  }

  return (
    <div>
      <h1>Grievances</h1>
      <div className="card" style={{ marginTop: 16, maxWidth: 220 }}>
        <label>Status</label>
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All</option>
          <option value="open">Open</option>
          <option value="resolved">Resolved</option>
        </select>
      </div>
      <div className="card" style={{ marginTop: 16 }}>
        <table>
          <thead><tr><th>From</th><th>Subject</th><th>Message</th><th>Status</th><th>Filed</th><th></th></tr></thead>
          <tbody>
            {items.map((g) => (
              <tr key={g.grievance_id}>
                <td>{g.user_name}</td>
                <td>{g.subject || "—"}</td>
                <td style={{ maxWidth: 280 }}>{g.message}</td>
                <td><span className={`badge ${g.status === "resolved" ? "green" : "amber"}`}>{g.status}</span></td>
                <td>{new Date(g.created_at).toLocaleDateString()}</td>
                <td>{g.status === "open" && <button className="ghost" onClick={() => resolve(g.grievance_id)}>Resolve</button>}</td>
              </tr>
            ))}
            {items.length === 0 && <tr><td colSpan={6} className="muted">No grievances.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
