"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import {
  Check,
  Circle,
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
import { GoogleSignInButton } from "@/components/GoogleSignInButton";
import { GuestOnly } from "@/components/GuestOnly";

export default function SignupPage() {
  return (
    <GuestOnly>
      <SignupPageInner />
    </GuestOnly>
  );
}

function SignupPageInner() {
  const router = useRouter();
  const { signup } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  // Honeypot: rendered hidden so humans never touch it. Bots that
  // brute-fill every form field populate this and the backend rejects.
  const [website, setWebsite] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Lightweight password strength indicator — purely visual, server still enforces minLength=8
  const checks = passwordChecks(password);
  const strength = passwordStrength(password);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await signup(email, password, name || undefined, website || undefined);
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
              Free forever. Track every pull across English, Japanese, and Korean
              catalogs — and watch the market every day.
            </p>
          </div>

          {/* Value bullets — three quick wins to drive the conversion */}
          <ul className="grid grid-cols-1 gap-2 text-left w-full max-w-xs">
            <ValuePill
              icon={<Library className="h-4 w-4 text-accent-yellow" />}
              label="43,000+ cards in EN · JP · KR"
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

          <div className="mt-6">
            <GoogleSignInButton
              text="signup_with"
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
            {/* Honeypot — visually hidden from humans (off-screen,
                aria-hidden, tabIndex=-1, autocomplete=off) but
                still in the DOM for form-fill bots to populate.
                Backend rejects on non-empty value. */}
            <div
              aria-hidden="true"
              style={{
                position: "absolute",
                left: "-9999px",
                width: "1px",
                height: "1px",
                overflow: "hidden",
              }}
            >
              <label>
                Website (leave empty)
                <input
                  type="text"
                  name="website"
                  tabIndex={-1}
                  autoComplete="off"
                  value={website}
                  onChange={(e) => setWebsite(e.target.value)}
                />
              </label>
            </div>

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
                  placeholder="Ash"
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
              {/* Live strength bar + criteria — hidden until the user starts typing */}
              {password.length > 0 && (
                <div className="mt-2 space-y-2">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 grid grid-cols-4 gap-1">
                      {[0, 1, 2, 3].map((i) => (
                        <div
                          key={i}
                          className={`h-1 rounded-full transition-colors duration-200 ${
                            i < strength.score ? strength.barColor : "bg-border"
                          }`}
                        />
                      ))}
                    </div>
                    <span className={`text-[11px] font-mono uppercase tracking-wider ${strength.textColor}`}>
                      {strength.label}
                    </span>
                  </div>

                  {/* Live criteria checklist — each item lights up the moment its rule is satisfied,
                      and the whole block collapses into a single "strong" confirmation when 4/4 met. */}
                  {strength.score < 4 ? (
                    <ul className="rounded-xl bg-bg-surface/70 dark:bg-black/20 backdrop-blur-sm border border-border/60 px-3 py-2 grid grid-cols-2 gap-x-3 gap-y-1.5 text-[11px]">
                      <CheckItem met={checks.length8} label="8+ characters" />
                      <CheckItem met={checks.mixedCase} label="Upper + lower" />
                      <CheckItem met={checks.numberAndSymbol} label="Number + symbol" />
                      <CheckItem met={checks.length12} label="12+ for strong" />
                    </ul>
                  ) : (
                    <p className="inline-flex items-center gap-1.5 text-[11px] font-mono uppercase tracking-wider text-accent-green">
                      <Check className="h-3 w-3" aria-hidden /> Locked in — you&apos;re good
                    </p>
                  )}
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

function CheckItem({ met, label }: { met: boolean; label: string }) {
  return (
    <li
      className={`flex items-center gap-1.5 transition-colors duration-200 ${
        met ? "text-accent-green" : "text-text-tertiary"
      }`}
    >
      {met ? (
        <Check className="h-3 w-3 flex-shrink-0" aria-hidden />
      ) : (
        <Circle className="h-3 w-3 flex-shrink-0 opacity-60" aria-hidden />
      )}
      <span className={met ? "line-through opacity-70" : ""}>{label}</span>
    </li>
  );
}

function passwordChecks(pw: string) {
  return {
    length8: pw.length >= 8,
    length12: pw.length >= 12,
    mixedCase: /[A-Z]/.test(pw) && /[a-z]/.test(pw),
    numberAndSymbol: /\d/.test(pw) && /[^A-Za-z0-9]/.test(pw),
  };
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
  const checks = passwordChecks(pw);
  const score = Object.values(checks).filter(Boolean).length;

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
