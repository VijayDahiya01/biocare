"use client";
// Events: create an event, bulk-import delegates (CSV), view footfall.
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api, apiUpload } from "../../../lib/api";

type Event = { event_id: string; name: string };

export default function Events() {
  const router = useRouter();
  const [items, setItems] = useState<Event[]>([]);
  const [name, setName] = useState("");
  const [selected, setSelected] = useState("");
  const [footfall, setFootfall] = useState<any[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function load() {
    try { setItems((await api<{ items: Event[] }>("/events")).items); }
    catch (e) { if (e instanceof ApiError && e.status === 401) router.push("/admin/login"); }
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  async function createEvent(e: React.FormEvent) {
    e.preventDefault(); setErr(null);
    try {
      await api("/events", { method: "POST", body: { name: name.trim() } });
      setName(""); load();
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Failed"); }
  }

  async function importCsv() {
    setErr(null); setMsg(null);
    const file = fileRef.current?.files?.[0];
    if (!file || !selected) { setErr("Pick an event and a CSV file."); return; }
    const fd = new FormData();
    fd.append("event_id", selected);
    fd.append("file", file);
    try {
      const d = await apiUpload<{ created: number }>("/events/import", fd);
      setMsg(`Imported ${d.created} delegates (pending face capture).`);
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Import failed"); }
  }

  async function loadFootfall(id: string) {
    try { setFootfall((await api<{ by_zone: any[] }>(`/events/${id}/footfall`)).by_zone); }
    catch { /* ignore */ }
  }

  return (
    <div>
      <h1>Events</h1>
      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", marginTop: 16 }}>
        <form className="card" onSubmit={createEvent}>
          <h2>Create event</h2>
          <label>Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Tech Conf 2026" required />
          <button type="submit" style={{ width: "100%", marginTop: 14 }}>Create</button>
        </form>

        <div className="card">
          <h2>Bulk import delegates</h2>
          <label>Event</label>
          <select value={selected} onChange={(e) => { setSelected(e.target.value); loadFootfall(e.target.value); }}>
            <option value="">Select…</option>
            {items.map((ev) => <option key={ev.event_id} value={ev.event_id}>{ev.name}</option>)}
          </select>
          <label>CSV file (first_name,last_name,email,member_id)</label>
          <input ref={fileRef} type="file" accept=".csv" />
          {msg && <div className="muted" style={{ color: "#166534", marginTop: 8 }}>{msg}</div>}
          <button onClick={importCsv} style={{ width: "100%", marginTop: 14 }}>Import</button>
        </div>
      </div>
      {err && <div className="error">{err}</div>}

      {selected && (
        <div className="card" style={{ marginTop: 16 }}>
          <h2>Footfall by zone (today)</h2>
          <table>
            <thead><tr><th>Zone</th><th>Count</th></tr></thead>
            <tbody>
              {footfall.map((f, i) => <tr key={i}><td>{f.zone_id}</td><td>{f.count}</td></tr>)}
              {footfall.length === 0 && <tr><td colSpan={2} className="muted">No footfall yet.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
