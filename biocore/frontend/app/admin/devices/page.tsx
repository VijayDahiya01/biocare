"use client";
// A10 — Devices: list, register (shows one-time pairing token + kiosk URL), disable.
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../../lib/api";

type D = { device_id: string; name: string; status: string; capture_method: string; last_seen: string | null };
type Created = { device_id: string; pairing_token: string; kiosk_url: string };

export default function Devices() {
  const router = useRouter();
  const [items, setItems] = useState<D[]>([]);
  const [name, setName] = useState("");
  const [method, setMethod] = useState("webcam");
  const [created, setCreated] = useState<Created | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    try {
      const d = await api<{ items: D[] }>("/devices");
      setItems(d.items);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/admin/login");
    }
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  async function register(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      const d = await api<Created>("/devices", { method: "POST", body: { name: name.trim(), capture_method: method } });
      setCreated(d); setName(""); load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not register device");
    }
  }

  async function disable(id: string) {
    await api(`/devices/${id}/disable`, { method: "POST" }).catch(() => {});
    load();
  }

  const kioskHref = created ? `/kiosk?token=${created.pairing_token}` : "#";

  return (
    <div>
      <h1>Devices</h1>

      <form className="card" style={{ marginTop: 16, display: "flex", gap: 12, alignItems: "flex-end" }} onSubmit={register}>
        <div style={{ flex: 1 }}><label>Device name</label><input value={name} onChange={(e) => setName(e.target.value)} placeholder="KIOSK-GATE-01" required /></div>
        <div style={{ width: 180 }}><label>Capture</label>
          <select value={method} onChange={(e) => setMethod(e.target.value)}>
            <option value="webcam">Browser webcam</option>
            <option value="rtsp">IP camera (RTSP)</option>
          </select>
        </div>
        <button type="submit">Register</button>
      </form>
      {err && <div className="error">{err}</div>}

      {created && (
        <div className="card" style={{ marginTop: 12, background: "#ecfdf5", borderColor: "#a7f3d0" }}>
          <h2>Device registered — pairing token (shown once)</h2>
          <p style={{ fontFamily: "monospace", wordBreak: "break-all" }}>{created.pairing_token}</p>
          <p className="muted">Open the kiosk on the terminal: <a href={kioskHref}>{`/kiosk?token=…`}</a></p>
        </div>
      )}

      <div className="card" style={{ marginTop: 16 }}>
        <table>
          <thead><tr><th>Name</th><th>Capture</th><th>Status</th><th>Last seen</th><th></th></tr></thead>
          <tbody>
            {items.map((d) => (
              <tr key={d.device_id}>
                <td>{d.name}</td>
                <td>{d.capture_method}</td>
                <td><span className={`badge ${d.status === "online" ? "green" : d.status === "disabled" ? "red" : "gray"}`}>{d.status}</span></td>
                <td>{d.last_seen ? new Date(d.last_seen).toLocaleString() : "—"}</td>
                <td>{d.status !== "disabled" && <button className="ghost" style={{ color: "#dc2626" }} onClick={() => disable(d.device_id)}>Disable</button>}</td>
              </tr>
            ))}
            {items.length === 0 && <tr><td colSpan={5} className="muted">No devices yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
