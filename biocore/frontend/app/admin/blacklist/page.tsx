"use client";
// A12 — Blacklist: capture a face to add, list existing entries.
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import CameraCapture from "../../../components/CameraCapture";
import { ApiError, api } from "../../../lib/api";

type Entry = { blacklist_id: string; reason: string | null; created_at: string };

export default function Blacklist() {
  const router = useRouter();
  const [items, setItems] = useState<Entry[]>([]);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    try { setItems((await api<{ items: Entry[] }>("/blacklist")).items); }
    catch (e) { if (e instanceof ApiError && e.status === 401) router.push("/admin/login"); }
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  async function add(image: string) {
    setErr(null); setBusy(true);
    try {
      await api("/blacklist", { method: "POST", body: { image, reason: reason.trim() || null } });
      setReason(""); load();
    } catch (e) {
      if (e instanceof ApiError && e.code === "IMAGE_QUALITY_FAILED") setErr("Image quality failed — retry.");
      else setErr(e instanceof ApiError ? e.message : "Failed");
    } finally { setBusy(false); }
  }

  return (
    <div>
      <h1>Blacklist</h1>
      <div className="grid" style={{ gridTemplateColumns: "360px 1fr", marginTop: 16 }}>
        <div className="card">
          <h2>Add face</h2>
          <label>Reason</label>
          <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. trespass notice" />
          <div style={{ marginTop: 12 }}>
            <CameraCapture onCapture={add} busy={busy} label="Capture & blacklist" />
          </div>
          {err && <div className="error">{err}</div>}
        </div>
        <div className="card">
          <h2>Entries</h2>
          <table>
            <thead><tr><th>Reason</th><th>Added</th></tr></thead>
            <tbody>
              {items.map((e) => (
                <tr key={e.blacklist_id}>
                  <td>{e.reason || "—"}</td>
                  <td>{new Date(e.created_at).toLocaleString()}</td>
                </tr>
              ))}
              {items.length === 0 && <tr><td colSpan={2} className="muted">No entries.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
