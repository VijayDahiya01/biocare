export default function Home() {
  return (
    <div className="center">
      <div className="card narrow">
        <h1>BioCore</h1>
        <p className="muted">Face authentication &amp; attendance platform.</p>
        <div style={{ display: "grid", gap: 10, marginTop: 18 }}>
          <a href="/member/login"><button style={{ width: "100%" }}>Your BioCore (user app)</button></a>
          <a href="/admin/login"><button className="secondary" style={{ width: "100%" }}>Admin portal</button></a>
          <a href="/guard"><button className="secondary" style={{ width: "100%" }}>Check-in terminal (guard)</button></a>
          <a href="/onboard"><button className="ghost" style={{ width: "100%" }}>Create a company (onboarding)</button></a>
          <a href="/register"><button className="ghost" style={{ width: "100%" }}>Register (new member)</button></a>
          <a href="/me/login"><button className="ghost" style={{ width: "100%" }}>Member sign in</button></a>
        </div>
        <p className="muted" style={{ marginTop: 16, fontSize: 12 }}>
          Kiosk terminals open <code>/kiosk?token=…</code> with their device token.
        </p>
      </div>
    </div>
  );
}
