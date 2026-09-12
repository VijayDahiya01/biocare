"use client";
// Timetable (school): list/create periods, view per-period attendance.
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../lib/api";

type TT = { session_id: string; class_id: string; subject: string | null; day_of_week: number;
            start_time: string; end_time: string };
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function Timetable() {
  const router = useRouter();
  const [items, setItems] = useState<TT[]>([]);
  const [form, setForm] = useState({ class_id: "", subject: "", day_of_week: "0", start_time: "", end_time: "" });
  const [present, setPresent] = useState<{ session: string; rows: any[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    try { setItems((await api<{ items: TT[] }>("/timetable")).items); }
    catch (e) { if (e instanceof ApiError && e.status === 401) router.push("/admin/login"); }
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault(); setErr(null);
    try {
      await api("/timetable", { method: "POST", body: {
        class_id: form.class_id.trim(), subject: form.subject.trim() || null,
        day_of_week: Number(form.day_of_week), start_time: form.start_time, end_time: form.end_time,
      }});
      setForm({ class_id: "", subject: "", day_of_week: "0", start_time: "", end_time: "" }); load();
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Failed"); }
  }

  async function viewSession(id: string) {
    try {
      const d = await api<{ present: any[] }>(`/attendance/session?session_id=${id}`);
      setPresent({ session: id, rows: d.present });
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Failed"); }
  }

  return (
    <div>
      <h1>Timetable</h1>
      <form className="card" style={{ marginTop: 16, display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }} onSubmit={create}>
        <div style={{ width: 120 }}><label>Class</label><input value={form.class_id} onChange={(e) => setForm({ ...form, class_id: e.target.value })} required /></div>
        <div style={{ width: 140 }}><label>Subject</label><input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} /></div>
        <div style={{ width: 110 }}><label>Day</label>
          <select value={form.day_of_week} onChange={(e) => setForm({ ...form, day_of_week: e.target.value })}>
            {DAYS.map((d, i) => <option key={i} value={i}>{d}</option>)}
          </select>
        </div>
        <div style={{ width: 110 }}><label>Start</label><input type="time" value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} required /></div>
        <div style={{ width: 110 }}><label>End</label><input type="time" value={form.end_time} onChange={(e) => setForm({ ...form, end_time: e.target.value })} required /></div>
        <button type="submit">Add period</button>
      </form>
      {err && <div className="error">{err}</div>}

      <div className="card" style={{ marginTop: 16 }}>
        <table>
          <thead><tr><th>Class</th><th>Subject</th><th>Day</th><th>Time</th><th></th></tr></thead>
          <tbody>
            {items.map((t) => (
              <tr key={t.session_id}>
                <td>{t.class_id}</td><td>{t.subject || "—"}</td><td>{DAYS[t.day_of_week]}</td>
                <td>{t.start_time}–{t.end_time}</td>
                <td><button className="ghost" onClick={() => viewSession(t.session_id)}>Attendance</button></td>
              </tr>
            ))}
            {items.length === 0 && <tr><td colSpan={5} className="muted">No periods.</td></tr>}
          </tbody>
        </table>
      </div>

      {present && (
        <div className="card" style={{ marginTop: 16 }}>
          <h2>Present this period (today)</h2>
          <table>
            <thead><tr><th>Name</th><th>At</th></tr></thead>
            <tbody>
              {present.rows.map((r, i) => <tr key={i}><td>{r.name}</td><td>{new Date(r.at).toLocaleTimeString()}</td></tr>)}
              {present.rows.length === 0 && <tr><td colSpan={2} className="muted">Nobody checked in during this period today.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
