"use client";
// Inside one business (mobile): status + one-tap allow, badges, my check-in history.
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../../lib/api";

type Detail = {
  membership_id: string; business: string; sector: string; role: string; status: string;
  face_verified_here: boolean; badges: string[]; credential_expires_at: string | null;
  has_zones: boolean; history: { event: string; at: string }[];
};

const DAY = 86400000;

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
const dateFmt = (s: string) =>
  new Date(s).toLocaleDateString([], { day: "numeric", month: "long", year: "numeric" });

export default function BusinessDetail({ params }: { params: { membership: string } }) {
  const { membership } = params;
  const router = useRouter();
  const [d, setD] = useState<Detail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // The pass this device kept when face entry was set up. Only some organisations issue one,
  // and it lives per-browser — so treat "not here" as normal, never as an error.
  const [pass, setPass] = useState<string | null>(null);
  const [showPass, setShowPass] = useState(false);

  useEffect(() => {
    try { setPass(localStorage.getItem(`biocore.pass.${membership}`)); } catch { /* private window */ }
  }, [membership]);

  const load = useCallback(async () => {
    try { setD(await api<Detail>(`/person/businesses/${membership}`)); }
    catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/member/login");
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
  // Whole days left on the credential. Negative means it already lapsed — which the person
  // would otherwise find out from a door, in front of a queue.
  const expiresIn = d.credential_expires_at
    ? Math.floor((new Date(d.credential_expires_at).getTime() - Date.now()) / DAY)
    : null;

  return (
    <div>
      <a className="app-back" href="/member">← My places</a>
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
            {expiresIn !== null && (
              <p className={expiresIn < 0 ? "app-err" : expiresIn <= 30 ? "app-warn" : "app-sub"}
                 style={{ margin: "0 0 10px", fontSize: 13.5 }}>
                {expiresIn < 0
                  ? `Ran out on ${dateFmt(d.credential_expires_at!)}. Set it up again to keep walking in.`
                  : expiresIn <= 30
                    ? `Runs out in ${expiresIn === 0 ? "less than a day" : `${expiresIn} day${expiresIn === 1 ? "" : "s"}`} — on ${dateFmt(d.credential_expires_at!)}. Set it up again before then.`
                    : `Valid until ${dateFmt(d.credential_expires_at!)}.`}
              </p>
            )}
            {pass && (
              <>
                <button className="btn" style={{ marginBottom: 8 }}
                        onClick={() => setShowPass(!showPass)}>
                  {showPass ? "Hide my pass" : "Show my pass"}
                </button>
                {showPass && (
                  <div style={{ textAlign: "center", padding: "10px 0 4px" }}>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={`data:image/png;base64,${pass}`} alt="Your entry pass"
                         style={{ width: 210, maxWidth: "100%", imageRendering: "pixelated",
                                  background: "#fff", padding: 10, borderRadius: 8 }} />
                    <p className="app-sub" style={{ fontSize: 12, marginTop: 8 }}>
                      Works without a signal. Showing it is not enough on its own — a gate still
                      has to see your face.
                    </p>
                  </div>
                )}
              </>
            )}
            <button className="btn danger" disabled={busy} onClick={revoke}>Turn off face entry</button>
          </>
        ) : (
          <>
            <p className="app-sub" style={{ margin: "0 0 6px" }}>Set up once, then walk in with just your face — no cards, no queues.</p>
            <a href={`/member/b/${membership}/verify`}><button className="btn primary">Set up face entry</button></a>
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

      {d.has_zones && (
        <a className="tile" href={`/member/b/${membership}/access`}>
          <div className="ic">🗺️</div>
          <div><div className="tt">Where can I go?</div><div className="ts">Which doors open for you, and when</div></div>
          <span className="chev">›</span>
        </a>
      )}

      <a className="tile" href={`/member/b/${membership}/events`}>
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
