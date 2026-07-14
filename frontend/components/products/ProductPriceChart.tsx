"use client";

/**
 * Sealed-product price history chart on the product detail page.
 * Hand-rolled SVG (matching CardPriceChart style) instead of Recharts
 * so the bundle stays small and the theming reuses our CSS vars.
 */

import { useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";

import { getProductHistory, ProductHistoryPoint } from "@/lib/api";

type Range = 30 | 90 | 180 | 365;

const RANGE_LABEL: Record<Range, string> = {
  30: "30d",
  90: "90d",
  180: "6M",
  365: "1Y",
};

function fmtPrice(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1000) return `$${Math.round(v).toLocaleString()}`;
  return `$${v.toFixed(2)}`;
}

function fmtDate(iso: string): string {
  const d = new Date(iso + "T00:00:00Z");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function ProductPriceChart({ productId }: { productId: string }) {
  const [range, setRange] = useState<Range>(90);
  const [points, setPoints] = useState<ProductHistoryPoint[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getProductHistory(productId, range)
      .then((h) => {
        if (!cancelled) setPoints(h.points);
      })
      .catch(() => {
        if (!cancelled) setPoints([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [productId, range]);

  const usable = useMemo(
    () =>
      (points ?? []).filter(
        (p): p is ProductHistoryPoint & { market: number } => p.market != null,
      ),
    [points],
  );

  const stats = useMemo(() => {
    if (!usable.length) return null;
    const values = usable.map((p) => p.market);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const first = usable[0].market;
    const last = usable[usable.length - 1].market;
    const changePct = first > 0 ? ((last - first) / first) * 100 : 0;
    return { min, max, first, last, changePct };
  }, [usable]);

  return (
    <section className="mt-8 rounded-card border border-border bg-bg-surface p-4">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold tracking-tight">Price history</h2>
          <div className="text-[11px] text-text-tertiary">
            TCGplayer daily market price · sealed
          </div>
        </div>
        <div className="flex items-center gap-1 rounded-full border border-border bg-bg p-0.5 text-xs font-mono">
          {([30, 90, 180, 365] as Range[]).map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => setRange(r)}
              className={
                "rounded-full px-2.5 py-0.5 transition-colors " +
                (range === r
                  ? "bg-accent-yellow text-gray-900"
                  : "text-text-tertiary hover:text-text-primary")
              }
            >
              {RANGE_LABEL[r]}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex h-48 items-center justify-center text-text-tertiary">
          <Loader2 className="h-5 w-5 animate-spin" />
        </div>
      ) : !usable.length ? (
        <div className="flex h-48 flex-col items-center justify-center rounded-lg border border-dashed border-border/60 bg-bg/40 text-center text-sm text-text-tertiary">
          <div className="font-semibold text-text-secondary">
            No price history indexed yet
          </div>
          <div className="mt-1 text-xs">
            Snapshots begin on our first daily sync — the chart populates as data
            accumulates.
          </div>
        </div>
      ) : (
        <>
          <Sparkline points={usable} range={range} />
          {stats && (
            <div className="mt-4 grid grid-cols-2 gap-4 text-xs sm:grid-cols-4">
              <Stat label="Latest" value={fmtPrice(stats.last)} />
              <Stat
                label="Change"
                value={`${stats.changePct >= 0 ? "+" : ""}${stats.changePct.toFixed(1)}%`}
                color={stats.changePct >= 0 ? "text-accent-green" : "text-accent-red"}
              />
              <Stat label={`${range}d Low`} value={fmtPrice(stats.min)} />
              <Stat label={`${range}d High`} value={fmtPrice(stats.max)} />
            </div>
          )}
        </>
      )}
    </section>
  );
}

function Stat({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-text-tertiary">
        {label}
      </div>
      <div className={"mt-0.5 font-bold text-text-primary " + (color ?? "")}>
        {value}
      </div>
    </div>
  );
}

function Sparkline({
  points,
  range,
}: {
  points: (ProductHistoryPoint & { market: number })[];
  range: Range;
}) {
  const width = 800;
  const height = 220;
  const paddingL = 44;
  const paddingR = 12;
  const paddingT = 12;
  const paddingB = 24;

  const minY = Math.min(...points.map((p) => p.market));
  const maxY = Math.max(...points.map((p) => p.market));
  const spread = Math.max(0.001, maxY - minY);
  const padSpread = spread * 0.12; // 12% headroom above / below
  const y0 = minY - padSpread;
  const y1 = maxY + padSpread;

  const first = points[0];
  const last = points[points.length - 1];
  const startDate = new Date(first.date + "T00:00:00Z").getTime();
  const endDate = new Date(last.date + "T00:00:00Z").getTime();
  const dateSpan = Math.max(1, endDate - startDate);

  const x = (iso: string) => {
    const t = new Date(iso + "T00:00:00Z").getTime();
    return (
      paddingL + ((t - startDate) / dateSpan) * (width - paddingL - paddingR)
    );
  };
  const y = (v: number) => {
    const usable = height - paddingT - paddingB;
    return paddingT + usable - ((v - y0) / (y1 - y0)) * usable;
  };

  const path = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${x(p.date).toFixed(2)} ${y(p.market).toFixed(2)}`)
    .join(" ");
  const areaPath =
    path +
    ` L ${x(last.date).toFixed(2)} ${(height - paddingB).toFixed(2)}` +
    ` L ${x(first.date).toFixed(2)} ${(height - paddingB).toFixed(2)} Z`;

  const ticks = [0.25, 0.5, 0.75].map((frac) => y0 + (y1 - y0) * frac).concat([y0, y1]);
  ticks.sort((a, b) => b - a);

  const dateTicks: string[] = [];
  const desired = 4;
  const step = Math.max(1, Math.floor(points.length / (desired + 1)));
  for (let i = step; i < points.length - step / 2; i += step) {
    dateTicks.push(points[i].date);
  }

  return (
    <div className="overflow-x-auto">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        className="h-56 w-full"
        role="img"
        aria-label={`Price history over the last ${range} days`}
      >
        {/* horizontal grid */}
        {ticks.map((t, i) => (
          <g key={i}>
            <line
              x1={paddingL}
              x2={width - paddingR}
              y1={y(t)}
              y2={y(t)}
              stroke="currentColor"
              strokeWidth={0.5}
              className="text-border/60"
            />
            <text
              x={paddingL - 6}
              y={y(t) + 3}
              textAnchor="end"
              className="fill-current text-[9px] font-mono text-text-tertiary"
            >
              {fmtPrice(t)}
            </text>
          </g>
        ))}

        {/* area fill */}
        <path
          d={areaPath}
          className="fill-accent-yellow"
          opacity={0.1}
        />
        {/* line */}
        <path
          d={path}
          fill="none"
          className="stroke-accent-yellow"
          strokeWidth={1.6}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* dots at ends */}
        <circle cx={x(first.date)} cy={y(first.market)} r={2.5} className="fill-accent-yellow" />
        <circle cx={x(last.date)} cy={y(last.market)} r={2.5} className="fill-accent-yellow" />

        {/* x-axis dates */}
        {dateTicks.map((d) => (
          <text
            key={d}
            x={x(d)}
            y={height - paddingB + 14}
            textAnchor="middle"
            className="fill-current text-[9px] font-mono text-text-tertiary"
          >
            {fmtDate(d)}
          </text>
        ))}
      </svg>
    </div>
  );
}
