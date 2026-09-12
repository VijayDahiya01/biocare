"use client";
// A business's events (mobile): register (per-event consent) / withdraw.
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../../../lib/api";

type Ev = { event_id: string; name: string; registered: boolean; consented: boolean };

export default function Events({ params }: { params: { membership: string } }) {
  const { membership } = params;
  const router = useRouter();
  const [items, setItems] = useState<Ev[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setItems((await api<{ items: Ev[] }>(`/person/businesses/${membership}/events`)).items); }
    catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/app/login");
      else setErr(e instanceof ApiError ? e.message : "Could not load");
    }
  }, [membership, router]);
  useEffect(() => { load(); }, [load]);

  async function register(id: string) {
    setErr(null);
    try { await api(`/person/events/${id}/register`, { method: "POST" }); await load(); }
    catch (e) {
      if (e instanceof ApiError && e.code === "NO_MASTER_FACE") { router.push(`/app/b/${membership}/verify`); return; }
      setErr(e instanceof ApiError ? e.message : "Failed");
    }
  }
  async function withdraw(id: string) {
    try { await api(`/person/events/${id}/consent/revoke`, { method: "POST" }); await load(); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Failed"); }
  }

  return (
    <div>
      <a className="app-back" href={`/app/b/${membership}`}>← Back</a>
      <h1 className="app-h1">Events</h1>
      {err && <div className="app-err">{err}</div>}

      {items.length === 0 && (
        <div className="app-card" style={{ textAlign: "center", marginTop: 14 }}>
          <div style={{ fontSize: 30 }}>🎫</div>
          <p className="app-sub">No events right now.</p>
        </div>
      )}

      <div className="tiles" style={{ marginTop: 14 }}>
        {items.map((e) => (
          <div key={e.event_id} className="tile" style={{ cursor: "default" }}>

            <div className="ic">🎫</div>
            <div style={{ minWidth: 0 }}>
              <div className="tt">{e.name}</div>
              <div style={{ marginTop: 4, display: "flex", gap: 5 }}>
                {e.registered
                  ? <><span className="pill green">Registered</span>{e.consented && <span className="pill green">Consent ✓</span>}</>
                  : <span className="pill gray">Not registered</span>}
              </div>
            </div>
            {e.registered
              ? <button className="btn danger sm" style={{ marginLeft: "auto" }} onClick={() => withdraw(e.event_id)}>Withdraw</button>
              : <button className="btn primary sm" style={{ marginLeft: "auto" }} onClick={() => register(e.event_id)}>Register</button>}
          </div>
        ))}
      </div>
    </div>
  );
}
