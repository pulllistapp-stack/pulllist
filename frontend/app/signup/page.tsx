"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import {
  Eye,
  EyeOff,
  Lock,
  Mail,
  Sparkles,
  User,
  TrendingUp,
  History,
  Library,
} from "lucide-react";

import { useAuth } from "@/components/AuthProvider";

export default function SignupPage() {
  const router = useRouter();
  const { signup } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Lightweight password strength indicator — purely visual, server still enforces minLength=8
  const strength = passwordStrength(password);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await signup(email, password, name || undefined);
      router.push("/portfolio");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Signup failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="relative min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-10 overflow-hidden">
      {/* Atmospheric glows behind the card */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-32 -left-24 h-96 w-96 rounded-full bg-accent-yellow/15 blur-3xl"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -bottom-32 -right-24 h-96 w-96 rounded-full bg-teal-400/10 blur-3xl"
      />

      <div className="relative w-full max-w-6xl grid grid-cols-1 lg:grid-cols-2 rounded-3xl overflow-hidden border border-border bg-bg-surface shadow-2xl shadow-black/10">
        {/* LEFT — mascot hero + value bullets */}
        <aside className="relative flex flex-col items-center justify-center gap-8 p-12 bg-gradient-to-br from-accent-yellow/15 via-accent-yellow/5 to-teal-400/10 dark:from-accent-yellow/10 dark:via-amber-500/5 dark:to-teal-500/10 text-center">
          <div className="relative h-72 w-72 sm:h-80 sm:w-80 flex items-center justify-center">
            {/* Outer dashed ring — empty, only it rotates */}
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

            {/* Floating mini cards — same vibe as login */}
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
              Build the vault you&apos;ll show off.
            </p>
            <p className="mt-2 text-sm text-text-secondary max-w-xs mx-auto">
              Free forever. Track every pull, watch prices in real time, and chase
              completion across every Mega Evolution set.
            </p>
          </div>

          {/* Value bullets — three quick wins to drive the conversion */}
          <ul className="grid grid-cols-1 gap-2 text-left w-full max-w-xs">
            <ValuePill
              icon={<Library className="h-4 w-4 text-accent-yellow" />}
              label="12,000+ cards indexed"
            />
            <ValuePill
              icon={<TrendingUp className="h-4 w-4 text-accent-green" />}
              label="Live eBay + TCGplayer prices"
            />
            <ValuePill
              icon={<History className="h-4 w-4 text-teal-400" />}
              label="Daily price history & trends"
            />
          </ul>
        </aside>

        {/* RIGHT — form */}
        <section className="p-10 sm:p-12 bg-bg flex flex-col justify-center">
          <h1 className="text-3xl font-extrabold tracking-tight text-text-primary">
            Start collecting — free.
          </h1>
          <p className="mt-1 text-sm text-text-secondary">
            Create your PullList account.
          </p>

          {/* OAuth row (Google stub for now — wires later) */}
          <button
            type="button"
            disabled
            title="Google sign-in coming soon"
            className="mt-6 flex items-center justify-center gap-2 w-full rounded-full border border-border bg-bg-surface px-4 py-2.5 text-sm font-semibold text-text-secondary opacity-70 cursor-not-allowed"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden>
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.99.66-2.25 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            Sign up with Google
            <span className="ml-1 text-[10px] uppercase tracking-wider text-text-tertiary">
              soon
            </span>
          </button>

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
                Display name <span className="lowercase text-text-tertiary/70">(optional)</span>
              </span>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-tertiary" />
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="LO"
                  className="w-full rounded-full bg-bg-surface border border-border pl-10 pr-3 py-2.5 text-sm focus:outline-none focus:border-accent-yellow/60 focus:ring-2 focus:ring-accent-yellow/15 transition-colors"
                />
              </div>
            </label>

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
              <span className="block text-xs font-mono uppercase tracking-wider text-text-tertiary mb-1.5">
                Password
              </span>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-tertiary" />
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                  placeholder="At least 8 characters"
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
              {/* Live strength bar — hidden until the user starts typing */}
              {password.length > 0 && (
                <div className="mt-2 flex items-center gap-2">
                  <div className="flex-1 grid grid-cols-4 gap-1">
                    {[0, 1, 2, 3].map((i) => (
                      <div
                        key={i}
                        className={`h-1 rounded-full ${
                          i < strength.score ? strength.barColor : "bg-border"
                        }`}
                      />
                    ))}
                  </div>
                  <span className={`text-[11px] font-mono uppercase tracking-wider ${strength.textColor}`}>
                    {strength.label}
                  </span>
                </div>
              )}
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
                "Creating account…"
              ) : (
                <>
                  Create account
                  <span aria-hidden>→</span>
                </>
              )}
            </button>

            <p className="text-[11px] text-center text-text-tertiary">
              By creating an account, you agree to our{" "}
              <Link href="#" className="hover:text-text-secondary underline">
                Terms
              </Link>{" "}
              &amp;{" "}
              <Link href="#" className="hover:text-text-secondary underline">
                Privacy
              </Link>
              .
            </p>
          </form>

          <p className="mt-6 text-sm text-center text-text-secondary">
            Already have an account?{" "}
            <Link href="/login" className="text-teal-500 font-semibold hover:text-teal-400">
              Log in
            </Link>
          </p>
        </section>
      </div>
    </main>
  );
}

function ValuePill({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <li className="flex items-center gap-3 rounded-full bg-bg/60 dark:bg-black/20 backdrop-blur border border-border/50 px-4 py-2 text-sm text-text-primary">
      <span className="flex-shrink-0">{icon}</span>
      <span className="font-medium">{label}</span>
    </li>
  );
}

function passwordStrength(pw: string): {
  score: number; // 0..4
  label: string;
  barColor: string;
  textColor: string;
} {
  if (pw.length === 0) {
    return { score: 0, label: "", barColor: "bg-border", textColor: "text-text-tertiary" };
  }
  let score = 0;
  if (pw.length >= 8) score += 1;
  if (pw.length >= 12) score += 1;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score += 1;
  if (/\d/.test(pw) && /[^A-Za-z0-9]/.test(pw)) score += 1;

  if (score <= 1) {
    return { score: Math.max(score, 1), label: "Weak", barColor: "bg-accent-red", textColor: "text-accent-red" };
  }
  if (score === 2) {
    return { score: 2, label: "Okay", barColor: "bg-amber-500", textColor: "text-amber-500" };
  }
  if (score === 3) {
    return { score: 3, label: "Good", barColor: "bg-teal-400", textColor: "text-teal-400" };
  }
  return { score: 4, label: "Strong", barColor: "bg-accent-green", textColor: "text-accent-green" };
}
