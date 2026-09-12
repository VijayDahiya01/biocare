"use client";
// Verification belongs to a BUSINESS, not to the person.
//
// This used to be a one-time "master face capture" reused everywhere. That model is gone: each
// business issues its own credential, so there is nothing to capture without knowing which one.
// Rather than leave a dead screen, this sends people to the right place - straight through when
// they only belong to one business.
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../lib/api";

type Biz = {
  membership_id: string;
  business: string;
  sector: string;
  face_verified_here: boolean;
};

export default function VerifyRouter() {
  const router = useRouter();
  const [places, setPlaces] = useState<Biz[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const d = await api<{ by_sector: Record<string, Biz[]> }>("/person/businesses");
        const all = Object.values(d.by_sector ?? {}).flat();
        const pending = all.filter((b) => !b.face_verified_here);
        // One place still to do: skip the middle step entirely.
        if (pending.length === 1) {
          router.replace(`/app/b/${pending[0].membership_id}/verify`);
          return;
        }
        setPlaces(all);
      } catch (e) {
        setErr(e instanceof ApiError ? e.message : "Could not load your places.");
      }
    })();
  }, [router]);

  if (err) {
    return (
      <div>
        <a className="app-back" href="/app">← Home</a>
        <h1 className="app-h1">Verify your face</h1>
        <div className="app-err" style={{ marginTop: 14 }}>{err}</div>
      </div>
    );
  }

  if (places === null) {
    return (
      <div>
        <a className="app-back" href="/app">← Home</a>
        <h1 className="app-h1">Verify your face</h1>
        <p className="app-sub">One moment…</p>
      </div>
    );
  }

  if (places.length === 0) {
    return (
      <div>
        <a className="app-back" href="/app">← Home</a>
        <h1 className="app-h1">Join a place first</h1>
        <p className="app-sub">
          Your face is verified for one place at a time, so there is nothing to do until you have
          joined somewhere. You need the organisation code from whoever invited you.
        </p>
        <div className="app-card" style={{ marginTop: 14 }}>
          <a className="btn primary" href="/app/join">Join a place</a>
        </div>
      </div>
    );
  }

  const pending = places.filter((b) => !b.face_verified_here);
  const done = places.filter((b) => b.face_verified_here);

  return (
    <div>
      <a className="app-back" href="/app">← Home</a>
      <h1 className="app-h1">Verify your face</h1>
      <p className="app-sub">
        Each place verifies you separately, and holds only its own record. Pick where to do it.
      </p>

      {pending.length > 0 && (
        <div className="app-card" style={{ marginTop: 14 }}>
          {pending.map((b) => (
            <a key={b.membership_id} className="toggle" href={`/app/b/${b.membership_id}/verify`}>
              <span className="tw">
                <b>{b.business}</b>
                <span>{b.sector?.toUpperCase()} · not verified yet</span>
              </span>
            </a>
          ))}
        </div>
      )}

      {done.length > 0 && (
        <div className="app-card">
          <p className="app-sub" style={{ marginBottom: 8 }}>Already verified</p>
          {done.map((b) => (
            <a key={b.membership_id} className="toggle" href={`/app/b/${b.membership_id}`}>
              <span className="tw">
                <b>{b.business}</b>
                <span>{b.sector?.toUpperCase()} · verified</span>
              </span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
