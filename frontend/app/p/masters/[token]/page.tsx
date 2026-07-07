"use client";

import Image from "next/image";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { MascotLoader } from "@/components/MascotLoader";
import { BinderSpread } from "@/components/portfolio/BinderSpread";
import { getPublicBinderView, type BinderView } from "@/lib/api";

/**
 * Anonymous read-only view of a shared master set.
 *
 * Fetches by share_token and hands the result straight to BinderSpread,
 * with cover-upload / cover-clear callbacks omitted so the binder
 * renders in view-only mode. Progress numbers reflect the OWNER's
 * collection, not the viewer's.
 */
export default function PublicBinderPage() {
  const params = useParams<{ token: string }>();
  const token = params?.token;

  const [view, setView] = useState<BinderView | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        setView(await getPublicBinderView(token));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load");
      }
    })();
  }, [token]);

  if (error) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-16 text-center">
        <div className="text-5xl mb-3" aria-hidden>
          🔒
        </div>
        <h1 className="text-xl font-bold mb-2">Shared binder not found</h1>
        <p className="text-sm text-text-secondary mb-6">
          The link may have been revoked or was never valid.
        </p>
        <Link
          href="/"
          className="inline-flex items-center rounded-full bg-accent-yellow text-bg font-semibold px-4 py-2 text-sm hover:brightness-110"
        >
          Home
        </Link>
      </main>
    );
  }

  if (!view) {
    return (
      <main className="mx-auto max-w-[100rem] px-6 py-10">
        <MascotLoader size="lg" className="py-12" />
      </main>
    );
  }

  const pctBase = view.master_set.total_base
    ? Math.round((view.master_set.owned_base / view.master_set.total_base) * 100)
    : 0;
  const pctMaster = view.master_set.total_master
    ? Math.round(
        (view.master_set.owned_master / view.master_set.total_master) * 100,
      )
    : 0;
  const complete = pctBase === 100 && view.slots.length > 0;

  return (
    <main className="mx-auto max-w-[100rem] px-6 py-10">
      <div className="mb-6 rounded-card border border-border bg-bg-surface p-3 text-xs text-text-tertiary flex flex-wrap items-center gap-2">
        <span aria-hidden>👀</span>
        You&apos;re viewing someone&apos;s public master set. Sign in to build your
        own —{" "}
        <Link
          href="/portfolio/masters"
          className="text-accent-yellow font-semibold hover:brightness-110"
        >
          start yours
        </Link>
        .
      </div>

      <header className="mb-6 flex items-start gap-4 flex-wrap">
        {view.master_set.set_logo_url ? (
          <div className="relative h-16 w-24 shrink-0 flex items-center justify-center">
            <Image
              src={view.master_set.set_logo_url}
              alt=""
              width={96}
              height={64}
              className="max-h-16 w-auto object-contain"
              unoptimized
            />
          </div>
        ) : null}
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-bold tracking-tight">
            {view.master_set.set_name}
          </h1>
          <p className="text-sm text-text-secondary">
            {view.master_set.set_release_date ?? "Release TBD"} · Base{" "}
            {view.master_set.owned_base}/{view.master_set.total_base} · Master{" "}
            {view.master_set.owned_master}/{view.master_set.total_master}
          </p>
        </div>
        <Link
          href={`/sets/${view.master_set.set_id}`}
          className="text-xs text-text-secondary hover:text-text-primary underline decoration-dotted"
        >
          Browse full set →
        </Link>
      </header>

      <section
        className={
          "mb-6 rounded-card border p-4 " +
          (complete
            ? "border-accent-green/60 bg-accent-green/10"
            : "border-border bg-bg-surface")
        }
      >
        <div className="flex items-baseline justify-between mb-2">
          <div className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
            {view.master_set.display_mode === "master"
              ? "Master completion"
              : "Base completion"}
          </div>
          <div className="font-mono tabular-nums text-lg">
            {view.master_set.display_mode === "master" ? pctMaster : pctBase}%
          </div>
        </div>
        <div className="h-3 w-full rounded-full bg-bg overflow-hidden">
          <div
            className={
              "h-full transition-[width] duration-700 " +
              (complete ? "bg-accent-green" : "bg-accent-yellow")
            }
            style={{
              width: `${view.master_set.display_mode === "master" ? pctMaster : pctBase}%`,
            }}
          />
        </div>
      </section>

      {view.slots.length === 0 ? (
        <div className="rounded-card border border-dashed border-border bg-bg-surface p-8 text-center text-sm text-text-secondary">
          This set has no cards catalogued yet.
        </div>
      ) : (
        <BinderSpread
          slots={view.slots}
          gridSize={view.master_set.binder_size}
          setName={view.master_set.set_name}
          setLogoUrl={view.master_set.set_logo_url}
          coverImageUrl={view.master_set.cover_image_url}
          isCompleted={!!view.master_set.completed_at}
        />
      )}
    </main>
  );
}
