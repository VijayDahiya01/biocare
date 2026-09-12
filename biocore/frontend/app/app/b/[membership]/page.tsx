"use client";
// Inside one business (mobile): status + one-tap allow, badges, my check-in history.
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../../lib/api";

type Detail = {
  membership_id: string; business: string; sector: string; role: string; status: string;
  face_verified_here: boolean; badges: string[]; history: { event: string; at: string }[];
};

const STATUS: Record<string, { label: string; cls: string }> = {
  active: { label: "Active", cls: "green" }, suspended: { label: "Suspended", cls: "red" },
  pending_face: { label: "Getting started", cls: "amber" }, pending_email: { label: "Confirm email", cls: "amber" },
};
const stat = (s: string) => STATUS[s] || { label: s.replace(/_/g, " "), cls: "amber" };
const EVENT: Record<string, { label: string; cls: string }> = {
  check_in: { label: "Checked in", cls: "green" }, check_out: { label: "Checked out", cls: "amber" },
  break_start: { label: "Break started", cls: "amber" }, break_end: { label: "Break ended", cls: "green" },
};
const ev = (e: string) => EVENT[e] || { label: e.replace(/_/g, " "), cls: "gray" };
const humanize = (s: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, " ") : s);

export default function BusinessDetail({ params }: { params: { membership: string } }) {
  const { membership } = params;
  const router = useRouter();
  const [d, setD] = useState<Detail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { setD(await api<Detail>(`/person/businesses/${membership}`)); }
    catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/app/login");
      else setErr(e instanceof ApiError ? e.message : "Could not load");
    }
  }, [membership, router]);
  useEffect(() => { load(); }, [load]);

  async function revoke() {
    if (!confirm("Withdraw face use for this business?")) return;
    setBusy(true);
    try { await api(`/person/businesses/${membership}/consent/revoke`, { method: "POST" }); await load(); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Failed"); }
    finally { setBusy(false); }
  }

  if (!d) return <p className="app-sub" style={{ padding: 8 }}>{err || "Loading…"}</p>;

  const timeFmt = (s: string) => new Date(s).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

  return (
    <div>
      <a className="app-back" href="/app">← My places</a>
      <h1 className="app-h1">{d.business}</h1>
      <p className="app-sub">{humanize(d.sector)} · {humanize(d.role)}</p>

      <div className="app-card" style={{ marginTop: 14 }}>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 }}>
          <span className={`pill ${stat(d.status).cls}`}>{stat(d.status).label}</span>
          {d.face_verified_here ? <span className="pill green">✓ Face entry ready</span> : <span className="pill amber">Face entry not set up</span>}
        </div>
        {d.face_verified_here ? (
          <>
            <p className="app-sub" style={{ margin: "0 0 6px" }}>You can enter with just your face at this business.</p>
            <button className="btn danger" disabled={busy} onClick={revoke}>Turn off face entry</button>
          </>
        ) : (
          <>
            <p className="app-sub" style={{ margin: "0 0 6px" }}>Set up once, then walk in with just your face — no cards, no queues.</p>
            <a href={`/app/b/${membership}/verify`}><button className="btn primary">Set up face entry</button></a>
          </>
        )}
        {err && <div className="app-err">{err}</div>}
      </div>

      <div className="app-card">
        <div className="app-label" style={{ marginTop: 0 }}>Badges</div>
        <div style={{ marginTop: 6, display: "flex", gap: 6, flexWrap: "wrap" }}>
          {d.badges.length ? d.badges.map((b) => <span key={b} className="pill gray">{b}</span>) : <span className="app-sub">none</span>}
        </div>
      </div>

      <a className="tile" href={`/app/b/${membership}/events`}>
        <div className="ic">🎫</div>
        <div><div className="tt">Events</div><div className="ts">Register & manage consent</div></div>
        <span className="chev">›</span>
      </a>

      <div className="app-card">
        <div className="app-label" style={{ marginTop: 0 }}>My check-in history</div>
        {d.history.length === 0 && <p className="app-sub" style={{ marginTop: 8 }}>No check-ins yet.</p>}
        {d.history.map((h, i) => (
          <div key={i} className="list-row">
            <span className={`pill ${ev(h.event).cls}`}>{ev(h.event).label}</span>
            <span className="app-sub">{timeFmt(h.at)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
