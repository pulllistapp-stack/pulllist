"use client";

import { useMemo, useState } from "react";

import type { SetWithCardCount } from "@/lib/api";

import { SetCard } from "./SetCard";

type Props = {
  sets: SetWithCardCount[];
};

export function SetsBrowser({ sets }: Props) {
  const [activeSeries, setActiveSeries] = useState<string | null>(null);

  // Build series list ordered by the most recent set in each series
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
              {series} <span className="opacity-60">({count})</span>
            </button>
          );
        })}
      </div>

      {/* Grouped grid */}
      {orderedSeries.map((series) => (
        <section key={series} className="mb-12">
          {activeSeries === null && (
            <h2 className="text-sm font-mono uppercase tracking-wider text-text-tertiary mb-4">
              {series}
            </h2>
          )}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {grouped[series].map((s) => (
              <SetCard key={s.id} set={s} />
            ))}
          </div>
        </section>
      ))}
    </>
  );
}
