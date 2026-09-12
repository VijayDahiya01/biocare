"use client";
// A2 — Dashboard overview: live metrics, live check-in feed, device status.
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../lib/api";

type Presence = { inside_count: number; people: { name: string; since: string }[] };
type Att = { items: { name: string; event_type: string; timestamp: string }[] };
type Dev = { items: { name: string; status: string }[] };

const EVENT_LABEL: Record<string, string> = {
  check_in: "Checked in", check_out: "Checked out", break_start: "Break start", break_end: "Break end",
};
const evLabel = (e: string) => EVENT_LABEL[e] || e.replace(/_/g, " ");

export default function Dashboard() {
  const router = useRouter();
  const [presence, setPresence] = useState<Presence | null>(null);
  const [feed, setFeed] = useState<Att["items"]>([]);
  const [devices, setDevices] = useState<Dev["items"]>([]);

  async function load() {
    try {
      const [p, a, d] = await Promise.all([
        api<Presence>("/attendance/presence"),
        api<Att>("/attendance?page_size=10"),
        api<Dev>("/devices"),
      ]);
      setPresence(p); setFeed(a.items); setDevices(d.items);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/admin/login");
    }
  }

  useEffect(() => {
    load();
    const id = setInterval(load, 10000); // live update every 10s
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const today = feed.filter((f) => new Date(f.timestamp).toDateString() === new Date().toDateString());

  return (
    <div>
      <h1>Dashboard</h1>
      <div className="grid cols-4" style={{ marginTop: 16 }}>
        <div className="metric"><div className="n">{presence?.inside_count ?? "—"}</div><div className="l">Inside now</div></div>
        <div className="metric"><div className="n">{today.length}</div><div className="l">Check-ins today</div></div>
        <div className="metric"><div className="n">{devices.filter((d) => d.status === "online").length}</div><div className="l">Devices online</div></div>
        <div className="metric"><div className="n">{devices.length}</div><div className="l">Devices total</div></div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: "2fr 1fr", marginTop: 20 }}>
        <div className="card">
          <h2>Live check-in feed</h2>
          <table>
            <thead><tr><th>Name</th><th>Event</th><th>Time</th></tr></thead>
            <tbody>
              {feed.map((f, i) => (
                <tr key={i}>
                  <td>{f.name}</td>
                  <td><span className={`badge ${f.event_type === "check_in" ? "green" : "amber"}`}>{evLabel(f.event_type)}</span></td>
                  <td>{new Date(f.timestamp).toLocaleTimeString()}</td>
                </tr>
              ))}
              {feed.length === 0 && <tr><td colSpan={3} className="muted">No events yet.</td></tr>}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h2>Devices</h2>
          <table>
            <tbody>
              {devices.map((d, i) => (
                <tr key={i}>
                  <td>{d.name}</td>
                  <td><span className={`badge ${d.status === "online" ? "green" : d.status === "disabled" ? "red" : "gray"}`}>{d.status}</span></td>
                </tr>
              ))}
              {devices.length === 0 && <tr><td className="muted">No devices.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
