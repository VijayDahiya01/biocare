"use client";
// Camera hook: open the webcam via getUserMedia, render to a <video>, and
// capture a frame as a base64 JPEG data URL (the format the backend accepts).
import { useCallback, useEffect, useRef, useState } from "react";

export function useCamera() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const start = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: 640, height: 480 },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        // play() can reject with a benign AbortError if the element re-renders
        // ("interrupted by a new load request") — the video still plays, so ignore it.
        try { await videoRef.current.play(); } catch { /* benign autoplay interrupt */ }
      }
      setReady(true);
    } catch (e: any) {
      setError(e?.message || "Could not access camera");
      setReady(false);
    }
  }, []);

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setReady(false);
  }, []);

  const capture = useCallback((): string | null => {
    const video = videoRef.current;
    if (!video || !ready) return null;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", 0.85);
  }, [ready]);

  useEffect(() => () => stop(), [stop]);

  return { videoRef, ready, error, start, stop, capture };
}
