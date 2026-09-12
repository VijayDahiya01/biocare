"use client";
// Verified access overview (§11.4 / §10.6) — status-only admin views: verification funnel,
// subjects, device certificates and the erasure queue. No government photo, template or key
// is ever shown here.
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../lib/api";

type Analytics = { subjects: number; verified: number; active_credentials: number; sessions: number; entry_allow: number; entry_deny: number };
type Subject = { id: string; external_reference: string | null; display_name: string | null; subject_type: string; status: string; verification_status: string; authorization_status: string };
type Erasure = { id: string; tenant_subject_id: string; scope: string; status: string; created_at: string | null };
type Cert = { id: string; device_name: string; thumbprint: string; issued_at: string | null; expires_at: string | null; revoked: boolean };

export default function VerifiedAccess() {
  const router = useRouter();
  const [a, setA] = useState<Analytics | null>(null);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [erasure, setErasure] = useState<Erasure[]>([]);
  const [certs, setCerts] = useState<Cert[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [an, su, er, ce] = await Promise.all([
        api<Analytics>("/identity/analytics"),
        api<{ items: Subject[] }>("/identity/subjects"),
        api<{ items: Erasure[] }>("/privacy/erasure"),
        api<{ items: Cert[] }>("/devices/certificates"),
      ]);
      setA(an); setSubjects(su.items); setErasure(er.items); setCerts(ce.items);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) { router.push("/admin/login"); return; }
      setErr(e instanceof ApiError ? e.message : "Could not load");
    }
  }, [router]);
  useEffect(() => { load(); }, [load]);

  const vbadge = (v: string) => (v === "verified" ? "green" : v === "failed" ? "red" : "gray");
  const tiles: [string, number | undefined][] = [
    ["People", a?.subjects], ["Verified", a?.verified], ["Active face passes", a?.active_credentials],
    ["Verifications", a?.sessions], ["Entry allowed", a?.entry_allow], ["Entry denied", a?.entry_deny],
  ];

  return (
    <div>
      <h1>Face access</h1>
      <p className="muted">Overview of face entry — who&apos;s verified, active face passes, terminals and erasure requests. No photo, face data or key is ever shown.</p>
      {err && <div className="error">{err}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))", gap: 12, marginTop: 16 }}>
        {tiles.map(([l, v]) => (
          <div key={l} className="card" style={{ textAlign: "center" }}>
            <div style={{ fontSize: 28, fontWeight: 700 }}>{v ?? "—"}</div>
            <div className="muted" style={{ fontSize: 12 }}>{l}</div>
          </div>
        ))}
      </div>

      <h2 style={{ marginTop: 24 }}>People</h2>
      <div className="card">
        <table>
          <thead><tr><th>Reference</th><th>Name</th><th>Type</th><th>Verified</th><th>Access</th></tr></thead>
          <tbody>
            {subjects.map((s) => (
              <tr key={s.id}>
                <td>{s.external_reference || "—"}</td><td>{s.display_name || "—"}</td><td>{s.subject_type}</td>
                <td><span className={`badge ${vbadge(s.verification_status)}`}>{s.verification_status}</span></td>
                <td><span className="badge gray">{s.authorization_status}</span></td>
              </tr>
            ))}
            {subjects.length === 0 && <tr><td colSpan={5} className="muted">No people yet — add one in Verify identity.</td></tr>}
          </tbody>
        </table>
      </div>

      <h2 style={{ marginTop: 24 }}>Device certificates</h2>
      <div className="card">
        <table>
          <thead><tr><th>Device</th><th>Thumbprint</th><th>Issued</th><th>Expires</th><th>Status</th></tr></thead>
          <tbody>
            {certs.map((c) => (
              <tr key={c.id}>
                <td>{c.device_name}</td><td style={{ fontFamily: "monospace" }}>{c.thumbprint}</td>
                <td>{c.issued_at ? new Date(c.issued_at).toLocaleDateString() : "—"}</td>
                <td>{c.expires_at ? new Date(c.expires_at).toLocaleDateString() : "—"}</td>
                <td><span className={`badge ${c.revoked ? "red" : "green"}`}>{c.revoked ? "revoked" : "active"}</span></td>
              </tr>
            ))}
            {certs.length === 0 && <tr><td colSpan={5} className="muted">No device certificates. Pair a terminal to issue one.</td></tr>}
          </tbody>
        </table>
      </div>

      <h2 style={{ marginTop: 24 }}>Erasure queue</h2>
      <div className="card">
        <table>
          <thead><tr><th>Subject</th><th>Scope</th><th>Status</th><th>Requested</th></tr></thead>
          <tbody>
            {erasure.map((j) => (
              <tr key={j.id}>
                <td style={{ fontFamily: "monospace", fontSize: 12 }}>{j.tenant_subject_id.slice(0, 8)}…</td>
                <td>{j.scope}</td>
                <td><span className={`badge ${j.status === "completed" ? "green" : j.status === "failed" ? "red" : "gray"}`}>{j.status}</span></td>
                <td>{j.created_at ? new Date(j.created_at).toLocaleString() : "—"}</td>
              </tr>
            ))}
            {erasure.length === 0 && <tr><td colSpan={4} className="muted">No erasure requests.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
