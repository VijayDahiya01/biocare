"use client";
// K1 — Kiosk self-service terminal. Two modes:
//  • Check-in: always-on face scanner (/faces/search), auto-reset.
//  • Verified entry (§11.3): enter a pass/id → live capture → 1:1 match + authorization
//    decision (/entry). Device-authenticated; frames are never stored, auto-resets.
// Shares the light "terminal" look with the guard console (guard.css).
import "../guard/guard.css";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useCamera } from "../../lib/camera";
import { ApiError, deviceSearch } from "../../lib/api";

type Result = { kind: "in" | "out" | "bad" | "unknown"; icon: string; label: string; big: string; name?: string; meta?: string };
type Mode = "checkin" | "entry";
const RESET_MS = 3500, SCAN_MS = 1500;

const fmtDur = (m: number | null | undefined) => {
  if (m == null) return "";
  const h = Math.floor(m / 60), mm = m % 60;
  return h ? `${h}h ${mm}m` : `${mm}m`;
};
// privacy-safe messages (§11.3) — never reveal internal thresholds/rules.
const REASON_MSG: Record<string, string> = {
  ALLOWED: "Access granted",
  FACE_MISMATCH: "Face did not match — please see reception",
  LIVENESS_FAILED: "Please present a real face",
  CREDENTIAL_EXPIRED: "No active credential — please see reception",
  CONSENT_WITHDRAWN: "Please use the alternative entry",
  ACCESS_NOT_ALLOWED: "Not authorised for this gate / time",
  NO_FACE: "No face detected",
  MULTIPLE_FACES: "One person at a time",
  AMBIGUOUS_MATCH: "Could not confirm — please see reception",
  MATCH_ENGINE_UNAVAILABLE: "Service unavailable — please see reception",
};

function Kiosk() {
  const params = useSearchParams();
  const { videoRef, ready, error, start, capture } = useCamera();
  const [token, setToken] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>("checkin");
  const [result, setResult] = useState<Result | null>(null);
  const [status, setStatus] = useState("Look at the camera");
  const [count, setCount] = useState(0);
  const [now, setNow] = useState<Date>(() => new Date());
  const [entryStep, setEntryStep] = useState<"claim" | "capture">("claim");
  const [claim, setClaim] = useState("");
  const [subject, setSubject] = useState<{ subject_id: string } | null>(null);
  const [entryBusy, setEntryBusy] = useState(false);
  const [entryErr, setEntryErr] = useState<string | null>(null);
  const busy = useRef(false);

  useEffect(() => {
    const t = params.get("token") || (typeof window !== "undefined" && sessionStorage.getItem("biocore_device_token")) || null;
    if (t) { sessionStorage.setItem("biocore_device_token", t); setToken(t); }
    start();
  }, [params, start]);

  useEffect(() => { const id = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(id); }, []);

  function resetEntry() { setEntryStep("claim"); setClaim(""); setSubject(null); setEntryErr(null); }

  const scan = useCallback(async () => {
    if (!token || !ready || busy.current || result || mode !== "checkin") return;
    const image = capture();
    if (!image) return;
    busy.current = true; setStatus("Scanning…");
    const t = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    try {
      const d = await deviceSearch("/faces/search", token, { image, action: "auto" });
      if (d.blacklist_hit) setResult({ kind: "bad", icon: "⚠", label: "Blacklist hit", big: "Do not admit", meta: "Alert sent to security" });
      else if (!d.match) setResult({ kind: "unknown", icon: "?", label: "No match", big: "Not recognised", meta: "Please see reception" });
      else if (d.event === "check_in") setResult({ kind: "in", icon: "✓", label: "Checked in", big: "Welcome", name: d.name, meta: `${t} · ${(d.score * 100).toFixed(0)}% match` });
      else setResult({ kind: "out", icon: "✓", label: "Checked out", big: "Goodbye", name: d.name, meta: `${t}${d.duration_minutes != null ? " · " + fmtDur(d.duration_minutes) : ""}` });
      setCount((c) => c + 1);
    } catch (e) {
      const code = e instanceof ApiError ? e.code : "";
      if (code === "SPOOF_DETECTED") setResult({ kind: "bad", icon: "✕", label: "Liveness failed", big: "Use a real face" });
      else if (code === "IMAGE_QUALITY_FAILED") setStatus("Hold still — move a little closer");
      else setStatus("Try again");
    } finally { busy.current = false; }
  }, [token, ready, result, capture, mode]);

  useEffect(() => { const id = setInterval(scan, SCAN_MS); return () => clearInterval(id); }, [scan]);

  useEffect(() => {
    if (!result) return;
    const id = setTimeout(() => { setResult(null); setStatus("Look at the camera"); if (mode === "entry") resetEntry(); }, RESET_MS);
    return () => clearTimeout(id);
  }, [result, mode]);

  async function resolveClaim() {
    if (!token) return;
    setEntryErr(null); setEntryBusy(true);
    try {
      const d = await deviceSearch("/entry/resolve-claim", token, { claim: claim.trim() });
      if (!d.resolved) setEntryErr("Pass / ID not recognised.");
      else if (!d.has_credential) setEntryErr("No entry credential on file — please see reception.");
      else { setSubject({ subject_id: d.subject_id }); setEntryStep("capture"); }
    } catch (e) { setEntryErr(e instanceof ApiError ? e.message : "Failed"); }
    finally { setEntryBusy(false); }
  }

  async function verifyEntry() {
    if (!token || !subject) return;
    setEntryErr(null); setEntryBusy(true);
    const image = capture();
    if (!image) { setEntryErr("Camera not ready"); setEntryBusy(false); return; }
    try {
      const d = await deviceSearch("/entry/match", token, { subject_id: subject.subject_id, image });
      if (d.decision === "allow") setResult({ kind: "in", icon: "✓", label: "Access granted", big: "Entry allowed", meta: REASON_MSG[d.reason] || "" });
      else setResult({ kind: "bad", icon: "✕", label: "Access denied", big: "Entry denied", meta: REASON_MSG[d.reason] || d.reason });
    } catch (e) { setEntryErr(e instanceof ApiError ? e.message : "Failed"); }
    finally { setEntryBusy(false); }
  }

  const switchMode = (m: Mode) => { setMode(m); setResult(null); setStatus("Look at the camera"); resetEntry(); };

  return (
    <div className="gd">
      <div className="gd-top">
        <div className="gd-brand">
          <span className="mark">B</span>
          <div><div className="bt">BioCore</div><div className="bs">Self-service terminal</div></div>
        </div>
        <div className="gd-rightbar">
          <div style={{ display: "flex", gap: 4, background: "var(--violet-tint)", borderRadius: 999, padding: 3 }}>
            {(["checkin", "entry"] as const).map((m) => (
              <button key={m} onClick={() => switchMode(m)}
                style={{ border: 0, borderRadius: 999, padding: "6px 14px", fontSize: 13, fontWeight: 600, cursor: "pointer",
                         background: mode === m ? "#fff" : "transparent", color: mode === m ? "var(--violet)" : "var(--muted)" }}>
                {m === "checkin" ? "Check-in" : "Verified entry"}
              </button>
            ))}
          </div>
          <div className="gd-clock">
            <div className="t">{now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</div>
            <div className="d">{now.toLocaleDateString([], { weekday: "long", day: "numeric", month: "long" })}</div>
          </div>
        </div>
      </div>

      <div className="gd-main">
        <div className="gd-stage">
          <div className="gd-stagebody">
            <video ref={videoRef} muted playsInline className="gd-video preview" />

            {result ? (
              <div className={`gd-hero ${result.kind}`}>
                <div className="gd-rring"><span className="gd-ricon">{result.icon}</span></div>
                <div className="gd-rlabel">{result.label}</div>
                <div className="gd-rbig">{result.big}</div>
                {result.name && <div className="gd-rname">{result.name}</div>}
                {result.meta && <div className="gd-rmeta">{result.meta}</div>}
              </div>
            ) : mode === "checkin" ? (
              <div className="gd-hero idle">
                <div className="gd-rring" />
                <div className="gd-rbig">Look at the camera</div>
                <div className="gd-rmeta">{status === "Look at the camera" ? "Checking in is automatic — just look ahead" : status}</div>
              </div>
            ) : entryStep === "claim" ? (
              <div className="gd-hero idle">
                <div className="gd-rbig">Verified entry</div>
                <div className="gd-rmeta" style={{ marginBottom: 12 }}>Enter your pass or ID to begin.</div>
                <div style={{ display: "flex", gap: 6, maxWidth: 320, margin: "0 auto" }}>
                  <input className="gd-field" style={{ margin: 0 }} value={claim} onChange={(e) => setClaim(e.target.value)} placeholder="EMP-001"
                         onKeyDown={(e) => { if (e.key === "Enter") resolveClaim(); }} />
                  <button className="gd-btn primary" disabled={!claim.trim() || entryBusy} onClick={resolveClaim}>Continue</button>
                </div>
                {entryErr && <div className="gd-err" style={{ marginTop: 10, maxWidth: 320, marginInline: "auto" }}>{entryErr}</div>}
              </div>
            ) : (
              <div className="gd-hero idle">
                <div className="gd-rbig">Look at the camera</div>
                <div className="gd-rmeta" style={{ marginBottom: 12 }}>Position your face in front of the camera, then verify.</div>
                <button className="gd-btn-wide" style={{ maxWidth: 260, marginInline: "auto" }} disabled={entryBusy} onClick={verifyEntry}>Verify entry</button>
                {entryErr && <div className="gd-err" style={{ marginTop: 10, maxWidth: 320, marginInline: "auto" }}>{entryErr}</div>}
              </div>
            )}

            {!token && <div className="gd-err" style={{ maxWidth: 380 }}>No device token. Open this page from the kiosk URL (…/kiosk?token=…).</div>}
            {error && <div className="gd-err" style={{ maxWidth: 380 }}>{error}</div>}
          </div>

          <div className="gd-stats">
            <div className="gd-stat"><span className="ic v">✓</span><div><div className="n">{count}</div><div className="l">Checks today</div></div></div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function KioskPage() {
  return (
    <Suspense fallback={<div className="gd"><div className="gd-center">Loading…</div></div>}>
      <Kiosk />
    </Suspense>
  );
}
