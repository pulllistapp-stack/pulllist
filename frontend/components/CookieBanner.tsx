"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { X } from "lucide-react";

const STORAGE_KEY = "pulllist_cookie_acked";

/**
 * Minimal cookie disclosure banner.
 *
 * PullList uses one first-party cookie (the auth token) and no
 * third-party tracking - we don't need EU-style granular consent UI,
 * just a one-time disclosure that survives session/page refreshes
 * until acknowledged. The banner reads the ack flag from localStorage
 * AFTER mount to avoid hydration mismatch.
 */
export function CookieBanner() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      if (window.localStorage.getItem(STORAGE_KEY) !== "1") {
        setShow(true);
      }
    } catch {
      // Private mode etc. — fall through, banner just won't render.
    }
  }, []);

  const dismiss = () => {
    try {
      window.localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      // ignore
    }
    setShow(false);
  };

  if (!show) return null;

  return (
    <div
      role="dialog"
      aria-live="polite"
      aria-label="Cookie disclosure"
      className="fixed bottom-[calc(0.75rem_+_env(safe-area-inset-bottom))] left-3 right-3 sm:left-auto sm:right-[calc(1rem_+_env(safe-area-inset-right))] sm:bottom-[calc(1rem_+_env(safe-area-inset-bottom))] z-50 max-w-md mx-auto sm:mx-0 rounded-2xl border border-border bg-bg-surface/95 backdrop-blur shadow-2xl shadow-black/20 p-4 sm:p-5"
    >
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <p className="text-sm text-text-primary font-semibold mb-1">
            One cookie, no trackers.
          </p>
          <p className="text-xs text-text-secondary leading-relaxed">
            We use one first-party cookie (
            <code className="font-mono bg-bg border border-border rounded px-1">
              pulllist_token
            </code>
            ) to keep you signed in. No third-party trackers, no ad pixels.{" "}
            <Link
              href="/privacy"
              className="text-teal-500 underline font-medium"
            >
              Privacy
            </Link>
            .
          </p>
        </div>
        <button
          type="button"
          onClick={dismiss}
          className="flex-shrink-0 rounded-full bg-accent-yellow text-gray-900 px-3 py-1.5 text-xs font-bold hover:brightness-105 transition-all"
        >
          Got it
        </button>
        <button
          type="button"
          aria-label="Dismiss"
          onClick={dismiss}
          className="absolute top-2 right-2 sm:hidden text-text-tertiary hover:text-text-primary p-1"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
