"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { useAuth } from "@/components/AuthProvider";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      router.push("/me/collection");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="mx-auto max-w-md px-6 py-16">
      <h1 className="text-3xl font-bold mb-2 tracking-tight">Welcome back</h1>
      <p className="text-text-secondary mb-8 text-sm">
        Pick up where you left off.
      </p>

      <form onSubmit={onSubmit} className="space-y-4">
        <label className="block">
          <span className="block text-sm text-text-secondary mb-1.5">Email</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            placeholder="you@example.com"
            className="w-full rounded-btn bg-bg-surface border border-border px-3 py-2 text-sm focus:outline-none focus:border-accent-yellow/50"
          />
        </label>
        <label className="block">
          <span className="block text-sm text-text-secondary mb-1.5">Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="w-full rounded-btn bg-bg-surface border border-border px-3 py-2 text-sm focus:outline-none focus:border-accent-yellow/50"
          />
        </label>

        {error && (
          <div className="rounded-card bg-accent-red/10 border border-accent-red/30 p-3 text-sm text-accent-red">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-btn bg-accent-yellow text-bg font-semibold py-2.5 hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? "Logging in…" : "Log in"}
        </button>
      </form>

      <p className="mt-6 text-sm text-text-secondary">
        New here?{" "}
        <Link href="/signup" className="text-accent-yellow hover:underline">
          Create an account
        </Link>
      </p>
    </main>
  );
}
