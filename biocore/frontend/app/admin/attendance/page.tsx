"use client";
// A3 — Attendance log with date + department filters.
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../lib/api";

type Item = { name: string; event_type: string; timestamp: string; department: string | null; device_id: string | null };

export default function AttendanceLog() {
  const router = useRouter();
  const [items, setItems] = useState<Item[]>([]);
  const [total, setTotal] = useState(0);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [dept, setDept] = useState("");
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    const q = new URLSearchParams({ page: String(page), page_size: "50" });
    if (from) q.set("from", from);
    if (to) q.set("to", to);
    if (dept) q.set("department", dept);
    try {
      const d = await api<{ items: Item[]; total: number }>(`/attendance?${q}`);
      setItems(d.items); setTotal(d.total);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/admin/login");
    }
  }, [from, to, dept, page, router]);

  useEffect(() => { load(); }, [load]);

  return (
    <div>
      <h1>Attendance log</h1>
      <div className="card" style={{ display: "flex", gap: 12, alignItems: "flex-end", marginTop: 16 }}>
        <div style={{ flex: 1 }}><label>From</label><input type="date" value={from} onChange={(e) => { setFrom(e.target.value); setPage(1); }} /></div>
        <div style={{ flex: 1 }}><label>To</label><input type="date" value={to} onChange={(e) => { setTo(e.target.value); setPage(1); }} /></div>
        <div style={{ flex: 1 }}><label>Department</label><input value={dept} onChange={(e) => { setDept(e.target.value); setPage(1); }} placeholder="All" /></div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <table>
          <thead><tr><th>Name</th><th>Event</th><th>Department</th><th>Time</th></tr></thead>
          <tbody>
            {items.map((it, i) => (
              <tr key={i}>
                <td>{it.name}</td>
                <td><span className={`badge ${it.event_type === "check_in" ? "green" : "amber"}`}>{it.event_type}</span></td>
                <td>{it.department || "—"}</td>
                <td>{new Date(it.timestamp).toLocaleString()}</td>
              </tr>
            ))}
            {items.length === 0 && <tr><td colSpan={4} className="muted">No records.</td></tr>}
          </tbody>
        </table>
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 12 }}>
          <span className="muted">{total} records</span>
          <span>
            <button className="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Prev</button>{" "}
            <span className="muted">page {page}</span>{" "}
            <button className="secondary" disabled={page * 50 >= total} onClick={() => setPage((p) => p + 1)}>Next</button>
          </span>
        </div>
      </div>
    </div>
  );
}
