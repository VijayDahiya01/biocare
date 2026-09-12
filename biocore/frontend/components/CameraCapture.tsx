"use client";
// Reusable camera capture: live preview + a capture button that hands back a
// base64 JPEG. `guide` mode shows a friendly face-circle + instructions for the
// person app (so users know exactly where to put their face).
import { useEffect } from "react";
import { useCamera } from "../lib/camera";

export default function CameraCapture({
  onCapture,
  busy = false,
  disabled = false,
  label = "Capture",
  videoClassName,
  buttonClassName,
  guide = false,
}: {
  onCapture: (image: string) => void;
  busy?: boolean;
  disabled?: boolean;
  label?: string;
  videoClassName?: string;
  buttonClassName?: string;
  guide?: boolean;
}) {
  const { videoRef, ready, error, start, capture } = useCamera();

  useEffect(() => {
    if (!disabled) start();
  }, [disabled, start]);

  const take = () => {
    const img = capture();
    if (img) onCapture(img);
  };

  if (guide) {
    return (
      <div className="cc-guide">
        <div className={`cc-oval ${ready ? "on" : ""}`}>
          <video ref={videoRef} muted playsInline />
          <div className="cc-ring" />
          {!ready && !error && <div className="cc-cam-off">📷<span>Turning on camera…</span></div>}
        </div>
        <p className="cc-hint">
          {error ? "Camera blocked — allow camera access in your browser, then reload."
            : !ready ? "When your browser asks, tap “Allow” to turn on the camera."
            : "Look straight at the camera and fit your face inside the circle."}
        </p>
        {error && <div className="app-err">{error}</div>}
        <button className={buttonClassName || "btn primary"} disabled={!ready || busy || disabled} onClick={take}>
          {busy ? "Checking your face…" : label}
        </button>
      </div>
    );
  }

  return (
    <div>
      <video
        ref={videoRef}
        muted
        playsInline
        className={videoClassName}
        style={videoClassName ? undefined : { width: "100%", borderRadius: 12, background: "#000", transform: "scaleX(-1)" }}
      />
      {error && <div className={buttonClassName ? "app-err" : "error"}>{error}</div>}
      <button
        className={buttonClassName}
        disabled={!ready || busy || disabled}
        onClick={take}
        style={buttonClassName ? undefined : { width: "100%", marginTop: 12 }}
      >
        {busy ? "Working…" : label}
      </button>
    </div>
  );
}
