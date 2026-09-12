"use client";
// A11 — Visitors: create a time-limited invite; share the link/QR target.
import { useState } from "react";
import { ApiError, api } from "../../../lib/api";

type Invite = { invite_id: string; token: string; enroll_url: string; expires_at: string };

export default function Visitors() {
  const [name, setName] = useState("");
  const [hours, setHours] = useState(4);
  const [invite, setInvite] = useState<Invite | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function create(e: React.FormEvent) {
    e.preventDefault(); setErr(null); setCopied(false);
    try {
      const data = await api<Invite>("/visitors/invite", {
        method: "POST", body: { visitor_name: name.trim() || null, valid_hours: Number(hours) },
      });
      setInvite(data);
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Failed"); }
  }

  const link = invite ? `${typeof window !== "undefined" ? window.location.origin : ""}/visit/${invite.token}` : "";

  return (
    <div>
      <h1>Visitors</h1>
      <form className="card" style={{ marginTop: 16, display: "flex", gap: 12, alignItems: "flex-end" }} onSubmit={create}>
        <div style={{ flex: 1 }}><label>Visitor name (optional)</label><input value={name} onChange={(e) => setName(e.target.value)} /></div>
        <div style={{ width: 140 }}><label>Valid hours</label><input type="number" min={1} max={24} value={hours} onChange={(e) => setHours(Number(e.target.value))} /></div>
        <button type="submit">Generate invite</button>
      </form>
      {err && <div className="error">{err}</div>}

      {invite && (
        <div className="card" style={{ marginTop: 16, background: "#eff6ff", borderColor: "#bfdbfe" }}>
          <h2>Invite created</h2>
          <p className="muted">Expires {new Date(invite.expires_at).toLocaleString()}. Share this link (or encode as a QR):</p>
          <p style={{ fontFamily: "monospace", wordBreak: "break-all" }}>{link}</p>
          <button className="secondary" onClick={() => { navigator.clipboard?.writeText(link); setCopied(true); }}>
            {copied ? "Copied!" : "Copy link"}
          </button>
        </div>
      )}
    </div>
  );
}
