"use client";
// Memberships (gym): expiring list + create/renew.
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../lib/api";

type Expiring = { user_id: string; name: string; plan_type: string; end_date: string };
type U = { user_id: string; name: string };

export default function Memberships() {
  const router = useRouter();
  const [expiring, setExpiring] = useState<Expiring[]>([]);
  const [users, setUsers] = useState<U[]>([]);
  const [form, setForm] = useState({ user_id: "", plan_type: "monthly", start_date: "", amount_paid: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    try {
      const [ex, u] = await Promise.all([
        api<{ items: Expiring[] }>("/memberships/expiring?days=30"),
        api<{ items: U[] }>("/users?status=active&page_size=200"),
      ]);
      setExpiring(ex.items); setUsers(u.items);
    } catch (e) { if (e instanceof ApiError && e.status === 401) router.push("/admin/login"); }
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault(); setErr(null); setMsg(null);
    try {
      const d = await api<{ end_date: string }>("/memberships", { method: "POST", body: {
        user_id: form.user_id, plan_type: form.plan_type, start_date: form.start_date,
        amount_paid: form.amount_paid ? Number(form.amount_paid) : null,
      }});
      setMsg(`Membership active until ${d.end_date}.`);
      setForm({ user_id: "", plan_type: "monthly", start_date: "", amount_paid: "" }); load();
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Failed"); }
  }

  return (
    <div>
      <h1>Memberships</h1>
      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", marginTop: 16 }}>
        <form className="card" onSubmit={create}>
          <h2>New / renew</h2>
          <label>Member</label>
          <select value={form.user_id} onChange={(e) => setForm({ ...form, user_id: e.target.value })} required>
            <option value="">Select…</option>
            {users.map((u) => <option key={u.user_id} value={u.user_id}>{u.name}</option>)}
          </select>
          <label>Plan</label>
          <select value={form.plan_type} onChange={(e) => setForm({ ...form, plan_type: e.target.value })}>
            <option value="monthly">Monthly</option><option value="quarterly">Quarterly</option><option value="annual">Annual</option>
          </select>
          <label>Start date</label>
          <input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} required />
          <label>Amount paid (₹)</label>
          <input type="number" value={form.amount_paid} onChange={(e) => setForm({ ...form, amount_paid: e.target.value })} />
          {msg && <div className="muted" style={{ color: "#166534", marginTop: 8 }}>{msg}</div>}
          <button type="submit" style={{ width: "100%", marginTop: 14 }}>Save</button>
        </form>

        <div className="card">
          <h2>Expiring within 30 days</h2>
          <table>
            <thead><tr><th>Member</th><th>Plan</th><th>Ends</th></tr></thead>
            <tbody>
              {expiring.map((m) => (
                <tr key={m.user_id}><td>{m.name}</td><td>{m.plan_type}</td><td>{m.end_date}</td></tr>
              ))}
              {expiring.length === 0 && <tr><td colSpan={3} className="muted">None expiring soon.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      {err && <div className="error">{err}</div>}
    </div>
  );
}
