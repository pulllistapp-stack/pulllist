"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { ReactNode, useEffect } from "react";
import { Loader2 } from "lucide-react";

import { useAuth } from "./AuthProvider";

type Props = {
  children: ReactNode;
  /** Where to send already-signed-in visitors. Defaults to home. */
  destination?: string;
};

/**
 * Wraps guest-only pages like /login + /signup. When an authenticated
 * user lands here (typed the URL, followed a stale link, or hit the
 * footer's pre-login section after logging in), shows a brief
 * "already signed in" notice and replaces the route with `destination`.
 *
 * Returns null while auth state is loading so the form doesn't flash
 * for a fraction of a second before the redirect fires.
 */
export function GuestOnly({ children, destination = "/" }: Props) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) {
      router.replace(destination);
    }
  }, [loading, user, router, destination]);

  if (loading) return null;

  if (user) {
    return (
      <main className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4">
        <div className="max-w-md w-full rounded-3xl border border-border bg-bg-surface px-8 py-10 text-center shadow-xl shadow-black/10">
          <div className="mx-auto h-14 w-14 rounded-full bg-accent-green/15 flex items-center justify-center mb-4">
            <Image
              src="/pullist-mascot.png"
              alt=""
              width={36}
              height={36}
              unoptimized
            />
          </div>
          <h2 className="text-lg font-bold text-text-primary">
            You&apos;re already signed in
          </h2>
          <p className="mt-1 text-sm text-text-secondary">
            Logged in as{" "}
            <span className="font-mono text-text-primary">{user.email}</span> —
            taking you home.
          </p>
          <div className="mt-4 inline-flex items-center gap-2 text-xs font-mono text-text-tertiary">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Redirecting...
          </div>
        </div>
      </main>
    );
  }

  return <>{children}</>;
}
