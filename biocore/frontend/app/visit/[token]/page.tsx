"use client";
// K6 — Visitor self-enroll. Opened from the invite link/QR; captures the
// visitor's face against the token for time-limited access.
import { useState } from "react";
import CameraCapture from "../../../components/CameraCapture";
import { ApiError, api } from "../../../lib/api";

export default function VisitEnroll({ params }: { params: { token: string } }) {
  const { token } = params;
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const detailsOk = name.trim().length > 0;

  async function enroll(image: string) {
    setErr(null); setBusy(true);
    try {
      await api("/visitors/enroll", { method: "POST", body: { token, name: name.trim(), phone: phone.trim() || null, image } });
      setDone(true);
    } catch (e) {
      if (e instanceof ApiError && e.code === "INVITE_EXPIRED") setErr("This invite has expired.");
      else if (e instanceof ApiError && e.code === "INVITE_USED") setErr("This invite was already used.");
      else if (e instanceof ApiError && e.code === "IMAGE_QUALITY_FAILED") setErr("Image quality failed — retry.");
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
            <p className="muted">You can now check in at the kiosk for the duration of your visit.</p>
          </div>
        ) : (
          <>
            <h1>Visitor check-in</h1>
            <p className="muted">Enter your details, then capture your face.</p>
            <label>Full name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} required />
            <label>Phone (optional)</label>
            <input value={phone} onChange={(e) => setPhone(e.target.value)} />
            <div style={{ marginTop: 12 }}>
              {detailsOk
                ? <CameraCapture onCapture={enroll} busy={busy} label="Capture & enroll" />
                : <p className="muted">Enter your name to enable the camera.</p>}
            </div>
            {err && <div className="error">{err}</div>}
          </>
        )}
      </div>
    </div>
  );
}
