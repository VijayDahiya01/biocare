"use client";
// A5 — Users list, and inviting someone to join.
//
// The invite API existed from the start but nothing in the UI called it, so there was no way to
// add a person without handing them the organisation code by hand.
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../lib/api";

type U = { user_id: string; name: string; email: string | null; user_type: string;
           department: string | null; status: string; member_id: string | null };

type Invite = { invite_id: string; email: string; role: string; status: string };

const statusBadge = (s: string) =>
  s === "active" ? "green" : s === "suspended" ? "red" : "amber";

const ROLES = [
  ["member", "Member — normal staff"],
  ["manager", "Manager — can see reports"],
] as const;

export default function Users() {
  const router = useRouter();
  const [items, setItems] = useState<U[]>([]);
  const [status, setStatus] = useState("");

  const [invites, setInvites] = useState<Invite[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<string>("member");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const on401 = useCallback((e: unknown) => {
    if (e instanceof ApiError && e.status === 401) router.push("/admin/login");
  }, [router]);

  useEffect(() => {
    const q = new URLSearchParams({ page_size: "100" });
    if (status) q.set("status", status);
    api<{ items: U[] }>(`/users?${q}`).then((d) => setItems(d.items)).catch(on401);
  }, [status, on401]);

  const loadInvites = useCallback(() => {
    api<{ items: Invite[] }>("/businesses/invites")
      .then((d) => setInvites(d.items))
      .catch(on401);
  }, [on401]);

  useEffect(() => { loadInvites(); }, [loadInvites]);

  async function invite(e: React.FormEvent) {
    e.preventDefault();
    setErr(null); setSent(null); setSending(true);
    try {
      await api("/businesses/invites", { method: "POST", body: { email: email.trim(), role } });
      setSent(email.trim());
      setEmail("");
      loadInvites();
    } catch (e2) {
      on401(e2);
      setErr(e2 instanceof ApiError ? e2.message : "Could not send the invitation.");
    } finally { setSending(false); }
  }

  const pending = invites.filter((i) => i.status === "pending");

  return (
    <div>
      <h1>People</h1>

      <div className="card" style={{ marginTop: 16 }}>
        <h2 style={{ marginTop: 0 }}>Invite someone</h2>
        <p className="muted" style={{ marginTop: 4 }}>
          They will see the invitation when they sign in to the BioCore app with this email
          address. Nothing happens to them until they accept it.
        </p>
        <form onSubmit={invite}
              style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap", marginTop: 12 }}>
          <div style={{ flex: "1 1 240px" }}>
            <label htmlFor="invite-email">Their email address</label>
            <input id="invite-email" type="email" required value={email} placeholder="name@example.com"
                   onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div style={{ flex: "0 1 220px" }}>
            <label htmlFor="invite-role">Role</label>
            <select id="invite-role" value={role} onChange={(e) => setRole(e.target.value)}>
              {ROLES.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
            </select>
          </div>
          <button type="submit" disabled={sending || !email.trim()}>
            {sending ? "Sending…" : "Send invitation"}
          </button>
        </form>
        {sent && <div className="ok" style={{ marginTop: 10 }}>Invitation sent to {sent}.</div>}
        {err && <div className="error" style={{ marginTop: 10 }}>{err}</div>}
      </div>

      {pending.length > 0 && (
        <div className="card">
          <h2 style={{ marginTop: 0 }}>Waiting to be accepted ({pending.length})</h2>
          <table>
            <thead><tr><th>Email</th><th>Role</th></tr></thead>
            <tbody>
              {pending.map((i) => (
                <tr key={i.invite_id}><td>{i.email}</td><td>{i.role}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Everyone here ({items.length})</h2>
        <div style={{ margin: "12px 0", maxWidth: 220 }}>
          <label htmlFor="user-status">Show</label>
          <select id="user-status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Everyone</option>
            <option value="active">Active</option>
            <option value="pending_email">Waiting to confirm email</option>
            <option value="pending_face">Face not set up yet</option>
            <option value="suspended">Suspended</option>
          </select>
        </div>
        {items.length === 0
          ? <p className="muted">Nobody has joined yet. Send an invitation above to get started.</p>
          : (
            <table>
              <thead><tr><th>Name</th><th>Email</th><th>Type</th><th>Department</th><th>Status</th></tr></thead>
              <tbody>
                {items.map((u) => (
                  <tr key={u.user_id}>
                    <td><a href={`/admin/users/${u.user_id}`}>{u.name}</a></td>
                    <td>{u.email ?? "—"}</td>
                    <td>{u.user_type}</td>
                    <td>{u.department ?? "—"}</td>
                    <td><span className={`badge ${statusBadge(u.status)}`}>{u.status.replace(/_/g, " ")}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </div>
    </div>
  );
}
