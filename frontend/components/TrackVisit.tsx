"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

const SESSION_KEY = "pulllist_session_id";

/**
 * Fires a fire-and-forget POST /api/track-visit on every pathname change.
 * Adds a persistent anonymous session_id to localStorage so we can count
 * unique visitors (anon + logged-in) without storing IPs server-side.
 *
 * Skipped on /admin/* paths so the admin's own dashboard browsing doesn't
 * pollute the traffic stats.
 */
export function TrackVisit() {
  const pathname = usePathname();
  const lastTrackedRef = useRef<string | null>(null);

  useEffect(() => {
    if (!pathname) return;
    // Skip admin views — we don't want LO's triage taps to inflate the
    // numbers he's reading.
    if (pathname.startsWith("/admin")) return;
    // Same path twice in a row (e.g. layout re-render) — already counted.
    if (lastTrackedRef.current === pathname) return;
    lastTrackedRef.current = pathname;

    const sessionId = ensureSessionId();
    const device = detectDevice();
    const referrer = document.referrer || null;

    void fetch("/api/track-visit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        path: pathname,
        referrer,
        device,
      }),
      keepalive: true,
    }).catch(() => {
      // Swallow — visit tracking is best-effort
    });
  }, [pathname]);

  return null;
}

function ensureSessionId(): string {
  if (typeof window === "undefined") return "ssr";
  let id = window.localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = generateId();
    window.localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

function generateId(): string {
  // crypto.randomUUID exists in all modern browsers + Node; fall back to
  // Math.random concat for the rare environment that doesn't have it.
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return (
    Math.random().toString(36).slice(2) + Date.now().toString(36)
  );
}

function detectDevice(): "mobile" | "tablet" | "desktop" | "bot" {
  if (typeof navigator === "undefined") return "desktop";
  const ua = navigator.userAgent.toLowerCase();
  if (/bot|crawler|spider|crawling/i.test(ua)) return "bot";
  if (/ipad|tablet/.test(ua)) return "tablet";
  if (/mobile|android|iphone|ipod/.test(ua)) return "mobile";
  return "desktop";
}
