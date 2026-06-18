import Image from "next/image";
import Link from "next/link";
import { Compass, Home, Search } from "lucide-react";

import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Lost in the long grass · PullList",
};

export default function NotFound() {
  return (
    <main className="relative min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-16 overflow-hidden">
      {/* soft theme-aware glows so the page feels intentional, not broken */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-32 -left-24 h-96 w-96 rounded-full bg-accent-yellow/15 blur-3xl"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -bottom-32 -right-24 h-96 w-96 rounded-full bg-teal-400/10 blur-3xl"
      />

      <div className="relative w-full max-w-xl rounded-3xl border border-border bg-bg-surface shadow-2xl shadow-black/10 p-10 sm:p-12 text-center">
        <div className="mx-auto mb-6 h-32 w-32 sm:h-40 sm:w-40 rounded-full bg-white flex items-center justify-center shadow-[0_18px_40px_-14px_rgba(0,0,0,0.25)] dark:shadow-[0_20px_45px_-10px_rgba(20,184,166,0.4)] [animation:pl-float_5s_ease-in-out_infinite]">
          <Image
            src="/pullist-mascot.png"
            alt="PullList mascot looking confused"
            width={120}
            height={120}
            className="object-contain"
            unoptimized
            priority
          />
        </div>

        <p className="font-mono text-xs uppercase tracking-widest text-text-tertiary">
          404 · Not Found
        </p>
        <h1 className="mt-2 text-3xl sm:text-4xl font-extrabold tracking-tight text-text-primary">
          Lost in the long grass.
        </h1>
        <p className="mt-3 text-sm text-text-secondary max-w-md mx-auto">
          We couldn&apos;t find that card. The URL might be off, or the card may
          not be in our catalog yet.
        </p>

        <div className="mt-8 flex flex-col sm:flex-row gap-3 justify-center">
          <Link
            href="/"
            className="inline-flex items-center justify-center gap-2 rounded-full bg-accent-yellow text-gray-900 font-bold px-5 py-2.5 text-sm hover:brightness-105 shadow-md shadow-accent-yellow/30 transition-all"
          >
            <Home className="h-4 w-4" />
            Home
          </Link>
          <Link
            href="/search"
            className="inline-flex items-center justify-center gap-2 rounded-full border border-border bg-bg-surface text-text-primary font-semibold px-5 py-2.5 text-sm hover:border-accent-yellow/60 transition-all"
          >
            <Search className="h-4 w-4" />
            Search cards
          </Link>
          <Link
            href="/sets"
            className="inline-flex items-center justify-center gap-2 rounded-full border border-border bg-bg-surface text-text-primary font-semibold px-5 py-2.5 text-sm hover:border-accent-yellow/60 transition-all"
          >
            <Compass className="h-4 w-4" />
            Browse sets
          </Link>
        </div>
      </div>
    </main>
  );
}
