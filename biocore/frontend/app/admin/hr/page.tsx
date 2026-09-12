"use client";
// A15 — HR / payroll: summary, wage config, payroll run + CSV export.
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api, apiDownload } from "../../../lib/api";

type Summary = { headcount: number; present_today: number; on_leave: number };
type PayItem = { user_id: string; name: string; regular_hours: number; overtime_hours: number;
                 base_pay: number; overtime_pay: number; total: number };
type U = { user_id: string; name: string };

export default function HR() {
  const router = useRouter();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [users, setUsers] = useState<U[]>([]);
  const [wage, setWage] = useState({ user_id: "", rate_per_hour: "", overtime_multiplier: "1.5", effective_from: "" });
  const [range, setRange] = useState({ from: "", to: "" });
  const [items, setItems] = useState<PayItem[]>([]);
  const [totalPayable, setTotalPayable] = useState(0);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api<Summary>("/hr/summary"), api<{ items: U[] }>("/users?status=active&page_size=200")])
      .then(([s, u]) => { setSummary(s); setUsers(u.items); })
      .catch((e) => { if (e instanceof ApiError && e.status === 401) router.push("/admin/login"); });
  }, [router]);

  async function saveWage(e: React.FormEvent) {
    e.preventDefault(); setErr(null); setMsg(null);
    try {
      await api("/wage-config", { method: "POST", body: {
        user_id: wage.user_id, rate_per_hour: Number(wage.rate_per_hour),
        overtime_multiplier: Number(wage.overtime_multiplier), effective_from: wage.effective_from,
      }});
      setMsg("Wage configuration saved.");
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Failed"); }
  }

  async function runPayroll(e: React.FormEvent) {
    e.preventDefault(); setErr(null);
    try {
      const d = await api<{ items: PayItem[]; total_payable: number }>(`/payroll/calculate?from=${range.from}&to=${range.to}`);
      setItems(d.items); setTotalPayable(d.total_payable);
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Failed"); }
  }

  async function exportCsv() {
    try { await apiDownload(`/payroll/export?from=${range.from}&to=${range.to}&format=csv`, "payroll.csv"); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Export failed"); }
  }

  return (
    <div>
      <h1>HR / Payroll</h1>
      <div className="grid cols-4" style={{ marginTop: 16 }}>
        <div className="metric"><div className="n">{summary?.headcount ?? "—"}</div><div className="l">Headcount</div></div>
        <div className="metric"><div className="n">{summary?.present_today ?? "—"}</div><div className="l">Present today</div></div>
        <div className="metric"><div className="n">{summary?.on_leave ?? "—"}</div><div className="l">On leave</div></div>
        <div className="metric"><div className="n">₹{totalPayable.toLocaleString()}</div><div className="l">Payable (range)</div></div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", marginTop: 20 }}>
        <form className="card" onSubmit={saveWage}>
          <h2>Wage configuration</h2>
          <label>Worker</label>
          <select value={wage.user_id} onChange={(e) => setWage({ ...wage, user_id: e.target.value })} required>
            <option value="">Select…</option>
            {users.map((u) => <option key={u.user_id} value={u.user_id}>{u.name}</option>)}
          </select>
          <label>Rate per hour (₹)</label>
          <input type="number" value={wage.rate_per_hour} onChange={(e) => setWage({ ...wage, rate_per_hour: e.target.value })} required />
          <label>Overtime multiplier</label>
          <input type="number" step="0.1" value={wage.overtime_multiplier} onChange={(e) => setWage({ ...wage, overtime_multiplier: e.target.value })} />
          <label>Effective from</label>
          <input type="date" value={wage.effective_from} onChange={(e) => setWage({ ...wage, effective_from: e.target.value })} required />
          {msg && <div className="muted" style={{ color: "#166534", marginTop: 10 }}>{msg}</div>}
          <button type="submit" style={{ width: "100%", marginTop: 14 }}>Save wage</button>
        </form>

        <form className="card" onSubmit={runPayroll}>
          <h2>Run payroll</h2>
          <label>From</label>
          <input type="date" value={range.from} onChange={(e) => setRange({ ...range, from: e.target.value })} required />
          <label>To</label>
          <input type="date" value={range.to} onChange={(e) => setRange({ ...range, to: e.target.value })} required />
          <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
            <button type="submit" style={{ flex: 1 }}>Calculate</button>
            <button type="button" className="secondary" onClick={exportCsv} disabled={!range.from || !range.to}>Export CSV</button>
          </div>
        </form>
      </div>
      {err && <div className="error">{err}</div>}

      {items.length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <table>
            <thead><tr><th>Name</th><th>Regular h</th><th>OT h</th><th>Base ₹</th><th>OT ₹</th><th>Total ₹</th></tr></thead>
            <tbody>
              {items.map((it) => (
                <tr key={it.user_id}>
                  <td>{it.name}</td><td>{it.regular_hours}</td><td>{it.overtime_hours}</td>
                  <td>{it.base_pay}</td><td>{it.overtime_pay}</td><td><b>{it.total}</b></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
