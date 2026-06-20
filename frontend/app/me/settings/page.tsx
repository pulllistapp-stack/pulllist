"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AlertTriangle, Trash2, User as UserIcon } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { deleteMe } from "@/lib/auth";

export default function AccountSettingsPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [confirmEmail, setConfirmEmail] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <main className="min-h-[calc(100vh-4rem)] flex items-center justify-center">
        <div className="h-8 w-8 rounded-full border-2 border-accent-yellow border-t-transparent animate-spin" />
      </main>
    );
  }

  const canDelete = confirmEmail.trim().toLowerCase() === user.email.toLowerCase();

  const handleDelete = async () => {
    setError(null);
    setDeleting(true);
    try {
      await deleteMe();
      logout();
      router.replace("/?account_deleted=1");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete account");
      setDeleting(false);
    }
  };

  return (
    <main className="max-w-2xl mx-auto px-4 py-10 space-y-8">
      <header>
        <p className="font-mono text-xs uppercase tracking-widest text-text-tertiary">
          Account
        </p>
        <h1 className="mt-1 text-3xl font-extrabold tracking-tight text-text-primary">
          Settings
        </h1>
      </header>

      {/* Profile */}
      <section className="rounded-2xl border border-border bg-bg-surface p-6">
        <h2 className="text-sm font-mono uppercase tracking-widest text-text-tertiary mb-4">
          Profile
        </h2>
        <div className="flex items-center gap-4">
          <div className="h-16 w-16 rounded-full border border-border overflow-hidden bg-bg flex items-center justify-center flex-shrink-0">
            {user.avatar_url ? (
              <Image
                src={user.avatar_url}
                alt={user.name ?? user.email}
                width={64}
                height={64}
                className="object-cover w-full h-full"
                unoptimized
              />
            ) : (
              <UserIcon className="h-7 w-7 text-text-tertiary" />
            )}
          </div>
          <div className="min-w-0">
            <p className="font-semibold text-text-primary truncate">
              {user.name ?? "Unnamed trainer"}
            </p>
            <p className="text-sm text-text-secondary truncate">{user.email}</p>
          </div>
        </div>

        <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Link
            href="/portfolio"
            className="rounded-full border border-border bg-bg px-4 py-2 text-sm font-semibold text-center hover:border-accent-yellow/60 transition-colors"
          >
            View portfolio
          </Link>
          <Link
            href="/wishlist"
            className="rounded-full border border-border bg-bg px-4 py-2 text-sm font-semibold text-center hover:border-accent-yellow/60 transition-colors"
          >
            View wishlist
          </Link>
        </div>
      </section>

      {/* Danger zone */}
      <section className="rounded-2xl border-2 border-accent-red/40 bg-bg-surface p-6">
        <div className="flex items-center gap-2 mb-4">
          <AlertTriangle className="h-4 w-4 text-accent-red" />
          <h2 className="text-sm font-mono uppercase tracking-widest text-accent-red">
            Danger zone
          </h2>
        </div>

        <h3 className="text-lg font-bold text-text-primary">
          Delete account
        </h3>
        <p className="mt-1 text-sm text-text-secondary">
          Permanently removes your account, collection, wishlist, portfolio
          history, and shared links. <strong>This cannot be undone.</strong>
        </p>

        <div className="mt-5 space-y-3">
          <label className="block">
            <span className="block text-xs font-mono uppercase tracking-wider text-text-tertiary mb-1.5">
              Type your email to confirm
            </span>
            <input
              type="email"
              value={confirmEmail}
              onChange={(e) => setConfirmEmail(e.target.value)}
              placeholder={user.email}
              className="w-full rounded-full bg-bg border border-border px-4 py-2.5 text-sm focus:outline-none focus:border-accent-red/60 focus:ring-2 focus:ring-accent-red/15 transition-colors"
            />
          </label>

          {error && (
            <div className="rounded-card bg-accent-red/10 border border-accent-red/30 p-3 text-sm text-accent-red">
              {error}
            </div>
          )}

          <button
            type="button"
            onClick={handleDelete}
            disabled={!canDelete || deleting}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-full bg-accent-red text-white font-bold px-6 py-2.5 text-sm hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
          >
            <Trash2 className="h-4 w-4" />
            {deleting ? "Deleting…" : "Delete my account"}
          </button>
        </div>
      </section>
    </main>
  );
}
