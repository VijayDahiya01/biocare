"use client";
// Your details. Until this is filled in, the app only knows your email address — and the name
// on file is a placeholder taken from it, which is not a name and must not reach a guard's
// screen or be compared against a government record.
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ApiError, api } from "../../../lib/api";

type Profile = {
  name: string; email: string | null; phone: string | null;
  gender: string | null; date_of_birth: string | null; profile_complete: boolean;
};

const GENDERS = ["female", "male", "non-binary", "prefer not to say"];

export default function MyDetailsPage() {
  return (
    <Suspense fallback={<p className="app-sub" style={{ padding: 8 }}>One moment…</p>}>
      <MyDetails />
    </Suspense>
  );
}

function MyDetails() {
  const router = useRouter();
  const next = useSearchParams().get("next");

  const [f, setF] = useState({ first_name: "", last_name: "", gender: "",
                               date_of_birth: "", phone: "" });
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api<Profile>("/person/me").then((p) => {
      // Only prefill a name the person actually gave us.
      const [first, ...rest] = p.profile_complete ? p.name.split(" ") : [""];
      setF({
        first_name: first || "", last_name: rest.join(" "),
        gender: p.gender ?? "", date_of_birth: p.date_of_birth ?? "", phone: p.phone ?? "",
      });
      setLoaded(true);
    }).catch((e) => {
      if (e instanceof ApiError && e.status === 401) router.push("/member/login");
      else setErr("Could not load your details.");
    });
  }, [router]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setErr(null); setBusy(true);
    try {
      await api("/person/me", { method: "PATCH", body: f });
      router.push(next || "/member");
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.message : "Could not save. Please try again.");
    } finally { setBusy(false); }
  }

  if (!loaded) return <p className="app-sub" style={{ padding: 8 }}>{err || "One moment…"}</p>;

  return (
    <div>
      <a className="app-back" href="/member">← Home</a>
      <h1 className="app-h1">Your details</h1>
      <p className="app-sub">
        This is the name a gate shows when it recognises you. Only you can change it.
      </p>

      <form className="app-card" style={{ marginTop: 14 }} onSubmit={save}>
        <label htmlFor="fn">First name</label>
        <input id="fn" required value={f.first_name} placeholder="Asha"
               onChange={(e) => setF({ ...f, first_name: e.target.value })} />

        <label htmlFor="ln">Last name</label>
        <input id="ln" value={f.last_name} placeholder="Rao"
               onChange={(e) => setF({ ...f, last_name: e.target.value })} />

        <label htmlFor="gd">Gender <span className="app-sub">(optional)</span></label>
        <select id="gd" value={f.gender} onChange={(e) => setF({ ...f, gender: e.target.value })}>
          <option value="">Prefer not to say</option>
          {GENDERS.map((g) => <option key={g} value={g}>{g}</option>)}
        </select>

        <label htmlFor="dob">Date of birth <span className="app-sub">(optional)</span></label>
        <input id="dob" type="date" value={f.date_of_birth}
               onChange={(e) => setF({ ...f, date_of_birth: e.target.value })} />

        <label htmlFor="ph">Phone <span className="app-sub">(optional)</span></label>
        <input id="ph" type="tel" value={f.phone} placeholder="+91…"
               onChange={(e) => setF({ ...f, phone: e.target.value })} />

        {err && <div className="app-err">{err}</div>}
        <button className="btn primary" type="submit" disabled={busy || f.first_name.trim().length < 2}
                style={{ width: "100%", marginTop: 16 }}>
          {busy ? "Saving…" : "Save"}
        </button>
      </form>
    </div>
  );
}
