"use client";
// Verified-identity console (BIOCORE_COMPLETE_CHANGE_SPEC §11) — the enrollment operator
// runs: consent-before-collection → government fetch → live capture + 1:1 verify → mint an
// encrypted entry credential, then manages it. Maps to /identity + /face-credentials.
// The government photo and raw response are never stored; only minimal claims are kept.
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../lib/api";
import CameraCapture from "../../../components/CameraCapture";

const PURPOSES: [string, string, string][] = [
  ["identity_verification", "Check ID", "Confirm identity via an official source."],
  ["government_data_processing", "Use ID record", "Use the official record only to verify — never stored."],
  ["live_face_capture", "Capture face", "Take a live photo of the person's face."],
  ["face_to_government_match", "Match face", "Check the live face matches the official photo."],
  ["entry_template_creation", "Set up entry", "Create a secure, encrypted face pass."],
  ["entry_authentication", "Allow entry", "Use the face to enter at approved gates."],
];

type Session = { session_id: string; tenant_subject_id: string; status: string };
type Cred = { credential_id: string; status: string; purpose: string; expires_at: string | null };
type Step = "start" | "consent" | "gov" | "verify" | "credential" | "done";

export default function IdentityConsole() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("start");
  const [f, setF] = useState({ external_reference: "", display_name: "", subject_type: "member" });
  const [session, setSession] = useState<Session | null>(null);
  const [acks, setAcks] = useState<Record<string, boolean>>({});
  const [reference, setReference] = useState("");
  const [gov, setGov] = useState<{ assurance_level: string } | null>(null);
  const [verified, setVerified] = useState<{ status: string; outcome: string } | null>(null);
  const [cred, setCred] = useState<Cred | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const allAcked = PURPOSES.every(([k]) => acks[k]);

  function fail(e: unknown) {
    if (e instanceof ApiError && e.status === 401) { router.push("/admin/login"); return; }
    setErr(e instanceof ApiError ? e.message : "Something went wrong");
  }

  async function startSession(e: React.FormEvent) {
    e.preventDefault(); setErr(null); setBusy(true);
    try {
      const s = await api<Session>("/identity/sessions", {
        method: "POST",
        body: { ...f, external_reference: f.external_reference.trim() || null },
      });
      setSession(s); setReference(f.external_reference.trim()); setStep("consent");
    } catch (e) { fail(e); } finally { setBusy(false); }
  }

  async function recordConsent() {
    if (!session) return; setErr(null); setBusy(true);
    try {
      await api(`/identity/sessions/${session.session_id}/consent`, {
        method: "POST", body: { purposes: PURPOSES.map(([k]) => k), method: "in_person" },
      });
      setStep("gov");
    } catch (e) { fail(e); } finally { setBusy(false); }
  }

  async function govFetch() {
    if (!session) return; setErr(null); setBusy(true);
    try {
      const r = await api<{ assurance_level: string }>(`/identity/sessions/${session.session_id}/government-fetch`, {
        method: "POST", body: { credential: { reference: reference.trim() } },
      });
      setGov(r); setStep("verify");
    } catch (e) { fail(e); } finally { setBusy(false); }
  }

  async function verify(image: string) {
    if (!session) return; setErr(null); setBusy(true);
    try {
      const r = await api<{ status: string; outcome: string }>(`/identity/sessions/${session.session_id}/verify`, {
        method: "POST", body: { live_image: image },
      });
      setVerified(r);
      if (r.outcome === "verified") setStep("credential");
    } catch (e) { fail(e); } finally { setBusy(false); }
  }

  async function enroll(image: string) {
    if (!session) return; setErr(null); setBusy(true);
    try {
      const c = await api<Cred>("/face-credentials", {
        method: "POST", body: { tenant_subject_id: session.tenant_subject_id, image },
      });
      setCred(c); setStep("done");
    } catch (e) { fail(e); } finally { setBusy(false); }
  }

  async function credAction(action: "revoke" | "erase") {
    if (!cred) return; setErr(null); setMsg(null);
    try {
      if (action === "erase") {
        await api(`/face-credentials/${cred.credential_id}`, { method: "DELETE" });
        setCred({ ...cred, status: "erased" }); setMsg("Credential erased.");
      } else {
        await api(`/face-credentials/${cred.credential_id}/revoke`, { method: "POST" });
        setCred({ ...cred, status: "revoked" }); setMsg("Credential revoked.");
      }
    } catch (e) { fail(e); }
  }

  function reset() {
    setStep("start"); setSession(null); setF({ external_reference: "", display_name: "", subject_type: "member" });
    setAcks({}); setReference(""); setGov(null); setVerified(null); setCred(null); setErr(null); setMsg(null);
  }

  const steps: [Step, string][] = [
    ["start", "Person"], ["consent", "Consent"], ["gov", "ID check"],
    ["verify", "Face"], ["credential", "Face pass"], ["done", "Done"],
  ];
  const idx = steps.findIndex(([s]) => s === step);

  return (
    <div>
      <h1>Verify identity</h1>
      <p className="muted">Enroll a person for face entry: consent → ID check → face → a secure face pass. The government photo and raw data are never stored.</p>

      <div style={{ display: "flex", gap: 8, margin: "14px 0", flexWrap: "wrap" }}>
        {steps.map(([s, label], i) => (
          <span key={s} className={`badge ${i < idx ? "green" : i === idx ? "" : "gray"}`}
                style={i === idx ? { background: "#1e293b", color: "#fff" } : undefined}>
            {i + 1}. {label}
          </span>
        ))}
      </div>

      {err && <div className="error">{err}</div>}

      {step === "start" && (
        <form className="card" onSubmit={startSession}>
          <label>External reference (employee / student / ticket id)</label>
          <input value={f.external_reference} onChange={(e) => setF({ ...f, external_reference: e.target.value })} placeholder="EMP-001" />
          <label>Display name</label>
          <input value={f.display_name} onChange={(e) => setF({ ...f, display_name: e.target.value })} placeholder="Aisha Khan" />
          <label>Subject type</label>
          <select value={f.subject_type} onChange={(e) => setF({ ...f, subject_type: e.target.value })}>
            <option value="member">Member / employee</option>
            <option value="student">Student</option>
            <option value="visitor">Visitor</option>
            <option value="guest">Guest</option>
            <option value="staff">Staff</option>
            <option value="contractor">Contractor</option>
          </select>
          <button type="submit" disabled={busy} style={{ marginTop: 12 }}>{busy ? "Starting…" : "Start verification"}</button>
        </form>
      )}

      {step === "consent" && (
        <div className="card">
          <h2>Purpose-specific consent</h2>
          <p className="muted">Taken in person, before any government data or face is collected.</p>
          {PURPOSES.map(([k, title, desc]) => (
            <label key={k} style={{ display: "flex", gap: 10, alignItems: "flex-start", padding: "8px 0", fontWeight: 400 }}>
              <input type="checkbox" style={{ width: 18, height: 18, marginTop: 2 }} checked={!!acks[k]} onChange={(e) => setAcks({ ...acks, [k]: e.target.checked })} />
              <span><b>{title}</b><br /><span className="muted">{desc}</span></span>
            </label>
          ))}
          <button disabled={!allAcked || busy} onClick={recordConsent} style={{ marginTop: 12 }}>{busy ? "Recording…" : "Record consent & continue"}</button>
        </div>
      )}

      {step === "gov" && (
        <div className="card">
          <h2>Government verification</h2>
          <p className="muted">Government record is <b>simulated</b> in this build (no real KYC photo). The face steps below use the <b>real</b> engine. Only minimal verified claims are kept — no photo, no raw response.</p>
          <label>Credential reference</label>
          <input value={reference} onChange={(e) => setReference(e.target.value)} placeholder="EMP-001" />
          <button disabled={busy} onClick={govFetch} style={{ marginTop: 12 }}>{busy ? "Contacting provider…" : "Fetch verified data"}</button>
        </div>
      )}

      {step === "verify" && (
        <div className="card">
          <h2>Live face check</h2>
          {gov && <p className="muted">Assurance: <b>{gov.assurance_level}</b>. <b>Real</b> liveness/face check on your live capture — a blank or no-face capture will NOT verify (routes to manual review).</p>}
          <div style={{ maxWidth: 360 }}>
            <CameraCapture onCapture={verify} busy={busy} label="Capture & verify" />
          </div>
          {verified && verified.outcome !== "verified" && (
            <div className="error" style={{ marginTop: 12 }}>Outcome: {verified.outcome.replace(/_/g, " ")} — route to manual review.</div>
          )}
        </div>
      )}

      {step === "credential" && (
        <div className="card">
          <h2>Create the face pass</h2>
          <p className="muted">Identity verified ✓. Capture a fresh live face to create the person&apos;s <b>encrypted</b> face pass for entry. The raw image is never stored.</p>
          <div style={{ maxWidth: 360 }}>
            <CameraCapture onCapture={enroll} busy={busy} label="Capture & create credential" />
          </div>
        </div>
      )}

      {step === "done" && (
        <div className="card" style={{ background: "#ecfdf5", borderColor: "#a7f3d0" }}>
          <h2>Verification complete</h2>
          <table>
            <tbody>
              <tr><td className="muted">Subject</td><td>{session?.tenant_subject_id}</td></tr>
              <tr><td className="muted">Identity</td><td><span className="badge green">verified ✓</span></td></tr>
              <tr><td className="muted">Assurance</td><td>{gov?.assurance_level}</td></tr>
              <tr><td className="muted">Credential</td><td>{cred?.credential_id} <span className={`badge ${cred?.status === "active" ? "green" : cred?.status === "erased" ? "red" : "gray"}`}>{cred?.status}</span></td></tr>
              <tr><td className="muted">Expires</td><td>{cred?.expires_at ? new Date(cred.expires_at).toLocaleString() : "no expiry set"}</td></tr>
            </tbody>
          </table>
          {msg && <div className="muted" style={{ marginTop: 8 }}>{msg}</div>}
          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            {cred?.status === "active" && <button className="ghost" style={{ color: "#b45309" }} onClick={() => credAction("revoke")}>Revoke</button>}
            {cred?.status !== "erased" && <button className="ghost" style={{ color: "#dc2626" }} onClick={() => credAction("erase")}>Erase</button>}
            <button onClick={reset}>Verify another person</button>
          </div>
        </div>
      )}
    </div>
  );
}
