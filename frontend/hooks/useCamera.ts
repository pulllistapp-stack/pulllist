"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type CameraState = {
  ready: boolean;
  error: string | null;
  facingMode: "environment" | "user";
  videoRef: React.RefObject<HTMLVideoElement | null>;
  start: () => Promise<void>;
  stop: () => void;
  flip: () => void;
  capture: () => Promise<Blob | null>;
};

/**
 * Browser-camera hook for the scan flow. Rear camera by default
 * (cards are physical, you point at them), flippable to selfie.
 *
 * `capture()` returns a JPEG Blob at native resolution so the
 * downstream Claude Vision call gets the sharpest readable text;
 * the Blob also doubles as the preview shown on the confirm screen.
 */
export function useCamera(): CameraState {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [facingMode, setFacingMode] = useState<"environment" | "user">(
    "environment",
  );

  const stop = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setReady(false);
  }, []);

  const start = useCallback(async () => {
    setError(null);
    try {
      // Stop any prior stream first so flipping camera doesn't leak tracks.
      if (streamRef.current) stop();
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: facingMode },
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setReady(true);
    } catch (e) {
      const msg =
        e instanceof Error
          ? e.name === "NotAllowedError"
            ? "Camera permission denied"
            : e.message
          : "Camera unavailable";
      setError(msg);
      setReady(false);
    }
  }, [facingMode, stop]);

  const flip = useCallback(() => {
    setFacingMode((m) => (m === "environment" ? "user" : "environment"));
  }, []);

  const capture = useCallback(async (): Promise<Blob | null> => {
    const video = videoRef.current;
    if (!video || !ready) return null;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return new Promise((resolve) => {
      canvas.toBlob(
        (blob) => resolve(blob),
        "image/jpeg",
        0.92,
      );
    });
  }, [ready]);

  // Re-attach stream when facingMode flips
  useEffect(() => {
    if (streamRef.current) {
      void start();
    }
    return () => undefined;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [facingMode]);

  // Tear down on unmount
  useEffect(() => {
    return () => stop();
  }, [stop]);

  return { ready, error, facingMode, videoRef, start, stop, flip, capture };
}
