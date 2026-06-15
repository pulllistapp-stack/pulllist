"use client";

import Link from "next/link";
import { ArrowRight, ScanLine } from "lucide-react";

import { useAuth } from "./AuthProvider";

/**
 * Two-button CTA row at the top of the hero.
 * - Logged out: "Start collecting — free" → /signup + "Browse sets"
 * - Logged in : "Open portfolio" → /portfolio + "Browse sets"
 *
 * While auth is still resolving, render the logged-out variant so SSR/CSR
 * markup matches and we avoid layout jank. Re-rendering on auth resolution
 * is a one-frame swap.
 */
export function HeroCTA() {
  const { user, loading } = useAuth();
  const signedIn = !loading && !!user;

  return (
    <div className="mt-8 flex flex-wrap gap-3">
      <Link
        href={signedIn ? "/portfolio" : "/signup"}
        className="inline-flex items-center gap-2 rounded-full bg-accent-yellow text-gray-900 font-bold px-6 py-3 text-sm hover:brightness-105 shadow-lg shadow-accent-yellow/30 transition-all"
      >
        {signedIn ? "Open portfolio" : "Start collecting — free"}
        <ArrowRight className="h-4 w-4" aria-hidden />
      </Link>
      {signedIn && (
        <Link
          href="/scan"
          className="inline-flex items-center gap-2 rounded-full border border-accent-yellow/40 bg-accent-yellow/10 text-accent-yellow font-semibold px-6 py-3 text-sm hover:bg-accent-yellow/20 transition-colors"
        >
          <ScanLine className="h-4 w-4" />
          Scan a card
        </Link>
      )}
      <Link
        href="/sets"
        className="inline-flex items-center gap-2 rounded-full border border-border bg-bg-surface text-text-primary font-semibold px-6 py-3 text-sm hover:border-teal-400/40 hover:text-teal-500 dark:hover:text-teal-300 transition-colors"
      >
        Browse sets
      </Link>
    </div>
  );
}

/**
 * Big bottom CTA card. Heading + sub copy + button all swap on auth state.
 */
export function FinalCTA() {
  const { user, loading } = useAuth();
  const signedIn = !loading && !!user;

  return (
    <>
      <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-text-primary">
        {signedIn
          ? `Welcome back${user?.name ? `, ${user.name}` : ""}.`
          : "Your pulls deserve a vault."}
      </h2>
      <p className="mt-3 text-text-secondary max-w-lg mx-auto">
        {signedIn
          ? "Pick up where you left off — check trending, log new pulls, or chase set completion."
          : "Free forever. No card limits, no paywall on history."}
      </p>
      <Link
        href={signedIn ? "/portfolio" : "/signup"}
        className="mt-7 inline-flex items-center gap-2 rounded-full bg-accent-yellow text-gray-900 font-bold px-7 py-3 text-sm hover:brightness-105 shadow-lg shadow-accent-yellow/30 transition-all"
      >
        {signedIn ? "Open your portfolio" : "Create your free account"}
        <ArrowRight className="h-4 w-4" aria-hidden />
      </Link>
    </>
  );
}
