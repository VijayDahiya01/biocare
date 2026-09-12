"use client";
// M5 — My data: export everything the platform holds, downloadable (DPDP access).
import { useEffect, useState } from "react";
import { ApiError, api } from "../../../lib/api";

export default function MyData() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api("/me/data/export").then(setData).catch((e) =>
      setErr(e instanceof ApiError ? e.message : "Could not load"));
  }, []);

  function download() {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "my-biocore-data.json"; a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="container">
      <p className="muted"><a href="/me">← My portal</a></p>
      <h1>My data</h1>
      <p className="muted">Everything BioCore holds about you. The raw face image is never stored — only an encrypted vector reference.</p>
      {err && <div className="error">{err} — <a href="/me/login">sign in</a></div>}
      {data && (
        <div className="card" style={{ marginTop: 12 }}>
          <button onClick={download} style={{ marginBottom: 12 }}>Download JSON</button>
          <pre style={{ overflow: "auto", fontSize: 12, background: "#f8fafc", padding: 12, borderRadius: 8 }}>
            {JSON.stringify(data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
