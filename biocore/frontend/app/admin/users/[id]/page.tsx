"use client";
// A6 — User profile: view, edit (role/department/status), and erase (DPDP cascade).
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../../lib/api";

type U = { user_id: string; name: string; email: string | null; user_type: string;
           role: string | null; department: string | null; status: string; member_id: string | null };

export default function UserProfile({ params }: { params: { id: string } }) {
  const { id } = params;
  const router = useRouter();
  const [u, setU] = useState<U | null>(null);
  const [form, setForm] = useState({ role: "", department: "", status: "", member_id: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api<U>(`/users/${id}`).then((d) => {
      setU(d);
      setForm({ role: d.role || "", department: d.department || "", status: d.status, member_id: d.member_id || "" });
    }).catch((e) => {
      if (e instanceof ApiError && e.status === 401) router.push("/admin/login");
      else setErr(e instanceof ApiError ? e.message : "Not found");
    });
  }, [id, router]);

  async function save(e: React.FormEvent) {
    e.preventDefault(); setErr(null); setMsg(null);
    try {
      await api(`/users/${id}`, { method: "PATCH", body: {
        role: form.role || null, department: form.department || null,
        status: form.status || null, member_id: form.member_id || null,
      }});
      setMsg("Saved.");
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Failed"); }
  }

  async function erase() {
    if (!window.confirm("Erase this user's biometric data (DPDP cascade)? This cannot be undone.")) return;
    try {
      const r = await api<{ erasure_ref: string }>(`/users/${id}`, { method: "DELETE" });
      setMsg(`Erased. Reference ${r.erasure_ref}.`);
      setTimeout(() => router.push("/admin/users"), 1500);
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Erase failed"); }
  }

  if (err && !u) return <div><p className="muted"><a href="/admin/users">← Users</a></p><div className="error">{err}</div></div>;
  if (!u) return <div><h1>User</h1><p className="muted">Loading…</p></div>;

  return (
    <div>
      <p className="muted"><a href="/admin/users">← Users</a></p>
      <h1>{u.name}</h1>
      <p className="muted">{u.email || "no email"} · {u.user_type} · id {u.user_id.slice(0, 8)}</p>

      <form className="card narrow" style={{ marginTop: 16 }} onSubmit={save}>
        <label>Role</label>
        <input value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} placeholder="e.g. manager" />
        <label>Department</label>
        <input value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} />
        <label>Status</label>
        <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
          <option value="active">active</option>
          <option value="pending_email">pending_email</option>
          <option value="pending_face">pending_face</option>
          <option value="suspended">suspended</option>
        </select>
        <label>Member ID</label>
        <input value={form.member_id} onChange={(e) => setForm({ ...form, member_id: e.target.value })} />
        {msg && <div className="muted" style={{ color: "#166534", marginTop: 8 }}>{msg}</div>}
        {err && <div className="error">{err}</div>}
        <button type="submit" style={{ width: "100%", marginTop: 14 }}>Save</button>
      </form>

      <div className="card narrow" style={{ marginTop: 16, borderColor: "#fecaca" }}>
        <h2 style={{ color: "#dc2626" }}>Danger zone</h2>
        <p className="muted">Erasure deletes the face vector + image, removes biometric records, flushes sessions, and issues a certificate. Attendance logs are retained but de-linked.</p>
        <button style={{ background: "#dc2626" }} onClick={erase}>Erase biometric data (DPDP)</button>
      </div>
    </div>
  );
}
