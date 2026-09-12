"use client";
// A20 — Roles & permissions: presets (read-only) + create/delete custom roles.
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../lib/api";

type Role = { role_id: string; key: string; name: string; is_preset: boolean; permissions: string[] };

export default function Roles() {
  const router = useRouter();
  const [roles, setRoles] = useState<Role[]>([]);
  const [catalog, setCatalog] = useState<Record<string, string[]>>({});
  const [name, setName] = useState("");
  const [perms, setPerms] = useState<Set<string>>(new Set());
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [r, p] = await Promise.all([
        api<{ items: Role[] }>("/roles"),
        api<Record<string, string[]>>("/permissions"),
      ]);
      setRoles(r.items); setCatalog(p);
    } catch (e) { if (e instanceof ApiError && e.status === 401) router.push("/admin/login"); }
  }, [router]);
  useEffect(() => { load(); }, [load]);

  function toggle(p: string) {
    const next = new Set(perms);
    next.has(p) ? next.delete(p) : next.add(p);
    setPerms(next);
  }

  async function create(e: React.FormEvent) {
    e.preventDefault(); setErr(null);
    try {
      await api("/roles", { method: "POST", body: { name: name.trim(), permissions: [...perms], scope: {} } });
      setName(""); setPerms(new Set()); load();
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Failed"); }
  }

  async function del(id: string) {
    if (!window.confirm("Delete this custom role?")) return;
    try { await api(`/roles/${id}`, { method: "DELETE" }); load(); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Failed (role may be in use)"); }
  }

  return (
    <div>
      <h1>Roles &amp; permissions</h1>
      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", marginTop: 16 }}>
        <form className="card" onSubmit={create}>
          <h2>Create custom role</h2>
          <label>Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Night Shift Supervisor" required />
          <label>Permissions</label>
          <div style={{ maxHeight: 280, overflow: "auto", border: "1px solid #e2e8f0", borderRadius: 8, padding: 10 }}>
            {Object.entries(catalog).map(([group, ps]) => (
              <div key={group} style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: "#64748b" }}>{group}</div>
                {ps.map((p) => (
                  <label key={p} className="checkbox" style={{ margin: "2px 0" }}>
                    <input type="checkbox" checked={perms.has(p)} onChange={() => toggle(p)} />
                    <span style={{ fontSize: 13 }}>{p}</span>
                  </label>
                ))}
              </div>
            ))}
          </div>
          {err && <div className="error">{err}</div>}
          <button type="submit" style={{ width: "100%", marginTop: 12 }} disabled={!name || perms.size === 0}>Create role</button>
        </form>

        <div className="card">
          <h2>All roles</h2>
          <table>
            <thead><tr><th>Name</th><th>Key</th><th>Type</th><th></th></tr></thead>
            <tbody>
              {roles.map((r) => (
                <tr key={r.role_id}>
                  <td>{r.name}</td>
                  <td><code>{r.key}</code></td>
                  <td><span className={`badge ${r.is_preset ? "gray" : "green"}`}>{r.is_preset ? "preset" : "custom"}</span></td>
                  <td>{!r.is_preset && <button className="ghost" style={{ color: "#dc2626" }} onClick={() => del(r.role_id)}>Delete</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
