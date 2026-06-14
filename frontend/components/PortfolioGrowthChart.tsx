"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowDownRight, ArrowUpRight, TrendingUp } from "lucide-react";

import {
  getPortfolioHistory,
  type PortfolioHistory,
  type PortfolioPoint,
} from "@/lib/auth";
import { cn } from "@/lib/utils";

const PERIODS = [
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
  { label: "1y", days: 365 },
] as const;

export function PortfolioGrowthChart() {
  const [periodDays, setPeriodDays] = useState(30);
  const [data, setData] = useState<PortfolioHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    getPortfolioHistory(periodDays)
      .then((r) => {
        if (!cancelled) setData(r);
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
  }, [periodDays]);

  const points = data?.points ?? [];
  const hasEnoughData = points.length >= 2;

  return (
    <div className="rounded-card bg-bg-surface border border-border p-5">
      <div className="mb-3 flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h2 className="text-sm font-mono uppercase tracking-wider text-text-tertiary">
            Portfolio growth
          </h2>
          {data && hasEnoughData && (
            <DeltaBadge
              delta_usd={data.delta_usd}
              delta_pct={data.delta_pct}
              periodDays={periodDays}
            />
          )}
        </div>
        <div className="inline-flex rounded-full border border-border bg-bg p-1">
          {PERIODS.map((p) => (
            <button
              key={p.days}
              onClick={() => setPeriodDays(p.days)}
              className={cn(
                "rounded-full px-2.5 py-1 text-[11px] font-semibold transition-colors",
                periodDays === p.days
                  ? "bg-accent-yellow text-gray-900"
                  : "text-text-secondary hover:text-text-primary",
              )}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {err && (
        <div className="h-44 flex items-center justify-center text-xs text-accent-red">
          {err}
        </div>
      )}

      {loading && !data && (
        <div className="h-44 rounded-md bg-bg/40 animate-pulse" />
      )}

      {!loading && !err && !hasEnoughData && (
        <div className="h-44 rounded-md border-2 border-dashed border-border bg-bg/40 flex flex-col items-center justify-center text-center px-4">
          <TrendingUp className="h-6 w-6 text-text-tertiary mb-2" />
          <p className="text-sm font-medium text-text-secondary">
            {points.length === 0
              ? "Tracking starts as snapshots accumulate"
              : "One snapshot so far — need 2+ for a chart"}
          </p>
          <p className="mt-1 text-xs text-text-tertiary">
            Daily cron at 05:00 UTC. Chart fills in over the next few days 🐲
          </p>
        </div>
      )}

      {!loading && hasEnoughData && (
        <GrowthSVG points={points} />
      )}
    </div>
  );
}

function DeltaBadge({
  delta_usd,
  delta_pct,
  periodDays,
}: {
  delta_usd: number;
  delta_pct: number;
  periodDays: number;
}) {
  const up = delta_usd >= 0;
  const periodLabel =
    PERIODS.find((p) => p.days === periodDays)?.label ?? `${periodDays}d`;
  return (
    <div
      className={cn(
        "mt-1 inline-flex items-center gap-1 text-xs font-mono",
        up ? "text-accent-green" : "text-accent-red",
      )}
    >
      {up ? (
        <ArrowUpRight className="h-3.5 w-3.5" />
      ) : (
        <ArrowDownRight className="h-3.5 w-3.5" />
      )}
      <span className="font-bold">
        {up ? "+" : ""}
        ${delta_usd.toFixed(2)}
      </span>
      <span className="opacity-70">
        ({up ? "+" : ""}
        {delta_pct.toFixed(1)}%)
      </span>
      <span className="text-text-tertiary opacity-60">· {periodLabel}</span>
    </div>
  );
}

function GrowthSVG({ points }: { points: PortfolioPoint[] }) {
  // Layout
  const W = 600;
  const H = 176;
  const padX = 12;
  const padY = 16;
  const innerW = W - padX * 2;
  const innerH = H - padY * 2;

  const { coords, minV, maxV, isFlat } = useMemo(() => {
    const values = points.map((p) => p.value);
    const minV = Math.min(...values);
    const maxV = Math.max(...values);
    const range = maxV - minV;
    const isFlat = range < 0.01;
    // Add 5% padding above/below for breathing room, unless flat.
    const lo = isFlat ? minV - 1 : minV - range * 0.08;
    const hi = isFlat ? maxV + 1 : maxV + range * 0.12;
    const span = hi - lo || 1;

    const coords = points.map((p, i) => {
      const x =
        padX + (points.length === 1 ? innerW / 2 : (i * innerW) / (points.length - 1));
      const y = padY + innerH - ((p.value - lo) / span) * innerH;
      return { x, y, p };
    });
    return { coords, minV, maxV, isFlat };
  }, [points]);

  const up = points[points.length - 1].value >= points[0].value;
  const strokeColor = up ? "rgb(34 197 94)" : "rgb(239 68 68)";
  const fillColor = up
    ? "rgba(34, 197, 94, 0.12)"
    : "rgba(239, 68, 68, 0.10)";

  const lineD = coords.map((c, i) => `${i === 0 ? "M" : "L"}${c.x},${c.y}`).join(" ");
  const areaD =
    `${lineD} L${coords[coords.length - 1].x},${padY + innerH} L${coords[0].x},${padY + innerH} Z`;

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-44"
        preserveAspectRatio="none"
      >
        {/* Subtle grid baseline */}
        <line
          x1={padX}
          x2={W - padX}
          y1={padY + innerH}
          y2={padY + innerH}
          stroke="currentColor"
          strokeOpacity={0.08}
          strokeWidth={1}
        />
        {/* Area fill */}
        <path d={areaD} fill={fillColor} />
        {/* Line */}
        <path
          d={lineD}
          fill="none"
          stroke={strokeColor}
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* End-point dot */}
        <circle
          cx={coords[coords.length - 1].x}
          cy={coords[coords.length - 1].y}
          r={4}
          fill={strokeColor}
        />
        <circle
          cx={coords[coords.length - 1].x}
          cy={coords[coords.length - 1].y}
          r={8}
          fill={strokeColor}
          opacity={0.2}
        />
      </svg>

      {/* Value labels — first / latest */}
      <div className="mt-2 flex items-center justify-between text-[11px] font-mono text-text-tertiary">
        <span>
          {points[0].date}: <span className="text-text-secondary">${points[0].value.toFixed(2)}</span>
        </span>
        {!isFlat && (
          <span className="text-text-tertiary">
            range ${minV.toFixed(0)} – ${maxV.toFixed(0)}
          </span>
        )}
        <span>
          <span className="text-text-secondary">${points[points.length - 1].value.toFixed(2)}</span> :{points[points.length - 1].date}
        </span>
      </div>
    </div>
  );
}
