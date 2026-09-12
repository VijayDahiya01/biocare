"use client";
// O1 — Company onboarding. A company owner provisions their tenant + first
// entity_admin (POST /admin/tenants), then gets their org code + 2FA secret.
import { useState } from "react";
import { ApiError, api } from "../../lib/api";

const VERTICALS = [
  "office", "factory", "warehouse", "hospital", "school", "university",
  "gym", "retail", "hospitality", "coworking", "religious", "government",
  "events", "logistics",
];
const PLANS = [
  ["starter", "Starter"],
  ["business", "Business"],
  ["enterprise", "Enterprise"],
];

type Provisioned = {
  tenant_id: string;
  org_code: string;
  admin_user_id: string;
  admin_email: string;
  totp_provisioning_uri: string;
};

function suggestOrgCode(name: string): string {
  const base = name.trim().toUpperCase().replace(/[^A-Z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  if (!base) return "";
  return `${base.slice(0, 12)}-${new Date().getFullYear()}`;
}

export default function Onboard() {
  const [form, setForm] = useState({
    name: "", org_code: "", vertical: "office", plan: "starter",
    admin_name: "", admin_email: "", admin_password: "",
  });
  const [orgTouched, setOrgTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState<Provisioned | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const v = e.target.value;
    setForm((f) => {
      const next = { ...f, [k]: v };
      // Keep org_code in sync with the company name until the user edits it.
      if (k === "name" && !orgTouched) next.org_code = suggestOrgCode(v);
      return next;
    });
  };

  const orgCode = form.org_code.trim();
  const passOk = form.admin_password.length >= 8;
  const canSubmit =
    form.name.trim() && orgCode.length >= 2 && form.admin_email.trim() && passOk;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null); setBusy(true);
    try {
      const data = await api<Provisioned>("/admin/tenants", {
        method: "POST",
        body: {
          name: form.name.trim(),
          org_code: orgCode,
          vertical: form.vertical,
          plan: form.plan,
          admin_name: form.admin_name.trim() || "Administrator",
          admin_email: form.admin_email.trim(),
          admin_password: form.admin_password,
        },
      });
      setDone(data);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not create the company. Please try again.");
    } finally { setBusy(false); }
  }

  async function copy(label: string, value: string) {
    try { await navigator.clipboard.writeText(value); setCopied(label); setTimeout(() => setCopied(null), 1500); }
    catch { /* clipboard blocked — the value is visible to select manually */ }
  }

  if (done) {
    const secret = new URLSearchParams(done.totp_provisioning_uri.split("?")[1] || "").get("secret") || "";
    return (
      <div className="center">
        <div className="card" style={{ width: "100%", maxWidth: 560 }}>
          <span className="badge green" style={{ marginBottom: 10 }}>Company created</span>
          <h1>{form.name.trim()} is live on BioCore</h1>
          <p className="muted">Two things to keep before you sign in — your org code and your 2FA secret.</p>

          <div style={{ marginTop: 18, display: "grid", gap: 14 }}>
            <div className="stack">
              <label style={{ margin: 0 }}>Org code — your people join with this</label>
              <div className="copyrow">
                <code className="big">{done.org_code}</code>
                <button type="button" className="secondary" onClick={() => copy("org", done.org_code)}>
                  {copied === "org" ? "Copied" : "Copy"}
                </button>
              </div>
            </div>

            <div className="stack">
              <label style={{ margin: 0 }}>Admin 2FA secret — add it to your authenticator app now</label>
              <div className="copyrow">
                <code className="big">{secret}</code>
                <button type="button" className="secondary" onClick={() => copy("2fa", secret)}>
                  {copied === "2fa" ? "Copied" : "Copy"}
                </button>
              </div>
              <p className="muted" style={{ fontSize: 12, margin: 0 }}>
                Open Google Authenticator (or similar) → add a manual key → paste this secret. You'll need the
                6-digit code to sign in. Full setup link:{" "}
                <code style={{ fontSize: 11, wordBreak: "break-all" }}>{done.totp_provisioning_uri}</code>
              </p>
            </div>
          </div>

          <div style={{ marginTop: 20, display: "grid", gap: 8 }}>
            <a href="/admin/login"><button style={{ width: "100%" }}>Continue to admin sign-in</button></a>
            <p className="muted" style={{ fontSize: 12, textAlign: "center", margin: 0 }}>
              Sign in as <b>{done.admin_email}</b> with your password + a 2FA code.
            </p>
          </div>

          <p className="muted" style={{ fontSize: 11, marginTop: 16 }}>
            tenant <code>{done.tenant_id}</code> · admin <code>{done.admin_user_id}</code>
          </p>
        </div>

        <style>{copyStyles}</style>
      </div>
    );
  }

  return (
    <div className="center">
      <form className="card" style={{ width: "100%", maxWidth: 560 }} onSubmit={submit}>
        <h1>Create your company on BioCore</h1>
        <p className="muted">Provisions your isolated workspace and your owner admin account.</p>

        <h2 style={{ marginTop: 20 }}>Company</h2>
        <label>Company name</label>
        <input value={form.name} onChange={set("name")} placeholder="Acme Hospital" required />

        <div className="row2">
          <div>
            <label>Industry / vertical</label>
            <select value={form.vertical} onChange={set("vertical")}>
              {VERTICALS.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </div>
          <div>
            <label>Plan</label>
            <select value={form.plan} onChange={set("plan")}>
              {PLANS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
        </div>

        <label>Org code</label>
        <input
          value={form.org_code}
          onChange={(e) => { setOrgTouched(true); set("org_code")(e); }}
          placeholder="ACME-2026"
          required
        />
        <p className="muted" style={{ fontSize: 12, marginTop: 4 }}>
          The code your members and guards type to join and check in. Must be unique.
        </p>

        <h2 style={{ marginTop: 22 }}>Owner admin</h2>
        <label>Full name</label>
        <input value={form.admin_name} onChange={set("admin_name")} placeholder="Priya Sharma" />
        <label>Work email</label>
        <input type="email" value={form.admin_email} onChange={set("admin_email")} placeholder="you@acme.com" required />
        <label>Password</label>
        <input type="password" value={form.admin_password} onChange={set("admin_password")}
               placeholder="At least 8 characters" required />
        {form.admin_password && !passOk && (
          <p className="muted" style={{ fontSize: 12, marginTop: 4, color: "#b45309" }}>
            Password must be at least 8 characters.
          </p>
        )}

        {err && <div className="error">{err}</div>}
        <button type="submit" disabled={busy || !canSubmit} style={{ width: "100%", marginTop: 20 }}>
          {busy ? "Creating company…" : "Create company"}
        </button>
        <p className="muted" style={{ fontSize: 12, textAlign: "center", marginTop: 12 }}>
          Already set up? <a href="/admin/login">Admin sign-in</a>
        </p>
      </form>

      <style>{copyStyles}</style>
    </div>
  );
}

const copyStyles = `
  .row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .stack { display: grid; gap: 6px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px 14px; }
  .copyrow { display: flex; align-items: center; gap: 10px; }
  .copyrow code.big { flex: 1; font-size: 18px; font-weight: 700; letter-spacing: .04em; color: #0f172a;
    background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px 12px; overflow-x: auto; white-space: nowrap; }
  .copyrow button { flex: 0 0 auto; }
  @media (max-width: 520px) { .row2 { grid-template-columns: 1fr; } }
`;
