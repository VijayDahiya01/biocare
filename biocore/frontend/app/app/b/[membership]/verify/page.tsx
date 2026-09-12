"use client";
// Person self-service identity verification (§11.1): consent-before-collection → live
// capture → government-verified identity + encrypted entry credential, for one business.
import { useState } from "react";
import { useRouter } from "next/navigation";
import CameraCapture from "../../../../../components/CameraCapture";
import { ApiError, api } from "../../../../../lib/api";

const PURPOSES: [string, string, string][] = [
  ["identity_verification", "Check my ID", "Confirm who I am using an official source."],
  ["government_data_processing", "Use my ID record", "Use my official record only to verify me — it is not stored."],
  ["live_face_capture", "Take my photo", "Capture a live photo of my face."],
  ["face_to_government_match", "Match my face", "Check my photo matches my official ID."],
  ["entry_template_creation", "Set up face entry", "Create a secure face pass so I can get in."],
  ["entry_authentication", "Enter with my face", "Let me enter with my face at this business."],
];
type Step = "consent" | "capture" | "done";

export default function VerifyIdentity({ params }: { params: { membership: string } }) {
  const { membership } = params;
  const router = useRouter();
  const [step, setStep] = useState<Step>("consent");
  const [acks, setAcks] = useState<Record<string, boolean>>({});
  const [business, setBusiness] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const all = PURPOSES.every(([k]) => acks[k]);
  const acceptAll = () => setAcks(Object.fromEntries(PURPOSES.map(([k]) => [k, true])));

  const STEPS: [Step, string][] = [["consent", "Agree"], ["capture", "Selfie"], ["done", "Verified"]];
  const stepIdx = STEPS.findIndex(([s]) => s === step);

  // What to tell someone standing in front of a camera. A photo that was refused and a service
  // that is offline need opposite advice: one is worth retrying, the other is not their fault.
  function captureAdvice(e: unknown): string {
    if (!(e instanceof ApiError)) return "Something went wrong — please try again.";
    if (e.code === "FACE_ENGINE_UNAVAILABLE")
      return "Face checking is temporarily unavailable. This isn’t anything you did — " +
             "please try again in a few minutes, or tell the organisation.";
    if (e.code === "CAPTURE_REFUSED" || e.code === "IMAGE_QUALITY_FAILED") {
      const reason = String((e.details as { reason?: string } | undefined)?.reason ?? "");
      if (reason.includes("LANDMARK"))
        return "Look straight at the camera and hold still, then take it again.";
      if (reason.includes("POSE") || reason.includes("ANGLE"))
        return "Face the camera square-on — no tilt — and take it again.";
      if (reason.includes("DARK") || reason.includes("LIGHT") || reason.includes("EXPOSURE"))
        return "It’s too dark. Face a window or a light, then take it again.";
      if (reason.includes("OCCLU") || reason.includes("MASK"))
        return "Something is covering your face. Remove glasses, mask or hat and take it again.";
      if (reason.includes("SMALL") || reason.includes("SIZE"))
        return "Move closer so your face fills the circle, then take it again.";
      return "That photo wasn’t clear enough. Find better light, move closer so your face " +
             "fills the circle, hold still, and take it again.";
    }
    if (e.status === 403) return e.message;
    return e.message || "Something went wrong — please try again.";
  }

  async function startVerify() {
    setErr(null); setBusy(true);
    try {
      const d = await api<{ business: string }>(`/person/verify/${membership}/start`, {
        method: "POST", body: { consents: PURPOSES.map(([k]) => k) },
      });
      setBusiness(d.business); setStep("capture");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) { router.push("/app/login"); return; }
      setErr(e instanceof ApiError ? e.message : "Failed");
    } finally { setBusy(false); }
  }

  async function complete(image: string) {
    setErr(null); setBusy(true);
    try {
      const d = await api<{ verified: boolean; outcome: string }>(`/person/verify/${membership}/complete`, {
        method: "POST", body: { reference: membership, image },
      });
      if (d.verified) setStep("done");
      else setErr(`Verification: ${d.outcome.replace(/_/g, " ")} — please try again or contact the business.`);
    } catch (e) {
      setErr(captureAdvice(e));
    } finally { setBusy(false); }
  }

  return (
    <div>
      <a className="app-back" href={`/app/b/${membership}`}>← Back</a>
      <h1 className="app-h1">Set up face entry</h1>
      <p className="app-sub">Three quick steps — done once. Your photo isn&apos;t stored, only a verified confirmation.</p>

      <div className="vstep">
        {STEPS.map(([s, label], i) => (
          <div key={s} className={`vstep-item ${i < stepIdx ? "done" : i === stepIdx ? "now" : ""}`}>
            <span className="vstep-dot">{i < stepIdx ? "✓" : i + 1}</span>
            <span className="vstep-label">{label}</span>
          </div>
        ))}
      </div>

      {err && <div className="app-err">{err}</div>}

      {step === "consent" && (
        <>
          <h2 style={{ margin: "0 0 4px", fontSize: 20 }}>Step 1 · Your consent</h2>
          <p className="app-sub">We need your OK before anything happens. Tap each, or <span className="cc-link" onClick={acceptAll}>agree to all</span>.</p>
          <div className="app-card" style={{ marginTop: 10 }}>
            {PURPOSES.map(([k, title, desc]) => (
              <label key={k} className="toggle">
                <input type="checkbox" checked={!!acks[k]} onChange={(e) => setAcks({ ...acks, [k]: e.target.checked })} />
                <span className="tw"><b>{title}</b><span>{desc}</span></span>
              </label>
            ))}
          </div>
          <button className="btn primary" disabled={!all || busy} onClick={startVerify}>{busy ? "Please wait…" : "I agree — continue"}</button>
        </>
      )}

      {step === "capture" && (
        <div className="app-card" style={{ marginTop: 14 }}>
          <h2 style={{ margin: "0 0 4px", fontSize: 20 }}>Step 2 · Take a selfie</h2>
          <p className="app-sub">The only time we capture your face. Look at the camera and tap the button — that&apos;s it.</p>
          <ul className="cc-tips">
            <li>Good light on your face</li>
            <li>No cap, sunglasses or mask</li>
            <li>Fit your whole face inside the circle</li>
          </ul>
          <CameraCapture onCapture={complete} busy={busy} guide label="Take my photo" buttonClassName="btn primary" />
        </div>
      )}

      {step === "done" && (
        <div className="app-card" style={{ marginTop: 14, textAlign: "center" }}>
          <div style={{ fontSize: 40 }}>✅</div>
          <h2 style={{ marginTop: 6 }}>You&apos;re all set{business ? ` at ${business}` : ""}</h2>
          <p className="app-sub">You can now walk in with just your face. Your photo wasn&apos;t stored — only a secure confirmation.</p>
          <div style={{ marginTop: 8 }}><span className="pill green">✓ Face entry ready</span></div>
          <a href={`/app/b/${membership}`}><button className="btn primary" style={{ marginTop: 14 }}>Done</button></a>
        </div>
      )}
    </div>
  );
}
