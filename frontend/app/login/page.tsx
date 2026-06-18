"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { Eye, EyeOff, Lock, Mail, Sparkles, TrendingUp } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { GoogleSignInButton } from "@/components/GoogleSignInButton";
import { getTrending, type TrendingMover } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [stayLoggedIn, setStayLoggedIn] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [peakMover, setPeakMover] = useState<TrendingMover | null>(null);

  // Tiny market peak ticker — pulls the biggest 7d gainer from the trending feed
  useEffect(() => {
    getTrending({ periodDays: 7, direction: "up", limit: 1 })
      .then((r) => setPeakMover(r.movers[0] ?? null))
      .catch(() => setPeakMover(null));
  }, []);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      router.push("/portfolio");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="relative min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-10 overflow-hidden">
      {/* Soft amber + mint glow behind the card to anchor the page in both themes */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-32 -left-24 h-96 w-96 rounded-full bg-accent-yellow/15 blur-3xl"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -bottom-32 -right-24 h-96 w-96 rounded-full bg-teal-400/10 blur-3xl"
      />

      <div className="relative w-full max-w-6xl grid grid-cols-1 lg:grid-cols-2 rounded-3xl overflow-hidden border border-border bg-bg-surface shadow-2xl shadow-black/10">
        {/* LEFT — mascot hero */}
        <aside className="relative flex flex-col items-center justify-center gap-8 p-12 bg-gradient-to-br from-accent-yellow/15 via-accent-yellow/5 to-teal-400/10 dark:from-accent-yellow/10 dark:via-amber-500/5 dark:to-teal-500/10 text-center">
          <div className="relative h-72 w-72 sm:h-80 sm:w-80 flex items-center justify-center">
            {/* Outer dashed ring — empty, the ONLY thing that rotates */}
            <div
              aria-hidden
              className="absolute inset-0 rounded-full border-2 border-dashed border-teal-400/60 dark:border-teal-300/40 [animation:pl-slow-spin_28s_linear_infinite]"
            />

            {/* Mascot — clean white circle, gently bobbing */}
            <div
              className="relative h-52 w-52 sm:h-56 sm:w-56 rounded-full bg-white flex items-center justify-center p-5 shadow-[0_18px_40px_-14px_rgba(0,0,0,0.3)] dark:shadow-[0_20px_45px_-10px_rgba(20,184,166,0.45)] [animation:pl-float_5s_ease-in-out_infinite]"
            >
              <Image
                src="/pullist-mascot.png"
                alt="PullList mascot"
                width={200}
                height={200}
                className="object-contain"
                unoptimized
                priority
              />
            </div>

            {/* Floating mini cards — each bobs on its own clock, sitting near the dashed ring */}
            <div
              aria-hidden
              className="absolute top-2 right-3 [animation:pl-float-a_5s_ease-in-out_infinite]"
            >
              <div className="h-14 w-10 rounded-md bg-gradient-to-br from-rose-300 to-amber-300 shadow-lg rotate-12" />
            </div>
            <div
              aria-hidden
              className="absolute bottom-4 left-3 [animation:pl-float-b_6s_ease-in-out_infinite]"
            >
              <div className="h-14 w-10 rounded-md bg-gradient-to-br from-teal-300 to-blue-400 shadow-lg -rotate-12" />
            </div>
            <Sparkles
              aria-hidden
              className="absolute top-8 left-14 h-5 w-5 text-amber-400 fill-amber-400 [animation:pl-float-c_4s_ease-in-out_infinite]"
            />
          </div>

          <div>
            <p className="text-2xl font-extrabold tracking-tight text-text-primary">
              Ready for your next big pull?
            </p>
            <p className="mt-2 text-sm text-text-secondary max-w-xs mx-auto">
              Join thousands of collectors tracking market trends and managing their
              vaults in real time.
            </p>
          </div>

          {/* Market peak ticker */}
          {peakMover && (
            <div className="mt-2 inline-flex items-center gap-2 rounded-full bg-bg/70 dark:bg-black/30 backdrop-blur px-3 py-1.5 text-xs">
              <span className="font-mono uppercase tracking-wider text-text-tertiary">
                Market peak
              </span>
              <TrendingUp className="h-3 w-3 text-accent-green" />
              <span className="font-semibold text-text-primary truncate max-w-[140px]">
                {peakMover.name ?? peakMover.card_id}
              </span>
              <span className="font-semibold text-accent-green">
                +{Math.abs(peakMover.delta_pct).toFixed(1)}%
              </span>
            </div>
          )}
        </aside>

        {/* RIGHT — form */}
        <section className="p-10 sm:p-12 bg-bg flex flex-col justify-center">
          <h1 className="text-3xl font-extrabold tracking-tight text-text-primary">
            Welcome back!
          </h1>
          <p className="mt-1 text-sm text-text-secondary">
            Log in to manage your collection.
          </p>

          <div className="mt-6">
            <GoogleSignInButton
              text="continue_with"
              onSuccess={() => router.push("/portfolio")}
              onError={(msg) => setError(msg)}
            />
          </div>

          <div className="my-6 flex items-center gap-3">
            <div className="h-px flex-1 bg-border" />
            <span className="text-[11px] font-mono uppercase tracking-widest text-text-tertiary">
              or with email
            </span>
            <div className="h-px flex-1 bg-border" />
          </div>

          <form onSubmit={onSubmit} className="space-y-4">
            <label className="block">
              <span className="block text-xs font-mono uppercase tracking-wider text-text-tertiary mb-1.5">
                Email
              </span>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-tertiary" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  placeholder="trainer@pallet.town"
                  className="w-full rounded-full bg-bg-surface border border-border pl-10 pr-3 py-2.5 text-sm focus:outline-none focus:border-accent-yellow/60 focus:ring-2 focus:ring-accent-yellow/15 transition-colors"
                />
              </div>
            </label>

            <label className="block">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-mono uppercase tracking-wider text-text-tertiary">
                  Password
                </span>
                <Link
                  href="#"
                  className="text-xs font-semibold text-teal-500 hover:text-teal-400"
                >
                  Forgot?
                </Link>
              </div>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-tertiary" />
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full rounded-full bg-bg-surface border border-border pl-10 pr-10 py-2.5 text-sm focus:outline-none focus:border-accent-yellow/60 focus:ring-2 focus:ring-accent-yellow/15 transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-text-tertiary hover:text-text-primary"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </label>

            <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer select-none">
              <input
                type="checkbox"
                checked={stayLoggedIn}
                onChange={(e) => setStayLoggedIn(e.target.checked)}
                className="h-4 w-4 rounded border-border accent-accent-yellow"
              />
              Stay logged in for 30 days
            </label>

            {error && (
              <div className="rounded-card bg-accent-red/10 border border-accent-red/30 p-3 text-sm text-accent-red">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-full bg-accent-yellow text-gray-900 font-bold py-3 text-sm hover:brightness-105 disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center justify-center gap-2 shadow-md shadow-accent-yellow/30 transition-all"
            >
              {submitting ? (
                "Logging in…"
              ) : (
                <>
                  Sign in
                  <span aria-hidden>→</span>
                </>
              )}
            </button>
          </form>

          <p className="mt-6 text-sm text-center text-text-secondary">
            Don&apos;t have an account?{" "}
            <Link href="/signup" className="text-teal-500 font-semibold hover:text-teal-400">
              Start collecting — free
            </Link>
          </p>

          <div className="mt-6 flex items-center justify-center gap-4 text-[11px] font-mono uppercase tracking-widest text-text-tertiary">
            <Link href="#" className="hover:text-text-secondary">
              Help
            </Link>
            <span className="opacity-50">·</span>
            <Link href="#" className="hover:text-text-secondary">
              Privacy
            </Link>
            <span className="opacity-50">·</span>
            <Link href="#" className="hover:text-text-secondary">
              Terms
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
