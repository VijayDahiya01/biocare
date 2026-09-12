"use client";
// K7 — Guardian self-enroll. Opened from the school's secure link; captures the
// guardian's face against the invite token for verified pickup.
import { useState } from "react";
import CameraCapture from "../../../components/CameraCapture";
import { ApiError, api } from "../../../lib/api";

export default function GuardianEnroll({ params }: { params: { token: string } }) {
  const { token } = params;
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function enroll(image: string) {
    setErr(null); setBusy(true);
    try {
      await api("/guardians/enroll", { method: "POST", body: { token, image } });
      setDone(true);
    } catch (e) {
      if (e instanceof ApiError && e.code === "INVITE_INVALID") setErr("This link is invalid or has expired.");
      else if (e instanceof ApiError && e.code === "IMAGE_QUALITY_FAILED") setErr("Image quality failed — please retry.");
      else setErr(e instanceof ApiError ? e.message : "Enrollment failed");
    } finally { setBusy(false); }
  }

  return (
    <div className="center">
      <div className="card narrow">
        {done ? (
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 40 }}>✅</div>
            <h1>You&apos;re enrolled</h1>
            <p className="muted">At pickup, the kiosk will verify your face before the child is released.</p>
          </div>
        ) : (
          <>
            <h1>Guardian enrollment</h1>
            <p className="muted">Capture your face to be verified at school pickup. The raw photo is discarded — only an encrypted vector is kept.</p>
            <CameraCapture onCapture={enroll} busy={busy} label="Capture &amp; enroll" />
            {err && <div className="error">{err}</div>}
          </>
        )}
      </div>
    </div>
  );
}
