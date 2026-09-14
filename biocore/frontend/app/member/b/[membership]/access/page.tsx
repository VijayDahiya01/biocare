"use client";
// Where can I go? — the areas at one business, and whether each will open for me.
// Every yes/no here comes from the same rule the door runs (explain_access → evaluate_access
// on the server), so this page cannot promise a door that would turn someone away.
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../../../lib/api";

type ZoneStatus = "open" | "allowed" | "timed" | "expired" | "denied";
type ZoneRow = {
  zone_id: string; name: string; kind: string;
  status: ZoneStatus; open_now: boolean; reason: string; hours: string;
  via_badge: string | null; expires: string | null;
  requires_ppe: boolean; ppe_items: string[];
};
type Overview = {
  membership_id: string; business: string; checked_at: string;
  badges: { name: string; expires: string | null; expired: boolean }[];
  zones: ZoneRow[];
};

// An ISO date with no time is a calendar date, not an instant — read it in the local
// calendar so a browser behind UTC does not render it as the day before.
const dateFmt = (s: string) => {
  const d = /^\d{4}-\d{2}-\d{2}$/.test(s)
    ? new Date(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10))
    : new Date(s);
  return d.toLocaleDateString([], { day: "numeric", month: "long", year: "numeric" });
};

const LOOK: Record<ZoneStatus, { ic: string; tone: string; pill: string; label: string }> = {
  open:    { ic: "🚪", tone: "ok",   pill: "green", label: "Walk in" },
  allowed: { ic: "✓",  tone: "ok",   pill: "green", label: "Open to you" },
  timed:   { ic: "🕒", tone: "wait", pill: "amber", label: "Not right now" },
  expired: { ic: "⚠",  tone: "wait", pill: "amber", label: "Needs renewing" },
  denied:  { ic: "—",  tone: "no",   pill: "gray",  label: "Not yours" },
};

// Most open first: what someone wants to know is where they can go, not where they can't.
const ORDER: ZoneStatus[] = ["allowed", "open", "timed", "expired", "denied"];

function why(z: ZoneRow): string {
  switch (z.status) {
    case "open":
      return z.hours === "Any time"
        ? "No badge needed."
        : `No badge needed. Open ${z.hours}.`;
    case "allowed":
      return z.via_badge
        ? `Your ${z.via_badge} badge lets you in.${z.hours === "Any time" ? "" : ` ${z.hours}.`}`
        : "You can go in.";
    case "timed":
      return z.via_badge
        ? `You have the ${z.via_badge} badge for this — it applies ${z.hours}.`
        : `Open ${z.hours}.`;
    case "expired":
      return z.expires
        ? `Your ${z.via_badge || "badge"} ran out on ${dateFmt(z.expires)}. Ask reception to renew it.`
        : `Your ${z.via_badge || "badge"} has run out. Ask reception to renew it.`;
    default:
      return "You don't have a badge for this area. Reception can add one.";
  }
}

export default function WhereCanIGo({ params }: { params: { membership: string } }) {
  const { membership } = params;
  const router = useRouter();
  const [d, setD] = useState<Overview | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setD(await api<Overview>(`/person/businesses/${membership}/access`)); }
    catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/member/login");
      else setErr(e instanceof ApiError ? e.message : "Could not load");
    }
  }, [membership, router]);
  useEffect(() => { load(); }, [load]);

  if (!d) return <p className="app-sub" style={{ padding: 8 }}>{err || "Loading…"}</p>;

  const openNow = d.zones.filter((z) => z.open_now).length;
  const sorted = [...d.zones].sort(
    (a, b) => ORDER.indexOf(a.status) - ORDER.indexOf(b.status) || a.name.localeCompare(b.name));

  return (
    <div>
      <a className="app-back" href={`/member/b/${membership}`}>← {d.business}</a>
      <h1 className="app-h1">Where can I go?</h1>
      <p className="app-sub">
        {d.zones.length === 0
          ? `${d.business} hasn't set up any areas yet.`
          : `${openNow} of ${d.zones.length} ${d.zones.length === 1 ? "area is" : "areas are"} open to you right now.`}
      </p>

      {d.zones.length === 0 && (
        <div className="app-card" style={{ marginTop: 14 }}>
          <p className="app-sub" style={{ margin: 0 }}>
            Nothing here is locked down yet, so your face works at every reader they put up.
            When they start dividing the building into areas, this page will show which ones
            are yours.
          </p>
        </div>
      )}

      {d.badges.length > 0 && (
        <div className="app-card" style={{ marginTop: 14 }}>
          <div className="app-label" style={{ marginTop: 0 }}>What you hold</div>
          <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
            {d.badges.map((b) => (
              <span key={b.name} className={`pill ${b.expired ? "amber" : "violet"}`}>
                {b.name}{b.expires ? ` · ${b.expired ? "ran out" : "until"} ${dateFmt(b.expires)}` : ""}
              </span>
            ))}
          </div>
        </div>
      )}

      {sorted.length > 0 && (
        <div className="app-card">
          <div className="app-label" style={{ marginTop: 0 }}>Areas</div>
          <div style={{ marginTop: 4 }}>
            {sorted.map((z) => {
              const look = LOOK[z.status];
              return (
                <div key={z.zone_id} className="zrow">
                  <div className={`zic ${look.tone}`} aria-hidden="true">{look.ic}</div>
                  <div className="zmain">
                    <div className="zname">{z.name}</div>
                    <div className="zmeta">{why(z)}</div>
                    {z.requires_ppe && (
                      <div className="zppe">
                        Safety gear required{z.ppe_items.length ? `: ${z.ppe_items.join(", ")}` : ""}
                      </div>
                    )}
                  </div>
                  <span className={`pill ${look.pill}`} style={{ flex: "none" }}>{look.label}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <p className="app-sub" style={{ fontSize: 12.5, padding: "0 4px" }}>
        This is what the door would decide right now. A gate still has to see your face — being
        allowed in is not the same as being let in without looking.
      </p>
    </div>
  );
}
