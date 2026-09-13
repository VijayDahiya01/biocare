"use client";
// Person hub (mobile): profile, verify CTA, invites, businesses by sector.
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../lib/api";

type Profile = { name: string; email: string; face_verified: boolean; business_count: number };
type Biz = { membership_id: string; business: string; sector: string; role: string; status: string; face_verified_here: boolean };
type Invite = { invite_id: string; business: string; sector: string; role: string };

const SECTOR_ICON: Record<string, string> = {
  office: "🏢", school: "🎓", hotel: "🏨", gym: "🏋️", hospital: "🏥",
  factory: "🏭", retail: "🛍️", warehouse: "📦", bank: "🏦", construction: "🏗️",
  residential: "🏘️", government: "🏛️", religious: "🛕", logistics: "🚚", event: "🎪",
};
const icon = (s: string) => SECTOR_ICON[s] || "🏢";
const initials = (n: string) => n.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();

const STATUS: Record<string, { label: string; cls: string }> = {
  active: { label: "Active", cls: "green" },
  suspended: { label: "Suspended", cls: "red" },
  pending_face: { label: "Getting started", cls: "amber" },
  pending_email: { label: "Pending email", cls: "amber" },
};
const stat = (s: string) => STATUS[s] || { label: s.replace(/_/g, " "), cls: "amber" };
const humanize = (s: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, " ") : s);

export default function Hub() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [bySector, setBySector] = useState<Record<string, Biz[]>>({});
  const [invites, setInvites] = useState<Invite[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [p, b, inv] = await Promise.all([
        api<Profile>("/person/me"),
        api<{ by_sector: Record<string, Biz[]> }>("/person/businesses"),
        api<{ items: Invite[] }>("/person/invites"),
      ]);
      setProfile(p); setBySector(b.by_sector); setInvites(inv.items);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/member/login");
      else setErr(e instanceof ApiError ? e.message : "Could not load");
    }
  }, [router]);
  useEffect(() => { load(); }, [load]);

  async function accept(id: string) {
    await api(`/person/invites/${id}/accept`, { method: "POST" }).catch(() => {});
    load();
  }

  if (!profile) return <p className="app-sub" style={{ padding: 8 }}>{err || "Loading…"}</p>;

  return (
    <div>
      {/* profile */}
      <div className="app-card grad">
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div className="avatar onGrad">{initials(profile.name)}</div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 18, fontWeight: 800 }}>{profile.name}</div>
            <div className="app-sub" style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{profile.email}</div>
            <div style={{ marginTop: 6 }}>
              {profile.face_verified
                ? <span className="pill light">Face verified ✓</span>
                : <span className="pill light">Face not set up</span>}
            </div>
          </div>
        </div>
        {!profile.face_verified && (
          <p className="app-sub" style={{ marginTop: 10, color: "rgba(255,255,255,.85)" }}>
            Open a place below and tap <b>Set up face entry</b> to get started.
          </p>
        )}
      </div>

      <div className="metrics">
        <div className="metric-mini"><div className="n">{profile.business_count}</div><div className="l">Places</div></div>
        <div className="metric-mini"><div className="n">{invites.length}</div><div className="l">Invites</div></div>
        <div className="metric-mini"><div className="n">{profile.face_verified ? "✓" : "—"}</div><div className="l">Verified</div></div>
      </div>

      {invites.length > 0 && (
        <>
          <div className="sector">Invitations</div>
          <div className="tiles">
            {invites.map((i) => (
              <div key={i.invite_id} className="tile" style={{ cursor: "default" }}>
                <div className="ic">{icon(i.sector)}</div>
                <div style={{ minWidth: 0 }}>
                  <div className="tt">{i.business}</div>
                  <div className="ts">{humanize(i.sector)} · {humanize(i.role)}</div>
                </div>
                <button className="btn primary sm" style={{ marginLeft: "auto" }} onClick={() => accept(i.invite_id)}>Accept</button>
              </div>
            ))}
          </div>
        </>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", margin: "18px 4px 4px" }}>
        <div className="sector" style={{ margin: 0 }}>My places</div>
        <a href="/member/join" style={{ fontSize: 14, fontWeight: 600 }}>+ Join</a>
      </div>

      {Object.keys(bySector).length === 0 && (
        <div className="app-card" style={{ textAlign: "center" }}>
          <div style={{ fontSize: 34 }}>🧭</div>
          <p className="app-sub">You haven&apos;t joined any place yet.</p>
          <a href="/member/join"><button className="btn primary">Join a business</button></a>
        </div>
      )}

      {Object.entries(bySector).map(([sector, list]) => (
        <div key={sector}>
          <div className="sector">{icon(sector)} {sector}</div>
          <div className="tiles">
            {list.map((b) => (
              <a key={b.membership_id} className="tile" href={`/member/b/${b.membership_id}`}>
                <div className="ic">{icon(b.sector)}</div>
                <div style={{ minWidth: 0 }}>
                  <div className="tt">{b.business}</div>
                  <div className="ts">{humanize(b.role)}</div>
                  <div style={{ marginTop: 5, display: "flex", gap: 5, flexWrap: "wrap" }}>
                    <span className={`pill ${stat(b.status).cls}`}>{stat(b.status).label}</span>
                    {b.face_verified_here
                      ? <span className="pill green">✓ Face entry</span>
                      : <span className="pill amber">Set up needed</span>}
                  </div>
                </div>
                <span className="chev">›</span>
              </a>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
