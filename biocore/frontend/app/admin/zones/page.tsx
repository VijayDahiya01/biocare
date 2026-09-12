"use client";
// A8 — Zones: list + create (entry/restricted/amenity, optional time window).
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../lib/api";

type Zone = { zone_id: string; name: string; type: string; access_rule: any; door_webhook_url: string | null };

export default function Zones() {
  const router = useRouter();
  const [items, setItems] = useState<Zone[]>([]);
  const [name, setName] = useState("");
  const [type, setType] = useState("entry_exit");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [webhook, setWebhook] = useState("");
  const [requirePpe, setRequirePpe] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    try { setItems((await api<{ items: Zone[] }>("/zones")).items); }
    catch (e) { if (e instanceof ApiError && e.status === 401) router.push("/admin/login"); }
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    const access_rule: any = {};
    if (from && to) access_rule.time_windows = [{ from, to }];
    if (requirePpe) { access_rule.require_ppe = true; access_rule.ppe_items = ["helmet", "vest"]; }
    try {
      await api("/zones", { method: "POST", body: {
        name: name.trim(), type, access_rule, door_webhook_url: webhook.trim() || null,
      }});
      setName(""); setFrom(""); setTo(""); setWebhook(""); setRequirePpe(false); load();
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Failed"); }
  }

  return (
    <div>
      <h1>Zones</h1>
      <form className="card" style={{ marginTop: 16, display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }} onSubmit={create}>
        <div style={{ flex: 1, minWidth: 160 }}><label>Name</label><input value={name} onChange={(e) => setName(e.target.value)} placeholder="Server room" required /></div>
        <div style={{ width: 160 }}><label>Type</label>
          <select value={type} onChange={(e) => setType(e.target.value)}>
            <option value="entry_exit">Entry / exit</option>
            <option value="restricted">Restricted</option>
            <option value="amenity">Amenity</option>
          </select>
        </div>
        <div style={{ width: 110 }}><label>From</label><input type="time" value={from} onChange={(e) => setFrom(e.target.value)} /></div>
        <div style={{ width: 110 }}><label>To</label><input type="time" value={to} onChange={(e) => setTo(e.target.value)} /></div>
        <div style={{ flex: 1, minWidth: 160 }}><label>Door webhook URL</label><input value={webhook} onChange={(e) => setWebhook(e.target.value)} placeholder="optional" /></div>
        <label className="checkbox" style={{ alignItems: "center", marginBottom: 6 }}>
          <input type="checkbox" checked={requirePpe} onChange={(e) => setRequirePpe(e.target.checked)} />
          <span>Require PPE</span>
        </label>
        <button type="submit">Add zone</button>
      </form>
      {err && <div className="error">{err}</div>}

      <div className="card" style={{ marginTop: 16 }}>
        <table>
          <thead><tr><th>Name</th><th>Type</th><th>Hours</th><th>PPE</th><th>Door</th></tr></thead>
          <tbody>
            {items.map((z) => {
              const w = z.access_rule?.time_windows?.[0];
              return (
                <tr key={z.zone_id}>
                  <td>{z.name}</td>
                  <td><span className={`badge ${z.type === "restricted" ? "red" : z.type === "amenity" ? "amber" : "gray"}`}>{z.type}</span></td>
                  <td>{w ? `${w.from}–${w.to}` : "always"}</td>
                  <td>{z.access_rule?.require_ppe ? <span className="badge amber">required</span> : "—"}</td>
                  <td>{z.door_webhook_url ? "linked" : "—"}</td>
                </tr>
              );
            })}
            {items.length === 0 && <tr><td colSpan={5} className="muted">No zones yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
