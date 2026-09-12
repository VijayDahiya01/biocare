"use client";
// A7 — Admin-assisted enrollment. Admin enrolls a person on their behalf; the
// four confirmations must be ticked before the camera will capture.
import { useState } from "react";
import CameraCapture from "../../../components/CameraCapture";
import { ApiError, api } from "../../../lib/api";

const TYPES = ["patient", "inmate", "citizen", "devotee", "visitor", "guardian"];
const CONFIRMS = [
  ["person_present", "The person is physically present."],
  ["purpose_explained", "I explained the purpose of enrollment."],
  ["person_consented", "The person consented (verbally or in writing)."],
  ["admin_responsible", "I take responsibility for this enrollment."],
] as const;

export default function AdminEnroll() {
  const [personType, setPersonType] = useState("patient");
  const [form, setForm] = useState({ first_name: "", last_name: "", reference_id: "", purpose: "", expiry_date: "" });
  const [confirms, setConfirms] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState<{ user_id: string; consent_ref: string } | null>(null);

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });
  const allConfirmed = CONFIRMS.every(([k]) => confirms[k]);
  const detailsOk = form.first_name.trim() && form.purpose.trim();

  async function enroll(image: string) {
    setErr(null); setBusy(true);
    try {
      const data = await api<{ user_id: string; consent_ref: string }>("/admin/enroll", {
        method: "POST",
        body: {
          person_type: personType, first_name: form.first_name.trim(),
          last_name: form.last_name.trim() || null, reference_id: form.reference_id.trim() || null,
          purpose: form.purpose.trim(), image, consent_method: "in_person_verbal",
          expiry_date: form.expiry_date || null, extra: {},
          person_present: confirms.person_present, purpose_explained: confirms.purpose_explained,
          person_consented: confirms.person_consented, admin_responsible: confirms.admin_responsible,
        },
      });
      setDone(data);
    } catch (e) {
      if (e instanceof ApiError && e.code === "IMAGE_QUALITY_FAILED") setErr("Image quality failed — retry.");
      else setErr(e instanceof ApiError ? e.message : "Enrollment failed");
    } finally { setBusy(false); }
  }

  function reset() {
    setDone(null); setForm({ first_name: "", last_name: "", reference_id: "", purpose: "", expiry_date: "" });
    setConfirms({});
  }

  if (done) {
    return (
      <div>
        <h1>Admin-assisted enrollment</h1>
        <div className="card" style={{ marginTop: 16, maxWidth: 480, background: "#ecfdf5", borderColor: "#a7f3d0" }}>
          <h2>✅ Enrolled</h2>
          <p className="muted">User ID: <code>{done.user_id}</code></p>
          <p className="muted">Consent ref: <code>{done.consent_ref}</code></p>
          <button onClick={reset} style={{ marginTop: 12 }}>Enroll another</button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1>Admin-assisted enrollment</h1>
      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", marginTop: 16 }}>
        <div className="card">
          <label>Person type</label>
          <select value={personType} onChange={(e) => setPersonType(e.target.value)}>
            {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <label>First name</label>
          <input value={form.first_name} onChange={set("first_name")} required />
          <label>Last name</label>
          <input value={form.last_name} onChange={set("last_name")} />
          <label>Reference ID</label>
          <input value={form.reference_id} onChange={set("reference_id")} placeholder="PAT-4821" />
          <label>Purpose</label>
          <input value={form.purpose} onChange={set("purpose")} placeholder="Patient identity verification" required />
          <label>Expiry (optional)</label>
          <input type="date" value={form.expiry_date} onChange={set("expiry_date")} />
        </div>

        <div className="card">
          <h2>Confirmations</h2>
          {CONFIRMS.map(([k, label]) => (
            <label key={k} className="checkbox">
              <input type="checkbox" checked={!!confirms[k]}
                     onChange={(e) => setConfirms({ ...confirms, [k]: e.target.checked })} />
              <span>{label}</span>
            </label>
          ))}
          <div style={{ marginTop: 14 }}>
            {!allConfirmed || !detailsOk ? (
              <p className="muted">Complete the details and tick all four confirmations to enable capture.</p>
            ) : (
              <CameraCapture onCapture={enroll} busy={busy} label="Capture & enroll" />
            )}
          </div>
          {err && <div className="error">{err}</div>}
        </div>
      </div>
    </div>
  );
}
