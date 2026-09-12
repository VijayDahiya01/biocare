"use client";
// M3 — My leave: balance, request form, my requests.
import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "../../../lib/api";

type Leave = { leave_id: string; type: string; from: string; to: string; status: string };
type Balance = { casual: number; sick: number; earned: number; used: Record<string, number> };

export default function MyLeave() {
  const [balance, setBalance] = useState<Balance | null>(null);
  const [items, setItems] = useState<Leave[]>([]);
  const [form, setForm] = useState({ type: "casual", from: "", to: "", reason: "" });
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const me = await api<{ user_id: string }>("/auth/me");
      const [bal, mine] = await Promise.all([
        api<Balance>(`/leave/balance/${me.user_id}`),
        api<{ items: Leave[] }>("/leave"),
      ]);
      setBalance(bal); setItems(mine.items);
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Could not load"); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr(null); setMsg(null);
    try {
      await api("/leave", { method: "POST", body: { type: form.type, from: form.from, to: form.to, reason: form.reason || null } });
      setMsg("Request submitted."); setForm({ type: "casual", from: "", to: "", reason: "" }); load();
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Failed"); }
  }

  return (
    <div className="container">
      <p className="muted"><a href="/me">← My portal</a></p>
      <h1>My leave</h1>
      {err && <div className="error">{err} — <a href="/me/login">sign in</a></div>}

      {balance && (
        <div className="grid cols-4" style={{ marginTop: 12 }}>
          <div className="metric"><div className="n">{balance.casual}</div><div className="l">Casual left</div></div>
          <div className="metric"><div className="n">{balance.sick}</div><div className="l">Sick left</div></div>
          <div className="metric"><div className="n">{balance.earned}</div><div className="l">Earned left</div></div>
          <div className="metric"><div className="n">{items.length}</div><div className="l">My requests</div></div>
        </div>
      )}

      <div className="grid" style={{ gridTemplateColumns: "1fr 2fr", marginTop: 16 }}>
        <form className="card" onSubmit={submit}>
          <h2>Request leave</h2>
          <label>Type</label>
          <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
            <option value="casual">Casual</option><option value="sick">Sick</option>
            <option value="earned">Earned</option><option value="unpaid">Unpaid</option>
          </select>
          <label>From</label>
          <input type="date" value={form.from} onChange={(e) => setForm({ ...form, from: e.target.value })} required />
          <label>To</label>
          <input type="date" value={form.to} onChange={(e) => setForm({ ...form, to: e.target.value })} required />
          <label>Reason</label>
          <input value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} />
          {msg && <div className="muted" style={{ color: "#166534", marginTop: 8 }}>{msg}</div>}
          <button type="submit" style={{ width: "100%", marginTop: 14 }}>Submit</button>
        </form>

        <div className="card">
          <h2>My requests</h2>
          <table>
            <thead><tr><th>Type</th><th>From</th><th>To</th><th>Status</th></tr></thead>
            <tbody>
              {items.map((l) => (
                <tr key={l.leave_id}>
                  <td>{l.type}</td><td>{l.from}</td><td>{l.to}</td>
                  <td><span className={`badge ${l.status === "approved" ? "green" : l.status === "rejected" ? "red" : "amber"}`}>{l.status}</span></td>
                </tr>
              ))}
              {items.length === 0 && <tr><td colSpan={4} className="muted">No requests yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
