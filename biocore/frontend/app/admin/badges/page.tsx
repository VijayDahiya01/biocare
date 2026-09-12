"use client";
// A9 — Badges: list + create (zones, time rule, expiry) + assign to a user.
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../lib/api";

type Zone = { zone_id: string; name: string };
type Badge = { badge_id: string; name: string; zones: string[]; time_rule: string; expiry: string | null };
type U = { user_id: string; name: string; status: string };

export default function Badges() {
  const router = useRouter();
  const [zones, setZones] = useState<Zone[]>([]);
  const [badges, setBadges] = useState<Badge[]>([]);
  const [users, setUsers] = useState<U[]>([]);
  const [name, setName] = useState("");
  const [selZones, setSelZones] = useState<string[]>([]);
  const [expiry, setExpiry] = useState("");
  const [assignUser, setAssignUser] = useState("");
  const [assignBadge, setAssignBadge] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    try {
      const [z, b, u] = await Promise.all([
        api<{ items: Zone[] }>("/zones"),
        api<{ items: Badge[] }>("/badges"),
        api<{ items: U[] }>("/users?status=active&page_size=100"),
      ]);
      setZones(z.items); setBadges(b.items); setUsers(u.items);
    } catch (e) { if (e instanceof ApiError && e.status === 401) router.push("/admin/login"); }
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault(); setErr(null);
    try {
      await api("/badges", { method: "POST", body: {
        name: name.trim(), zones: selZones,
        time_rule: "always", expiry: expiry || null, print_badge: false,
      }});
      setName(""); setSelZones([]); setExpiry(""); load();
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Failed"); }
  }

  async function assign(e: React.FormEvent) {
    e.preventDefault(); setErr(null); setMsg(null);
    try {
      await api("/badges/assign", { method: "POST", body: { user_id: assignUser, badge_id: assignBadge } });
      setMsg("Badge assigned.");
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Failed"); }
  }

  const zoneName = (id: string) => zones.find((z) => z.zone_id === id)?.name || id.slice(0, 6);

  return (
    <div>
      <h1>Badges</h1>
      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", marginTop: 16 }}>
        <form className="card" onSubmit={create}>
          <h2>Create badge</h2>
          <label>Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Doctor" required />
          <label>Zones it grants</label>
          <select multiple value={selZones} style={{ height: 110 }}
                  onChange={(e) => setSelZones(Array.from(e.target.selectedOptions, (o) => o.value))}>
            {zones.map((z) => <option key={z.zone_id} value={z.zone_id}>{z.name}</option>)}
          </select>
          <label>Expiry (optional)</label>
          <input type="date" value={expiry} onChange={(e) => setExpiry(e.target.value)} />
          <button type="submit" style={{ width: "100%", marginTop: 14 }}>Create</button>
        </form>

        <form className="card" onSubmit={assign}>
          <h2>Assign badge</h2>
          <label>User</label>
          <select value={assignUser} onChange={(e) => setAssignUser(e.target.value)} required>
            <option value="">Select…</option>
            {users.map((u) => <option key={u.user_id} value={u.user_id}>{u.name}</option>)}
          </select>
          <label>Badge</label>
          <select value={assignBadge} onChange={(e) => setAssignBadge(e.target.value)} required>
            <option value="">Select…</option>
            {badges.map((b) => <option key={b.badge_id} value={b.badge_id}>{b.name}</option>)}
          </select>
          {msg && <div className="muted" style={{ marginTop: 10, color: "#166534" }}>{msg}</div>}
          <button type="submit" style={{ width: "100%", marginTop: 14 }}>Assign</button>
        </form>
      </div>
      {err && <div className="error">{err}</div>}

      <div className="card" style={{ marginTop: 16 }}>
        <table>
          <thead><tr><th>Name</th><th>Zones</th><th>Rule</th><th>Expiry</th></tr></thead>
          <tbody>
            {badges.map((b) => (
              <tr key={b.badge_id}>
                <td>{b.name}</td>
                <td>{(b.zones || []).map(zoneName).join(", ") || "—"}</td>
                <td>{b.time_rule}</td>
                <td>{b.expiry || "—"}</td>
              </tr>
            ))}
            {badges.length === 0 && <tr><td colSpan={4} className="muted">No badges yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
