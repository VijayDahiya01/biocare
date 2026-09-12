"use client";
// Geofences: allowed areas for GPS field check-in.
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../lib/api";

type Fence = { id: string; name: string; center_lat: number; center_lng: number; radius_km: number };

export default function Geofences() {
  const router = useRouter();
  const [items, setItems] = useState<Fence[]>([]);
  const [form, setForm] = useState({ name: "", center_lat: "", center_lng: "", radius_km: "1" });
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    try { setItems((await api<{ items: Fence[] }>("/geofences")).items); }
    catch (e) { if (e instanceof ApiError && e.status === 401) router.push("/admin/login"); }
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault(); setErr(null);
    try {
      await api("/geofences", { method: "POST", body: {
        name: form.name.trim(), center_lat: Number(form.center_lat),
        center_lng: Number(form.center_lng), radius_km: Number(form.radius_km),
      }});
      setForm({ name: "", center_lat: "", center_lng: "", radius_km: "1" }); load();
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Failed"); }
  }

  return (
    <div>
      <h1>Geofences</h1>
      <form className="card" style={{ marginTop: 16, display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }} onSubmit={create}>
        <div style={{ flex: 1, minWidth: 140 }}><label>Name</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></div>
        <div style={{ width: 130 }}><label>Latitude</label><input type="number" step="any" value={form.center_lat} onChange={(e) => setForm({ ...form, center_lat: e.target.value })} required /></div>
        <div style={{ width: 130 }}><label>Longitude</label><input type="number" step="any" value={form.center_lng} onChange={(e) => setForm({ ...form, center_lng: e.target.value })} required /></div>
        <div style={{ width: 110 }}><label>Radius (km)</label><input type="number" step="any" value={form.radius_km} onChange={(e) => setForm({ ...form, radius_km: e.target.value })} required /></div>
        <button type="submit">Add</button>
      </form>
      {err && <div className="error">{err}</div>}

      <div className="card" style={{ marginTop: 16 }}>
        <table>
          <thead><tr><th>Name</th><th>Centre</th><th>Radius</th></tr></thead>
          <tbody>
            {items.map((f) => (
              <tr key={f.id}><td>{f.name}</td><td>{f.center_lat}, {f.center_lng}</td><td>{f.radius_km} km</td></tr>
            ))}
            {items.length === 0 && <tr><td colSpan={3} className="muted">No geofences.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
