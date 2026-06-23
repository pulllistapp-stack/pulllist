"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { ReactNode, useEffect } from "react";
import { Home, LogOut } from "lucide-react";

import { useAuth } from "./AuthProvider";

type Props = {
  children: ReactNode;
  /** Where the "Go home" button sends the user. Defaults to "/". */
  destination?: string;
};

/**
 * Wraps guest-only pages like /login + /signup. When an authenticated
 * user lands here, shows a centered modal popup (with backdrop) that
 * stays visible until the user picks an action — "Go home" to bounce
 * back to the rest of the site, or "Log out & sign in as someone else"
 * to clear the session and reveal the form they were trying to reach.
 *
 * Returns null while auth state is loading so the form doesn't render
 * for a fraction of a second before the modal takes over.
 */
export function GuestOnly({ children, destination = "/" }: Props) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();

  // Lock body scroll while the modal is up — same pattern as other modals.
  useEffect(() => {
    if (!loading && user) {
      const original = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      return () => {
        document.body.style.overflow = original;
      };
    }
  }, [loading, user]);

  if (loading) return null;

  if (user) {
    return (
      <>
        {/* Faded empty surface behind the modal so logged-out content doesn't flash */}
        <main className="min-h-[calc(100vh-4rem)]" aria-hidden />

        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/55 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="guest-only-title"
        >
          <div className="w-full max-w-md rounded-3xl border border-border bg-bg-surface shadow-2xl shadow-black/30 overflow-hidden">
            <div className="px-7 pt-8 pb-6 text-center">
              <div className="mx-auto h-16 w-16 rounded-full bg-accent-green/15 ring-4 ring-accent-green/20 flex items-center justify-center mb-4">
                <Image
                  src="/pullist-mascot.png"
                  alt=""
                  width={44}
                  height={44}
                  unoptimized
                />
              </div>
              <h2
                id="guest-only-title"
                className="text-xl font-extrabold tracking-tight text-text-primary"
              >
                You&apos;re already signed in
              </h2>
              <p className="mt-2 text-sm text-text-secondary">
                Logged in as{" "}
                <span className="font-mono text-text-primary">{user.email}</span>
                .
              </p>
              <p className="mt-1 text-xs text-text-tertiary">
                Want to keep going, or switch accounts?
              </p>
            </div>

            <div className="flex flex-col gap-2 p-5 border-t border-border bg-bg/40">
              <button
                type="button"
                onClick={() => router.replace(destination)}
                className="inline-flex items-center justify-center gap-2 rounded-full bg-accent-yellow text-gray-900 font-bold px-5 py-2.5 text-sm hover:brightness-105 shadow-md shadow-accent-yellow/30 transition-all"
              >
                <Home className="h-4 w-4" />
                Go home
              </button>
              <button
                type="button"
                onClick={() => logout()}
                className="inline-flex items-center justify-center gap-2 rounded-full border border-border text-text-secondary font-semibold px-5 py-2.5 text-sm hover:text-text-primary hover:border-accent-red/40 transition-colors"
              >
                <LogOut className="h-4 w-4" />
                Log out &amp; switch accounts
              </button>
            </div>
          </div>
        </div>
      </>
    );
  }

  return <>{children}</>;
}
