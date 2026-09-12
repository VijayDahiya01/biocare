"use client";
// A16 — Audit log viewer (read-only). Immutable trail of every significant action.
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../lib/api";

type Row = { action: string; actor_id: string | null; target_id: string | null;
             request_id: string | null; metadata: any; created_at: string };

export default function Audit() {
  const router = useRouter();
  const [items, setItems] = useState<Row[]>([]);
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    const q = new URLSearchParams({ page: String(page), page_size: "50" });
    if (action) q.set("action", action);
    try { setItems((await api<{ items: Row[] }>(`/audit?${q}`)).items); }
    catch (e) { if (e instanceof ApiError && e.status === 401) router.push("/admin/login"); }
  }, [action, page, router]);

  useEffect(() => { load(); }, [load]);

  return (
    <div>
      <h1>Audit log</h1>
      <div className="card" style={{ marginTop: 16, maxWidth: 280 }}>
        <label>Action filter</label>
        <input value={action} onChange={(e) => { setAction(e.target.value.toUpperCase()); setPage(1); }}
               placeholder="e.g. ERASURE_COMPLETE" />
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <table>
          <thead><tr><th>Action</th><th>Actor</th><th>Target</th><th>Request</th><th>When</th></tr></thead>
          <tbody>
            {items.map((r, i) => (
              <tr key={i}>
                <td><code>{r.action}</code></td>
                <td>{r.actor_id ? r.actor_id.slice(0, 8) : "—"}</td>
                <td>{r.target_id ? r.target_id.slice(0, 8) : "—"}</td>
                <td>{r.request_id || "—"}</td>
                <td>{new Date(r.created_at).toLocaleString()}</td>
              </tr>
            ))}
            {items.length === 0 && <tr><td colSpan={5} className="muted">No entries.</td></tr>}
          </tbody>
        </table>
        <div style={{ marginTop: 12 }}>
          <button className="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Prev</button>{" "}
          <span className="muted">page {page}</span>{" "}
          <button className="secondary" disabled={items.length < 50} onClick={() => setPage((p) => p + 1)}>Next</button>
        </div>
      </div>
    </div>
  );
}
