// K5 — Registration complete.
export default function EnrollDonePage() {
  return (
    <div className="center">
      <div className="card narrow" style={{ textAlign: "center" }}>
        <div style={{ fontSize: 48 }}>✅</div>
        <h1>You&apos;re all set</h1>
        <p className="muted">
          Your face has been enrolled. The raw photo was discarded — only an
          encrypted vector is kept. You can now check in at any kiosk.
        </p>
        <a href="/me/login"><button className="secondary" style={{ width: "100%", marginTop: 16 }}>
          Go to my portal
        </button></a>
      </div>
    </div>
  );
}
