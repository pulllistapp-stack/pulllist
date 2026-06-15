"use client";

import { useEffect } from "react";

/**
 * Registers the PullList service worker on the client. Mounted once at the
 * root layout. Only registers in production — keeps dev iteration fast and
 * avoids stale cached chunks during HMR.
 */
export function PWARegister() {
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!("serviceWorker" in navigator)) return;
    if (process.env.NODE_ENV !== "production") return;

    navigator.serviceWorker
      .register("/sw.js", { scope: "/" })
      .catch((err) => {
        // Non-fatal — PWA install simply won't be offered. Log for dev sanity.
        console.warn("[PullList] Service worker registration failed:", err);
      });
  }, []);

  return null;
}
