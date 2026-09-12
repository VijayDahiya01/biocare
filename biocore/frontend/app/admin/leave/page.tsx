"use client";
// Admin leave management: list requests, approve/reject.
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../lib/api";

type Leave = { leave_id: string; user_id: string; type: string; from: string; to: string;
               reason: string | null; status: string };

const stClass = (s: string) => (s === "approved" ? "green" : s === "rejected" ? "red" : "amber");

export default function AdminLeave() {
  const router = useRouter();
  const [items, setItems] = useState<Leave[]>([]);
  const [status, setStatus] = useState("pending");

  const load = useCallback(async () => {
    const q = status ? `?status=${status}` : "";
    try { setItems((await api<{ items: Leave[] }>(`/leave${q}`)).items); }
    catch (e) { if (e instanceof ApiError && e.status === 401) router.push("/admin/login"); }
  }, [status, router]);

  useEffect(() => { load(); }, [load]);

  async function decide(id: string, action: "approve" | "reject") {
    await api(`/leave/${id}/${action}`, { method: "POST", body: {} }).catch(() => {});
    load();
  }

  return (
    <div>
      <h1>Leave requests</h1>
      <div className="card" style={{ marginTop: 16, maxWidth: 220 }}>
        <label>Status</label>
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>
      <div className="card" style={{ marginTop: 16 }}>
        <table>
          <thead><tr><th>User</th><th>Type</th><th>From</th><th>To</th><th>Reason</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {items.map((l) => (
              <tr key={l.leave_id}>
                <td>{l.user_id.slice(0, 8)}</td>
                <td>{l.type}</td>
                <td>{l.from}</td>
                <td>{l.to}</td>
                <td>{l.reason || "—"}</td>
                <td><span className={`badge ${stClass(l.status)}`}>{l.status}</span></td>
                <td>
                  {l.status === "pending" && (
                    <>
                      <button className="ghost" style={{ color: "#16a34a" }} onClick={() => decide(l.leave_id, "approve")}>Approve</button>
                      <button className="ghost" style={{ color: "#dc2626" }} onClick={() => decide(l.leave_id, "reject")}>Reject</button>
                    </>
                  )}
                </td>
              </tr>
            ))}
            {items.length === 0 && <tr><td colSpan={7} className="muted">No requests.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
