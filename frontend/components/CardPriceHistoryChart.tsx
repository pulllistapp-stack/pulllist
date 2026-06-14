"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { getCardHistory, type CardHistory } from "@/lib/api";

const RANGES = [
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
  { label: "1y", days: 365 },
] as const;

const SOURCE_LABELS: Record<string, string> = {
  tcgplayer: "TCGplayer",
  ebay: "eBay",
  cardmarket: "Cardmarket",
};

const SOURCE_COLORS: Record<string, string> = {
  tcgplayer: "#3B82F6",
  ebay: "#10B981",
  cardmarket: "#F59E0B",
};

type Props = {
  cardId: string;
};

type ChartRow = {
  date: string;
  [source: string]: string | number | null;
};

export function CardPriceHistoryChart({ cardId }: Props) {
  const [days, setDays] = useState(30);
  const [history, setHistory] = useState<CardHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getCardHistory(cardId, { days })
      .then((h) => {
        if (!cancelled) setHistory(h);
      })
      .catch((e) => {
        if (!cancelled) setError(String(e?.message ?? e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [cardId, days]);

  // Merge per-source price points by date into rows the chart can consume.
  const { rows, sources, stats } = useMemo(() => {
    if (!history) return { rows: [] as ChartRow[], sources: [] as string[], stats: null };

    const byDate: Record<string, Record<string, number>> = {};
    const sourceSet = new Set<string>();

    for (const [key, points] of Object.entries(history.series)) {
      const source = key.split(":")[0];
      sourceSet.add(source);
      for (const p of points) {
        if (p.market == null) continue;
        if (!byDate[p.date]) byDate[p.date] = {};
        // If multiple variants exist for the same source/date, keep the highest (typical "market" = best variant).
        const prev = byDate[p.date][source];
        if (prev == null || (typeof p.market === "number" && p.market > prev)) {
          byDate[p.date][source] = p.market;
        }
      }
    }

    const dates = Object.keys(byDate).sort();
    const rows: ChartRow[] = dates.map((d) => ({ date: d, ...byDate[d] }));
    const sources = Array.from(sourceSet);

    // Headline stats: most recent across any source + change vs oldest in window
    let latestPrice: number | null = null;
    let latestDate = "";
    let oldestPrice: number | null = null;
    for (const row of rows) {
      for (const s of sources) {
        const v = row[s];
        if (typeof v === "number") {
          if (oldestPrice == null) oldestPrice = v;
          latestPrice = v;
          latestDate = row.date;
        }
      }
    }
    const stats =
      latestPrice != null && oldestPrice != null
        ? {
            latest: latestPrice,
            latestDate,
            delta: latestPrice - oldestPrice,
            pct: oldestPrice > 0 ? ((latestPrice - oldestPrice) / oldestPrice) * 100 : 0,
            samples: rows.length,
          }
        : null;

    return { rows, sources, stats };
  }, [history]);

  return (
    <div className="rounded-card bg-bg-surface border border-border p-5">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h3 className="text-sm font-mono uppercase tracking-wider text-text-tertiary">
          Price history
        </h3>
        <div className="flex gap-1">
          {RANGES.map((r) => (
            <button
              key={r.days}
              onClick={() => setDays(r.days)}
              className={`px-2.5 py-1 text-xs font-mono rounded transition-colors ${
                days === r.days
                  ? "bg-accent-yellow text-bg-base font-semibold"
                  : "text-text-tertiary hover:text-text-secondary hover:bg-text-tertiary/10"
              }`}
              type="button"
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {stats && (
        <div className="flex items-baseline gap-3 mb-4 font-mono">
          <div className="text-2xl font-bold text-accent-green">
            ${stats.latest.toFixed(2)}
          </div>
          {stats.samples > 1 && (
            <div
              className={`text-sm ${
                stats.delta >= 0 ? "text-accent-green" : "text-rose-400"
              }`}
            >
              {stats.delta >= 0 ? "+" : ""}
              ${stats.delta.toFixed(2)} ({stats.pct >= 0 ? "+" : ""}
              {stats.pct.toFixed(1)}%)
            </div>
          )}
          <div className="text-xs text-text-tertiary">{stats.samples}d sampled</div>
        </div>
      )}

      <div className="h-64">
        {loading ? (
          <div className="h-full flex items-center justify-center text-text-tertiary text-sm">
            Loading…
          </div>
        ) : error ? (
          <div className="h-full flex items-center justify-center text-rose-400 text-sm">
            {error}
          </div>
        ) : rows.length === 0 ? (
          <div className="h-full flex items-center justify-center text-text-tertiary text-sm border border-dashed border-border rounded-card">
            No price history yet. Daily snapshots will appear here as they accumulate.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 8, right: 14, left: -8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
              <XAxis
                dataKey="date"
                stroke="#6b7280"
                tick={{ fontSize: 10 }}
                tickFormatter={(d: string) => (d.length >= 10 ? d.slice(5) : d)}
                minTickGap={20}
              />
              <YAxis
                stroke="#6b7280"
                tick={{ fontSize: 10 }}
                tickFormatter={(v: number) =>
                  v >= 1000 ? `$${(v / 1000).toFixed(1)}k` : `$${v.toFixed(0)}`
                }
                width={50}
              />
              <Tooltip
                contentStyle={{
                  background: "#0b0e14",
                  border: "1px solid #2d3543",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                labelStyle={{ color: "#e8eaed" }}
                formatter={(value, name) => {
                  const v =
                    typeof value === "number"
                      ? `$${value.toFixed(2)}`
                      : value == null
                        ? "—"
                        : String(value);
                  const k = typeof name === "string" ? name : String(name);
                  return [v, SOURCE_LABELS[k] ?? k];
                }}
              />
              <Legend
                wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
                formatter={(value: string) => SOURCE_LABELS[value] ?? value}
              />
              {sources.map((source) => (
                <Line
                  key={source}
                  type="monotone"
                  dataKey={source}
                  stroke={SOURCE_COLORS[source] ?? "#9CA3AF"}
                  strokeWidth={2}
                  dot={{ r: 2 }}
                  activeDot={{ r: 4 }}
                  connectNulls
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
