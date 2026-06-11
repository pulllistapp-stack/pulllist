"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { useAuth } from "@/components/AuthProvider";

export default function SignupPage() {
  const router = useRouter();
  const { signup } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await signup(email, password, name || undefined);
      router.push("/me/collection");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Signup failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="mx-auto max-w-md px-6 py-16">
      <h1 className="text-3xl font-bold mb-2 tracking-tight">Create your account</h1>
      <p className="text-text-secondary mb-8 text-sm">
        Free. Track your Pokémon TCG collection across every set.
      </p>

      <form onSubmit={onSubmit} className="space-y-4">
        <Field
          label="Display name (optional)"
          value={name}
          onChange={setName}
          placeholder="LO"
          type="text"
        />
        <Field
          label="Email"
          value={email}
          onChange={setEmail}
          placeholder="you@example.com"
          type="email"
          required
        />
        <Field
          label="Password"
          value={password}
          onChange={setPassword}
          placeholder="At least 8 characters"
          type="password"
          required
          minLength={8}
        />

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
          {submitting ? "Creating account…" : "Create account"}
        </button>
      </form>

      <p className="mt-6 text-sm text-text-secondary">
        Already have an account?{" "}
        <Link href="/login" className="text-accent-yellow hover:underline">
          Log in
        </Link>
      </p>
    </main>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  type,
  required,
  minLength,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type: string;
  required?: boolean;
  minLength?: number;
}) {
  return (
    <label className="block">
      <span className="block text-sm text-text-secondary mb-1.5">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        minLength={minLength}
        className="w-full rounded-btn bg-bg-surface border border-border px-3 py-2 text-sm focus:outline-none focus:border-accent-yellow/50"
      />
    </label>
  );
}
