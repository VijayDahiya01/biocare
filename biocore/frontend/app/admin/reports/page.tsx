"use client";
// A13 — Reports: pick a report + range, view a table, export CSV.
import { useState } from "react";
import { ApiError, api, apiDownload } from "../../../lib/api";

const REPORTS = [
  ["attendance", "Attendance"],
  ["late", "Late arrivals"],
  ["absent", "Absentees"],
  ["zone-access", "Zone access"],
  ["footfall", "Footfall"],
] as const;

const EXPORTABLE = new Set(["attendance", "late", "zone-access", "footfall"]);

export default function Reports() {
  const [report, setReport] = useState("attendance");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [on, setOn] = useState("");
  const [rows, setRows] = useState<any[]>([]);
  const [err, setErr] = useState<string | null>(null);

  async function run(e: React.FormEvent) {
    e.preventDefault(); setErr(null); setRows([]);
    try {
      let path = "";
      if (report === "absent") path = `/reports/absent?on=${on}`;
      else path = `/reports/${report}?from=${from}&to=${to}`;
      const d = await api<{ items: any[] }>(path);
      setRows(d.items);
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Failed"); }
  }

  async function exportCsv() {
    try { await apiDownload(`/reports/export?report=${report}&from=${from}&to=${to}&format=csv`, `${report}.csv`); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Export failed"); }
  }

  const cols = rows[0] ? Object.keys(rows[0]) : [];

  return (
    <div>
      <h1>Reports</h1>
      <form className="card" style={{ marginTop: 16, display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }} onSubmit={run}>
        <div style={{ width: 180 }}><label>Report</label>
          <select value={report} onChange={(e) => setReport(e.target.value)}>
            {REPORTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
        </div>
        {report === "absent" ? (
          <div style={{ width: 160 }}><label>On date</label><input type="date" value={on} onChange={(e) => setOn(e.target.value)} required /></div>
        ) : (
          <>
            <div style={{ width: 160 }}><label>From</label><input type="date" value={from} onChange={(e) => setFrom(e.target.value)} required /></div>
            <div style={{ width: 160 }}><label>To</label><input type="date" value={to} onChange={(e) => setTo(e.target.value)} required /></div>
          </>
        )}
        <button type="submit">Run</button>
        {EXPORTABLE.has(report) && report !== "absent" && (
          <button type="button" className="secondary" onClick={exportCsv} disabled={!from || !to}>Export CSV</button>
        )}
      </form>
      {err && <div className="error">{err}</div>}

      <div className="card" style={{ marginTop: 16 }}>
        <table>
          <thead><tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>
            {rows.map((r, i) => <tr key={i}>{cols.map((c) => <td key={c}>{String(r[c])}</td>)}</tr>)}
            {rows.length === 0 && <tr><td className="muted">Run a report to see results.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
