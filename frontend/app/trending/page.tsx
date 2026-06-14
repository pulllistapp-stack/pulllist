"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";

import { getTrending, type TrendingMover } from "@/lib/api";

const PERIODS = [
  { label: "1d", days: 1 },
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
] as const;

const SOURCES = ["ebay", "tcgplayer"] as const;

export default function TrendingPage() {
  const [periodDays, setPeriodDays] = useState(7);
  const [source, setSource] = useState<(typeof SOURCES)[number]>("ebay");
  const [direction, setDirection] = useState<"up" | "down">("up");
  const [movers, setMovers] = useState<TrendingMover[]>([]);
  const [eligible, setEligible] = useState(0);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    getTrending({ periodDays, source, direction, limit: 25 })
      .then((r) => {
        if (cancelled) return;
        setMovers(r.movers);
        setEligible(r.total_eligible);
      })
      .catch((e) => {
        if (!cancelled) setErr(String(e?.message ?? e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [periodDays, source, direction]);

  return (
    <main className="mx-auto max-w-5xl px-4 py-10">
      <h1 className="text-3xl font-bold mb-2">Trending</h1>
      <p className="text-text-secondary mb-8">
        Biggest movers across our snapshot data. {eligible} cards eligible in this window.
      </p>

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <div className="flex gap-1 rounded-full border border-border bg-bg-surface p-1">
          {PERIODS.map((p) => (
            <button
              key={p.days}
              onClick={() => setPeriodDays(p.days)}
              className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${
                periodDays === p.days
                  ? "bg-accent-yellow text-bg"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        <div className="flex gap-1 rounded-full border border-border bg-bg-surface p-1">
          <button
            onClick={() => setDirection("up")}
            className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${
              direction === "up"
                ? "bg-accent-green/20 text-accent-green"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            ▲ Gainers
          </button>
          <button
            onClick={() => setDirection("down")}
            className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${
              direction === "down"
                ? "bg-accent-red/20 text-accent-red"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            ▼ Losers
          </button>
        </div>

        <div className="flex gap-1 rounded-full border border-border bg-bg-surface p-1">
          {SOURCES.map((s) => (
            <button
              key={s}
              onClick={() => setSource(s)}
              className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${
                source === s
                  ? "bg-bg-elevated text-text-primary"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {s === "ebay" ? "eBay" : "TCGplayer"}
            </button>
          ))}
        </div>
      </div>

      {err && (
        <div className="rounded-card bg-accent-red/10 border border-accent-red/30 p-4 text-sm mb-4">
          {err}
        </div>
      )}

      {loading ? (
        <div className="text-text-tertiary text-sm">Loading…</div>
      ) : movers.length === 0 ? (
        <div className="rounded-card border-2 border-dashed border-border bg-bg-surface/50 p-10 text-center">
          <p className="text-base font-bold text-text-primary">
            Not enough data yet
          </p>
          <p className="mt-2 text-sm text-text-secondary max-w-md mx-auto">
            Cards need at least 2 snapshots in the {periodDays}d window. Once the daily cron
            (GitHub Actions) has run a couple of times, this page fills in with real movers 🔥
          </p>
        </div>
      ) : (
        <ol className="flex flex-col gap-2">
          {movers.map((m, i) => {
            const up = m.delta_pct >= 0;
            return (
              <li key={m.card_id}>
                <Link
                  href={`/cards/${m.card_id}`}
                  className="flex items-center gap-3 rounded-card border border-border bg-bg-surface p-3 transition-colors hover:border-accent-yellow/40"
                >
                  <span className="w-6 text-center font-mono text-xs text-text-tertiary">
                    {i + 1}
                  </span>
                  <div className="relative h-14 w-10 shrink-0 overflow-hidden rounded-md bg-bg">
                    {m.image_small ? (
                      <Image
                        src={m.image_small}
                        alt={m.name ?? ""}
                        fill
                        className="object-contain"
                        sizes="40px"
                        unoptimized
                      />
                    ) : null}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium text-text-primary">
                      {m.name ?? m.card_id}
                    </div>
                    <div className="truncate text-xs text-text-tertiary font-mono">
                      {m.set_name ?? "?"} · #{m.number ?? "—"}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono text-sm font-bold text-text-primary">
                      ${m.latest_price.toFixed(2)}
                    </div>
                    <div
                      className={`text-xs font-semibold ${
                        up ? "text-accent-green" : "text-accent-red"
                      }`}
                    >
                      {up ? "▲" : "▼"} {Math.abs(m.delta_pct).toFixed(1)}%
                    </div>
                  </div>
                </Link>
              </li>
            );
          })}
        </ol>
      )}
    </main>
  );
}
