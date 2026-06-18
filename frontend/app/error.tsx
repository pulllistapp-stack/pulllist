"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect } from "react";
import { AlertTriangle, Home, RefreshCw } from "lucide-react";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // When we wire Sentry/PostHog this is where the capture call goes.
    // Until then keep the digest visible in the browser console so an
    // affected user can copy it into a support DM.
    if (typeof console !== "undefined") {
      console.error("[PullList] page error:", error.digest ?? "(no digest)", error);
    }
  }, [error]);

  return (
    <main className="relative min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-16 overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute -top-32 -left-24 h-96 w-96 rounded-full bg-accent-red/15 blur-3xl"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -bottom-32 -right-24 h-96 w-96 rounded-full bg-amber-400/10 blur-3xl"
      />

      <div className="relative w-full max-w-xl rounded-3xl border border-border bg-bg-surface shadow-2xl shadow-black/10 p-10 sm:p-12 text-center">
        <div className="mx-auto mb-6 h-32 w-32 sm:h-40 sm:w-40 rounded-full bg-white flex items-center justify-center shadow-[0_18px_40px_-14px_rgba(0,0,0,0.25)]">
          <div className="relative">
            <Image
              src="/pullist-mascot.png"
              alt="PullList mascot taking a knee"
              width={120}
              height={120}
              className="object-contain opacity-90"
              unoptimized
              priority
            />
            <AlertTriangle
              aria-hidden
              className="absolute -top-1 -right-1 h-7 w-7 text-amber-500 fill-amber-200 dark:fill-amber-400/30"
            />
          </div>
        </div>

        <p className="font-mono text-xs uppercase tracking-widest text-text-tertiary">
          500 · Server hiccup
        </p>
        <h1 className="mt-2 text-3xl sm:text-4xl font-extrabold tracking-tight text-text-primary">
          Something broke on our end.
        </h1>
        <p className="mt-3 text-sm text-text-secondary max-w-md mx-auto">
          Not your fault. Most retries fix it — the Render backend wakes from
          cold sleep within ~30 seconds.
        </p>

        {error.digest && (
          <p className="mt-3 font-mono text-[10px] uppercase tracking-wider text-text-tertiary">
            Error id: {error.digest}
          </p>
        )}

        <div className="mt-8 flex flex-col sm:flex-row gap-3 justify-center">
          <button
            type="button"
            onClick={reset}
            className="inline-flex items-center justify-center gap-2 rounded-full bg-accent-yellow text-gray-900 font-bold px-5 py-2.5 text-sm hover:brightness-105 shadow-md shadow-accent-yellow/30 transition-all"
          >
            <RefreshCw className="h-4 w-4" />
            Try again
          </button>
          <Link
            href="/"
            className="inline-flex items-center justify-center gap-2 rounded-full border border-border bg-bg-surface text-text-primary font-semibold px-5 py-2.5 text-sm hover:border-accent-yellow/60 transition-all"
          >
            <Home className="h-4 w-4" />
            Home
          </Link>
        </div>
      </div>
    </main>
  );
}
