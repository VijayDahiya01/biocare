"use client";
// A17/A18 — Settings: branding, DPDP config, match threshold + outbound webhooks.
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../lib/api";

type Settings = { branding: any; dpdp: any; settings: any; vertical: string; plan: string };
type Hook = { id: string; event: string; url: string; active: boolean };

const EVENTS = ["access.granted", "access.denied", "attendance.recorded", "blacklist.hit", "visitor.arrived", "badge.print"];

export default function SettingsPage() {
  const router = useRouter();
  const [s, setS] = useState<Settings | null>(null);
  const [hooks, setHooks] = useState<Hook[]>([]);
  const [displayName, setDisplayName] = useState("");
  const [color, setColor] = useState("#1F3A5F");
  const [dpo, setDpo] = useState("");
  const [retention, setRetention] = useState("1095");
  const [threshold, setThreshold] = useState("0.5");
  const [hook, setHook] = useState({ event: EVENTS[0], url: "", secret: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    try {
      const [cfg, hk] = await Promise.all([
        api<Settings>("/settings"),
        api<{ items: Hook[] }>("/settings/webhooks"),
      ]);
      setS(cfg); setHooks(hk.items);
      setDisplayName(cfg.branding?.display_name || "");
      setColor(cfg.branding?.primary_color || "#1F3A5F");
      setDpo(cfg.dpdp?.dpo_email || "");
      setRetention(String(cfg.dpdp?.retention_days ?? 1095));
      setThreshold(String(cfg.settings?.match_threshold ?? 0.5));
    } catch (e) { if (e instanceof ApiError && e.status === 401) router.push("/admin/login"); }
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault(); setErr(null); setMsg(null);
    try {
      await api("/settings", { method: "PATCH", body: {
        branding: { display_name: displayName, primary_color: color },
        dpdp: { dpo_email: dpo, retention_days: Number(retention) },
        match_threshold: Number(threshold),
      }});
      setMsg("Saved.");
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Failed"); }
  }

  async function addHook(e: React.FormEvent) {
    e.preventDefault(); setErr(null);
    try {
      await api("/settings/webhooks", { method: "POST", body: hook });
      setHook({ event: EVENTS[0], url: "", secret: "" }); load();
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Failed"); }
  }

  async function delHook(id: string) {
    await api(`/settings/webhooks/${id}`, { method: "DELETE" }).catch(() => {});
    load();
  }

  if (!s) return <div><h1>Settings</h1><p className="muted">Loading…</p></div>;

  return (
    <div>
      <h1>Settings</h1>
      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", marginTop: 16 }}>
        <form className="card" onSubmit={save}>
          <h2>Organisation ({s.vertical} · {s.plan})</h2>
          <label>Display name</label>
          <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
          <label>Primary colour</label>
          <input value={color} onChange={(e) => setColor(e.target.value)} />
          <label>DPO email</label>
          <input value={dpo} onChange={(e) => setDpo(e.target.value)} placeholder="privacy@acme.com" />
          <label>Retention (days)</label>
          <input type="number" value={retention} onChange={(e) => setRetention(e.target.value)} />
          <label>Match threshold (0–1)</label>
          <input type="number" step="0.01" min="0" max="1" value={threshold} onChange={(e) => setThreshold(e.target.value)} />
          {msg && <div className="muted" style={{ color: "#166534", marginTop: 10 }}>{msg}</div>}
          <button type="submit" style={{ width: "100%", marginTop: 14 }}>Save settings</button>
        </form>

        <div className="card">
          <h2>Webhooks</h2>
          <form onSubmit={addHook} style={{ marginBottom: 12 }}>
            <label>Event</label>
            <select value={hook.event} onChange={(e) => setHook({ ...hook, event: e.target.value })}>
              {EVENTS.map((ev) => <option key={ev} value={ev}>{ev}</option>)}
            </select>
            <label>URL</label>
            <input value={hook.url} onChange={(e) => setHook({ ...hook, url: e.target.value })} placeholder="https://…" required />
            <label>Secret (HMAC)</label>
            <input value={hook.secret} onChange={(e) => setHook({ ...hook, secret: e.target.value })} required />
            <button type="submit" style={{ width: "100%", marginTop: 12 }}>Add webhook</button>
          </form>
          <table>
            <thead><tr><th>Event</th><th>URL</th><th></th></tr></thead>
            <tbody>
              {hooks.map((h) => (
                <tr key={h.id}>
                  <td>{h.event}</td>
                  <td style={{ maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis" }}>{h.url}</td>
                  <td><button className="ghost" style={{ color: "#dc2626" }} onClick={() => delHook(h.id)}>Remove</button></td>
                </tr>
              ))}
              {hooks.length === 0 && <tr><td colSpan={3} className="muted">No webhooks.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      {err && <div className="error">{err}</div>}
    </div>
  );
}
