"use client";
// K4 — Consent + face capture. Consent (all four acks) MUST be recorded before
// the camera is enabled. A non-biometric alternative is always offered.
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useCamera } from "../../lib/camera";
import { ApiError, api } from "../../lib/api";

const ACKS = [
  ["purpose_understood", "I understand my face is captured for attendance/identity verification."],
  ["sensitivity_understood", "I understand biometric data is sensitive personal data under the DPDP Act."],
  ["rights_understood", "I understand I can access, export, and erase my data at any time."],
  ["freely_given", "I give this consent freely and was offered a non-biometric alternative."],
] as const;

export default function EnrollPage() {
  const router = useRouter();
  const { videoRef, ready, error, start, capture } = useCamera();
  const [acks, setAcks] = useState<Record<string, boolean>>({});
  const [consented, setConsented] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const allTicked = ACKS.every(([k]) => acks[k]);

  async function confirmConsent() {
    setErr(null);
    setBusy(true);
    try {
      await api("/consent", {
        method: "POST",
        body: { purpose: "attendance", method: "self", acknowledgements: acks },
      });
      setConsented(true);
      await start();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not record consent");
    } finally {
      setBusy(false);
    }
  }

  async function captureAndEnroll() {
    setErr(null);
    const image = capture();
    if (!image) { setErr("Camera not ready"); return; }
    setBusy(true);
    try {
      const data = await api<{ face_id: string }>("/faces/enroll", { method: "POST", body: { image } });
      router.push("/enroll/done");
      void data;
    } catch (e) {
      if (e instanceof ApiError && e.code === "IMAGE_QUALITY_FAILED")
        setErr("Image too blurry or no face detected — please retry.");
      else if (e instanceof ApiError && e.code === "SPOOF_DETECTED")
        setErr("Liveness check failed — use a live camera, not a photo.");
      else setErr(e instanceof ApiError ? e.message : "Enrollment failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="center">
      <div className="card narrow">
        {!consented ? (
          <>
            <h1>Consent</h1>
            <p className="muted">Please review and accept before we capture your face.</p>
            {ACKS.map(([k, label]) => (
              <label key={k} className="checkbox">
                <input type="checkbox" checked={!!acks[k]}
                       onChange={(e) => setAcks({ ...acks, [k]: e.target.checked })} />
                <span>{label}</span>
              </label>
            ))}
            {err && <div className="error">{err}</div>}
            <button disabled={!allTicked || busy} onClick={confirmConsent}
                    style={{ width: "100%", marginTop: 16 }}>
              {busy ? "Saving…" : "I consent — continue"}
            </button>
            <a href="/me/login"><button className="ghost" style={{ width: "100%", marginTop: 8 }}>
              Use manual attendance instead
            </button></a>
          </>
        ) : (
          <>
            <h1>Capture your face</h1>
            <p className="muted">Look straight at the camera, then capture.</p>
            <video ref={videoRef} muted playsInline
                   style={{ width: "100%", borderRadius: 12, background: "#000", transform: "scaleX(-1)" }} />
            {error && <div className="error">{error}</div>}
            {err && <div className="error">{err}</div>}
            <button disabled={!ready || busy} onClick={captureAndEnroll}
                    style={{ width: "100%", marginTop: 16 }}>
              {busy ? "Enrolling…" : "Capture & enroll"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
