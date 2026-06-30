"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import type { CatalogRegion, SetWithCardCount } from "@/lib/api";
import { listSets } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { seriesLabel } from "@/lib/series";

import { useAuth } from "./AuthProvider";
import { SetCard } from "./SetCard";

type Props = {
  initialSets: SetWithCardCount[];
  region?: CatalogRegion;
};

export function SetsBrowser({ initialSets, region = "en" }: Props) {
  const { user, loading } = useAuth();
  const [sets, setSets] = useState<SetWithCardCount[]>(initialSets);
  const [activeSeries, setActiveSeries] = useState<string | null>(null);

  // Reset to incoming server-rendered list on region switch.
  useEffect(() => {
    setSets(initialSets);
  }, [initialSets]);

  // Once we know the user is logged in, refetch with their token so the
  // backend can fill in per-set `owned_unique` and the progress bars render.
  useEffect(() => {
    if (loading || !user) return;
    const token = getToken();
    if (!token) return;
    let cancelled = false;
    listSets({ token, region })
      .then((fresh) => {
        if (!cancelled) setSets(fresh);
      })
      .catch(() => {
        // Silent — keep the initialSets we already rendered
      });
    return () => {
      cancelled = true;
    };
  }, [user, loading, region]);

  const seriesList = useMemo(() => {
    const groups: Record<string, number> = {};
    for (const s of sets) {
      const key = s.series ?? "Other";
      const date = Date.parse(s.release_date ?? "1970-01-01");
      groups[key] = Math.max(groups[key] ?? 0, date);
    }
    return Object.entries(groups)
      .sort((a, b) => b[1] - a[1])
      .map(([name]) => name);
  }, [sets]);

  const filtered = activeSeries
    ? sets.filter((s) => (s.series ?? "Other") === activeSeries)
    : sets;

  const grouped = useMemo(() => {
    const by: Record<string, SetWithCardCount[]> = {};
    for (const s of filtered) {
      const key = s.series ?? "Other";
      (by[key] ??= []).push(s);
    }
    for (const k of Object.keys(by)) {
      by[k].sort(
        (a, b) =>
          Date.parse(b.release_date ?? "1970-01-01") -
          Date.parse(a.release_date ?? "1970-01-01"),
      );
    }
    return by;
  }, [filtered]);

  const orderedSeries = useMemo(() => {
    return Object.keys(grouped).sort((a, b) => {
      const aMax = Math.max(...grouped[a].map((s) => Date.parse(s.release_date ?? "1970-01-01")));
      const bMax = Math.max(...grouped[b].map((s) => Date.parse(s.release_date ?? "1970-01-01")));
      return bMax - aMax;
    });
  }, [grouped]);

  // Has the user started a collection? If owned_unique > 0 anywhere, hide the
  // "Start tracking" CTA. Otherwise show it with auth-aware copy.
  const hasAnyOwned = useMemo(
    () => sets.some((s) => (s.owned_unique ?? 0) > 0),
    [sets],
  );

  return (
    <>
      {/* Series filter chips */}
      <div className="mb-8 flex flex-wrap gap-2">
        <button
          onClick={() => setActiveSeries(null)}
          className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors ${
            activeSeries === null
              ? "bg-accent-yellow text-gray-900 border-accent-yellow"
              : "bg-bg-surface border-border text-text-secondary hover:text-text-primary hover:border-accent-yellow/40"
          }`}
        >
          All series ({sets.length})
        </button>
        {seriesList.map((series) => {
          const count = sets.filter((s) => (s.series ?? "Other") === series).length;
          return (
            <button
              key={series}
              onClick={() => setActiveSeries(series)}
              className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors ${
                activeSeries === series
                  ? "bg-accent-yellow text-gray-900 border-accent-yellow"
                  : "bg-bg-surface border-border text-text-secondary hover:text-text-primary hover:border-accent-yellow/40"
              }`}
            >
              {seriesLabel(series)} <span className="opacity-60">({count})</span>
            </button>
          );
        })}
      </div>

      {/* Grouped grid */}
      {orderedSeries.map((series) => (
        <section key={series} className="mb-12">
          {activeSeries === null && (
            <h2 className="text-sm font-mono uppercase tracking-wider text-text-tertiary mb-4">
              {seriesLabel(series)}
            </h2>
          )}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {grouped[series].map((s) => (
              <SetCard key={s.id} set={s} />
            ))}
          </div>
        </section>
      ))}

      {/* Pokédex CTA — auth-aware */}
      {!hasAnyOwned && (
        <section className="mt-16 rounded-card border-2 border-dashed border-accent-yellow/30 bg-accent-yellow/5 p-8 text-center">
          <div className="mx-auto mb-3 inline-flex h-12 w-12 items-center justify-center rounded-full bg-accent-yellow/15">
            <span className="text-2xl">📖</span>
          </div>
          <h2 className="text-lg font-bold mb-1">Complete your Pokédex!</h2>
          <p className="mx-auto max-w-md text-sm text-text-secondary">
            {user
              ? "Mark cards you own from any set page and watch your completion bars fill in."
              : "Connect your collection to see automatic completion tracking for every set. Our scout even suggests the cheapest way to finish your binder."}
          </p>
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            {user ? (
              <Link
                href="/cards"
                className="rounded-full bg-accent-yellow px-5 py-2 text-sm font-semibold text-gray-900 hover:brightness-110"
              >
                Browse cards to add
              </Link>
            ) : (
              <Link
                href="/signup"
                className="rounded-full bg-accent-yellow px-5 py-2 text-sm font-semibold text-gray-900 hover:brightness-110"
              >
                Start tracking — free
              </Link>
            )}
            <Link
              href="/cards"
              className="rounded-full border border-border bg-bg-surface px-5 py-2 text-sm font-semibold text-text-secondary hover:text-text-primary hover:border-accent-yellow/40"
            >
              Browse master sets
            </Link>
          </div>
        </section>
      )}
    </>
  );
}
