"use client";
// Guard terminal — the guard-friendly flow: sign in → pick your gate → face check-in/out.
// The device token (terminal trust) is set up ONCE by an admin; the guard never sees it.
// One camera, walk-up 1:N recognition, with a manual (type-ID) fallback.
import "./guard.css";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useCamera } from "../../lib/camera";
import { useFaceDetect } from "../../lib/faceDetect";
import { ApiError, api, deviceGet, deviceSearch } from "../../lib/api";

type Guard = { email?: string; role?: string } | null;
type Gate = { id: string; name: string };
type Res = { kind: "in" | "out" | "bad" | "unknown"; big: string; name?: string; sub?: string };

const REASON: Record<string, string> = {
  ALLOWED: "Access granted",
  FACE_MISMATCH: "Not recognised — see reception",
  LIVENESS_FAILED: "Please look at the camera",
  CREDENTIAL_EXPIRED: "Face pass expired — see reception",
  CONSENT_WITHDRAWN: "See reception",
  ACCESS_NOT_ALLOWED: "Not allowed at this gate / time",
  NO_FACE: "No face detected",
  DEVICE_NOT_TRUSTED: "Terminal not trusted",
  FACE_ENGINE_UNAVAILABLE: "Face service unavailable — use manual",
  MATCH_ENGINE_UNAVAILABLE: "Face service unavailable — use manual",
};

export default function GuardPage() {
  return <Suspense fallback={null}><Terminal /></Suspense>;
}

function Terminal() {
  const params = useSearchParams();
  const { videoRef, ready, start, capture } = useCamera();
  const { faceOnRef } = useFaceDetect(videoRef);
  const [token, setToken] = useState<string | null>(null);
  const [guard, setGuard] = useState<Guard>(null);
  const [gates, setGates] = useState<Gate[]>([]);
  const [gate, setGate] = useState<Gate | null>(null);
  const [mode, setMode] = useState<"in" | "out">("in");
  const [res, setRes] = useState<Res | null>(null);
  const [manual, setManual] = useState(false);
  const [now, setNow] = useState(() => new Date());
  const busy = useRef(false);

  useEffect(() => {
    const t = params.get("token") || (typeof window !== "undefined" && localStorage.getItem("guard_device")) || null;
    if (t) { localStorage.setItem("guard_device", t); setToken(t); start(); }
    api<{ role?: string; email?: string }>("/auth/me")
      .then((d) => { if (d.role && d.role !== "self_user") setGuard({ email: d.email, role: d.role }); })
      .catch(() => {});
  }, [params, start]);

  useEffect(() => { const id = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(id); }, []);

  useEffect(() => {
    if (gate || !token || !guard) return;
    deviceGet("/entry/gates", token).then((d: { items: Gate[] }) => {
      setGates(d.items || []);
      const saved = typeof window !== "undefined" ? localStorage.getItem("guard_gate") : null;
      if (saved) { const g = (d.items || []).find((x) => x.id === saved); if (g) setGate(g); }
    }).catch(() => {});
  }, [token, guard, gate]);

  const scan = useCallback(async () => {
    if (!token || !gate || !ready || busy.current || res || manual) return;
    if (!faceOnRef.current) return;                 // only when a face fills the circle
    const image = capture(); if (!image) return;
    busy.current = true;
    try {
      const d = await deviceSearch("/entry/identify", token, { image, gate_id: gate.id, direction: mode });
      if (d.matched && d.decision === "allow")
        setRes({ kind: mode, big: mode === "in" ? "Welcome" : "Goodbye", name: d.name, sub: mode === "in" ? "Checked in" : "Checked out" });
      else if (d.matched)
        setRes({ kind: "bad", big: "Entry denied", name: d.name, sub: REASON[d.reason] || d.reason });
      else
        setRes({ kind: "unknown", big: "Not recognised", sub: REASON[d.reason] || "Please see reception" });
    } catch (e) {
      setRes({ kind: "bad", big: "Try again", sub: e instanceof ApiError ? (REASON[e.code] || e.message) : "Error" });
    } finally {
      busy.current = false;
      setTimeout(() => setRes(null), 3500);
    }
  }, [token, gate, ready, res, manual, faceOnRef, capture, mode]);

  useEffect(() => { const id = setInterval(scan, 700); return () => clearInterval(id); }, [scan]);

  if (!token) return <SetupScreen onToken={(t) => { localStorage.setItem("guard_device", t); setToken(t); start(); }} />;
  if (!guard) return <LoginScreen onIn={setGuard} />;
  if (!gate) return <GatePicker gates={gates} guard={guard} onPick={(g) => { localStorage.setItem("guard_gate", g.id); setGate(g); }} onSignOut={signOut} />;

  const kind = res ? res.kind : "idle";
  return (
    <div className="gd">
      <div className="gd-top">
        <div className="gd-brand"><span className="mark">B</span>
          <div><div className="bt">{gate.name}</div><div className="bs">{guard.email || "Guard"} · {now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</div></div>
        </div>
        <div className="gd-rightbar">
          <div className="gd-modeswitch">
            <button className={mode === "in" ? "on" : ""} onClick={() => setMode("in")}>Check-in</button>
            <button className={mode === "out" ? "on" : ""} onClick={() => setMode("out")}>Check-out</button>
          </div>
          <button className="gd-btn" onClick={() => { localStorage.removeItem("guard_gate"); setGate(null); }}>Change gate</button>
          <button className="gd-btn" onClick={signOut}>Sign out</button>
        </div>
      </div>

      <div className="gd-main">
        <div className="gd-stage" style={{ width: "100%" }}>
          <div className="gd-stagebody">
            <div className={`gd-hero ${kind}`}>
              <div className="gd-rring cam"><video ref={videoRef} muted playsInline className="gd-rvideo" />
                {res && <span className="gd-ricon">{res.kind === "in" ? "✓" : res.kind === "out" ? "→" : res.kind === "unknown" ? "?" : "✕"}</span>}
              </div>
              {res ? (
                <><div className="gd-rlabel">{mode === "in" ? "Check-in" : "Check-out"}</div>
                  <div className="gd-rbig">{res.big}</div>
                  {res.name && <div className="gd-rname">{res.name}</div>}
                  {res.sub && <div className="gd-rmeta">{res.sub}</div>}</>
              ) : (
                <><div className="gd-rbig">Look at the camera</div>
                  <div className="gd-rmeta">{mode === "in" ? "Step up to check in" : "Step up to check out"}</div></>
              )}
            </div>
            <div style={{ display: "flex", gap: 10, marginTop: 16, justifyContent: "center" }}>
              <button className="gd-btn primary" onClick={() => setManual(true)}>Manual check-in</button>
            </div>
          </div>
        </div>
      </div>

      {manual && <ManualPanel token={token} mode={mode} onClose={() => setManual(false)} />}
    </div>
  );
}

async function signOut() {
  try { await api("/auth/logout", { method: "POST" }); } catch {}
  if (typeof window !== "undefined") location.reload();
}

// --- terminal setup (admin, once) ---
function SetupScreen({ onToken }: { onToken: (t: string) => void }) {
  const [v, setV] = useState("");
  return (
    <div className="gd"><div className="gd-center"><div className="gd-modal">
      <h2 style={{ marginTop: 0 }}>Terminal not set up</h2>
      <p style={{ color: "var(--muted)", fontSize: 14 }}>Ask your administrator to set up this terminal. (Admin: paste the terminal token from <b>Admin → Devices</b>.)</p>
      <input className="gd-field" value={v} onChange={(e) => setV(e.target.value)} placeholder="dev_…" />
      <button className="gd-btn-wide" onClick={() => v.trim() && onToken(v.trim())}>Set up terminal</button>
    </div></div></div>
  );
}

// --- guard sign in ---
function LoginScreen({ onIn }: { onIn: (g: Guard) => void }) {
  const [f, setF] = useState({ email: "", password: "", totp_code: "" });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr(null); setBusy(true);
    try {
      await api("/auth/login", { method: "POST", body: { email: f.email.trim(), password: f.password, totp_code: f.totp_code.trim() || null } });
      const me = await api<{ role?: string; email?: string }>("/auth/me");
      onIn({ email: me.email || f.email, role: me.role || "" });
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Sign-in failed"); } finally { setBusy(false); }
  }
  return (
    <div className="gd"><div className="gd-center"><form className="gd-modal" onSubmit={submit}>
      <h2 style={{ marginTop: 0 }}>Guard sign in</h2>
      <input className="gd-field" placeholder="Email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />
      <input className="gd-field" type="password" placeholder="Password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} />
      <input className="gd-field" placeholder="2FA code (if asked)" value={f.totp_code} onChange={(e) => setF({ ...f, totp_code: e.target.value })} />
      {err && <div className="gd-err">{err}</div>}
      <button className="gd-btn-wide" type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
    </form></div></div>
  );
}

// --- pick your gate ---
function GatePicker({ gates, guard, onPick, onSignOut }: { gates: Gate[]; guard: Guard; onPick: (g: Gate) => void; onSignOut: () => void }) {
  return (
    <div className="gd"><div className="gd-center"><div className="gd-modal" style={{ maxWidth: 460 }}>
      <h2 style={{ marginTop: 0 }}>Which gate are you at?</h2>
      <p style={{ color: "var(--muted)", fontSize: 14 }}>Signed in as {guard?.email || "guard"}. Pick where you&apos;re standing.</p>
      <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
        {gates.length === 0 && <p style={{ color: "var(--muted)" }}>No gates set up. Ask an admin to add zones/gates.</p>}
        {gates.map((g) => (
          <button key={g.id} className="gd-btn-wide" onClick={() => onPick(g)}>🚪 {g.name}</button>
        ))}
      </div>
      <button className="gd-btn" style={{ marginTop: 14 }} onClick={onSignOut}>Sign out</button>
    </div></div></div>
  );
}

// --- manual fallback: admit by ID after the guard checks a physical ID (NO face needed) ---
function ManualPanel({ token, mode, onClose }: { token: string; mode: "in" | "out"; onClose: () => void }) {
  const [claim, setClaim] = useState("");
  const [subject, setSubject] = useState<{ subject_id: string; name?: string; verification_status: string } | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  async function find() {
    setMsg(null); setSubject(null); setBusy(true);
    try {
      const d = await deviceSearch("/entry/resolve-claim", token, { claim: claim.trim() });
      if (!d.resolved) setMsg({ ok: false, text: "No one found for that ID." });
      else setSubject({ subject_id: d.subject_id, name: d.name, verification_status: d.verification_status });
    } catch (e) { setMsg({ ok: false, text: e instanceof ApiError ? e.message : "Failed" }); } finally { setBusy(false); }
  }
  async function admit() {
    if (!subject) return; setBusy(true);
    try {
      await deviceSearch("/entry/commit", token, { subject_id: subject.subject_id, decision: "allow",
        reason: mode === "in" ? "MANUAL_CHECK_IN" : "MANUAL_CHECK_OUT" });
      setMsg({ ok: true, text: `✓ ${mode === "in" ? "Checked in" : "Checked out"} — ${subject.name || claim}` });
      setSubject(null); setClaim("");
    } catch (e) { setMsg({ ok: false, text: e instanceof ApiError ? e.message : "Failed" }); } finally { setBusy(false); }
  }
  return (
    <div className="gd-center" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.4)", zIndex: 50 }}>
      <div className="gd-modal">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ margin: 0 }}>Manual {mode === "in" ? "check-in" : "check-out"}</h2>
          <button className="gd-btn" onClick={onClose}>Close</button>
        </div>
        <p style={{ color: "var(--muted)", fontSize: 13 }}>Use when a face won&apos;t read. Check the person&apos;s ID card, then admit them.</p>
        <div style={{ display: "flex", gap: 6 }}>
          <input className="gd-field" style={{ margin: 0 }} value={claim} onChange={(e) => setClaim(e.target.value)} placeholder="EMP-001" />
          <button className="gd-btn primary" disabled={!claim.trim() || busy} onClick={find}>Find</button>
        </div>
        {subject && (
          <div className="gd-card" style={{ marginTop: 10 }}>
            <div style={{ fontWeight: 700, fontSize: 16 }}>{subject.name || claim}</div>
            <div style={{ margin: "6px 0 4px" }}>
              <span className={`gd-pill ${subject.verification_status === "verified" ? "gray" : "amber"}`}>
                {subject.verification_status === "verified" ? "identity verified ✓" : subject.verification_status}
              </span>
            </div>
            <button className="gd-btn-wide" style={{ marginTop: 6 }} disabled={busy} onClick={admit}>
              Admit — {mode === "in" ? "check in" : "check out"}
            </button>
          </div>
        )}
        {msg && <div className={msg.ok ? "gd-ok" : "gd-err"} style={{ marginTop: 10 }}>{msg.text}</div>}
      </div>
    </div>
  );
}
