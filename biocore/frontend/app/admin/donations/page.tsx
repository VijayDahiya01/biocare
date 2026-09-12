"use client";
// Donations (religious): record a donation, view donor history + 80G receipt.
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../lib/api";

type U = { user_id: string; name: string };
type D = { donation_id: string; amount: number; purpose: string; receipt_url: string; at: string };

export default function Donations() {
  const router = useRouter();
  const [users, setUsers] = useState<U[]>([]);
  const [form, setForm] = useState({ donor_user_id: "", amount: "", purpose: "general" });
  const [history, setHistory] = useState<D[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api<{ items: U[] }>("/users?status=active&page_size=200").then((u) => setUsers(u.items))
      .catch((e) => { if (e instanceof ApiError && e.status === 401) router.push("/admin/login"); });
  }, [router]);

  async function record(e: React.FormEvent) {
    e.preventDefault(); setErr(null);
    try {
      await api("/donations", { method: "POST", body: {
        donor_user_id: form.donor_user_id, amount: Number(form.amount), purpose: form.purpose,
      }});
      loadHistory(form.donor_user_id);
      setForm({ ...form, amount: "" });
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Failed"); }
  }

  async function loadHistory(donorId: string) {
    if (!donorId) return;
    try { setHistory((await api<{ items: D[] }>(`/donations/${donorId}`)).items); }
    catch { /* ignore */ }
  }

  return (
    <div>
      <h1>Donations</h1>
      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", marginTop: 16 }}>
        <form className="card" onSubmit={record}>
          <h2>Record donation</h2>
          <label>Donor</label>
          <select value={form.donor_user_id}
                  onChange={(e) => { setForm({ ...form, donor_user_id: e.target.value }); loadHistory(e.target.value); }} required>
            <option value="">Select…</option>
            {users.map((u) => <option key={u.user_id} value={u.user_id}>{u.name}</option>)}
          </select>
          <label>Amount (₹)</label>
          <input type="number" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} required />
          <label>Purpose</label>
          <input value={form.purpose} onChange={(e) => setForm({ ...form, purpose: e.target.value })} />
          <button type="submit" style={{ width: "100%", marginTop: 14 }}>Record &amp; issue 80G</button>
        </form>

        <div className="card">
          <h2>Donor history</h2>
          <table>
            <thead><tr><th>Amount</th><th>Purpose</th><th>Receipt</th><th>When</th></tr></thead>
            <tbody>
              {history.map((d) => (
                <tr key={d.donation_id}>
                  <td>₹{d.amount}</td><td>{d.purpose}</td>
                  <td><a href={d.receipt_url}>80G</a></td>
                  <td>{new Date(d.at).toLocaleDateString()}</td>
                </tr>
              ))}
              {history.length === 0 && <tr><td colSpan={4} className="muted">Select a donor to see history.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      {err && <div className="error">{err}</div>}
    </div>
  );
}
