"use client";
// MediaPipe face detection (Tasks Vision). Runs on a <video> and reports whether a
// face large enough to scan is in frame. Degrades gracefully: if the WASM/model can't
// load, `ready` stays false and callers should NOT gate scanning on `faceOn`.
import { useEffect, useRef, useState } from "react";
import type { FaceDetector } from "@mediapipe/tasks-vision";

const VER = "0.10.35";
const WASM = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${VER}/wasm`;
const MODEL = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite";
const MIN_FACE_RATIO = 0.045; // face-box area / frame area — "close enough to scan"
const DETECT_MS = 90;         // throttle detection to ~11 fps

export function useFaceDetect(videoRef: React.RefObject<HTMLVideoElement | null>) {
  const [faceOn, setFaceOn] = useState(false);
  const [ready, setReady] = useState(false);
  const faceOnRef = useRef(false);
  const detRef = useRef<FaceDetector | null>(null);
  const rafRef = useRef<number | null>(null);
  const lastRef = useRef(0);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const vision = await import("@mediapipe/tasks-vision");
        const fileset = await vision.FilesetResolver.forVisionTasks(WASM);
        const make = (delegate: "GPU" | "CPU") =>
          vision.FaceDetector.createFromOptions(fileset, {
            baseOptions: { modelAssetPath: MODEL, delegate },
            runningMode: "VIDEO",
            minDetectionConfidence: 0.5,
          });
        let det: FaceDetector;
        try { det = await make("GPU"); } catch { det = await make("CPU"); }
        if (cancelled) { det.close(); return; }
        detRef.current = det;
        setReady(true);
      } catch {
        if (!cancelled) setReady(false); // graceful fallback — no face gate
      }
    })();

    const loop = () => {
      rafRef.current = requestAnimationFrame(loop);
      const v = videoRef.current, det = detRef.current;
      if (!det || !v || v.readyState < 2 || !v.videoWidth) return;
      const t = performance.now();
      if (t - lastRef.current < DETECT_MS) return;
      lastRef.current = t;
      try {
        const res = det.detectForVideo(v, t);
        let on = false;
        for (const d of res.detections || []) {
          const bb = d.boundingBox;
          const ratio = bb ? (bb.width * bb.height) / (v.videoWidth * v.videoHeight) : 0.1;
          if (ratio >= MIN_FACE_RATIO) { on = true; break; }
        }
        if (on !== faceOnRef.current) { faceOnRef.current = on; setFaceOn(on); }
      } catch { /* transient per-frame error — ignore */ }
    };
    rafRef.current = requestAnimationFrame(loop);

    return () => {
      cancelled = true;
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      detRef.current?.close();
      detRef.current = null;
    };
  }, [videoRef]);

  return { faceOn, faceOnRef, ready };
}
