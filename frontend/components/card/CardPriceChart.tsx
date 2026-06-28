"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { getCardHistory, type CardHistory, type CardHistoryPoint } from "@/lib/api";

import { MascotMark } from "./Mascot";

type TabKey = "tcg" | "ebay" | "combined";
type RangeKey = "7d" | "30d" | "90d" | "1y";

interface PricePoint {
  date: string;
  low: number;
  mid: number;
  high: number;
  sales: number | null;
}

const RANGE_META: Record<
  RangeKey,
  { label: string; days: number; gapDays: number; bucket: "daily" | "weekly" | "monthly" }
> = {
  "7d": { label: "7D", days: 7, gapDays: 2, bucket: "daily" },
  // gapDays must clear the actual sample spacing or the line shatters
  // into one-point "segments" that don't render. Weekly backfill rows
  // sit 7 days apart, so 30D needs >= 8 to connect them; daily sync
  // will overwrite with denser data over time.
  "30d": { label: "30D", days: 30, gapDays: 8, bucket: "daily" },
  "90d": { label: "90D", days: 90, gapDays: 10, bucket: "weekly" },
  "1y": { label: "1Y", days: 365, gapDays: 40, bucket: "monthly" },
};

const VIEW_W = 800;
const VIEW_H = 320;
const M = { top: 16, right: 24, bottom: 44, left: 52 };
const PLOT_W = VIEW_W - M.left - M.right;
const PLOT_H = VIEW_H - M.top - M.bottom;

// ────────────────────────────── helpers ──────────────────────────────

function parseDate(dateStr: string): Date {
  const [y, m, d] = dateStr.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function fmtDateKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function fmtShort(dateStr: string): string {
  return parseDate(dateStr).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function fmtMonth(dateStr: string): string {
  return parseDate(dateStr).toLocaleDateString("en-US", { month: "short", year: "2-digit" });
}

function fmtMoney(v: number | null): string {
  if (v == null || Number.isNaN(v)) return "—";
  if (v >= 1000) return `$${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
  return `$${v.toFixed(2)}`;
}

function medianOf(arr: number[]): number {
  const sorted = [...arr].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

// ────────────────────────────── adapter ──────────────────────────────

/**
 * Convert our API's keyed series (`Record<string, CardHistoryPoint[]>`) into
 * two per-source arrays. Keys look like `<source>:<variant>` — e.g.
 * `tcgplayer:normal`, `tcgplayer:holofoil`, `tcgplayer:reverseHolofoil`,
 * `ebay:active`. We collapse all `tcgplayer:*` variants per date by picking
 * the entry with the highest `market` (the same heuristic the snapshot uses
 * for the denormalized Card.market_price_usd).
 */
function adaptSeries(history: CardHistory | null): {
  tcg: PricePoint[];
  ebay: PricePoint[];
} {
  if (!history) return { tcg: [], ebay: [] };

  const tcgByDate = new Map<string, PricePoint>();
  const ebayByDate = new Map<string, PricePoint>();

  const toPoint = (p: CardHistoryPoint): PricePoint | null => {
    if (p.market == null) return null;
    return {
      date: p.date,
      low: typeof p.low === "number" ? p.low : p.market,
      mid: typeof p.mid === "number" ? p.mid : p.market,
      high: typeof p.high === "number" ? p.high : p.market,
      sales: typeof p.sales === "number" ? p.sales : null,
    };
  };

  for (const [key, points] of Object.entries(history.series)) {
    const source = key.split(":")[0];
    const bucket = source === "tcgplayer" ? tcgByDate : source === "ebay" ? ebayByDate : null;
    if (!bucket) continue;
    for (const raw of points) {
      const p = toPoint(raw);
      if (!p) continue;
      const prev = bucket.get(p.date);
      if (!prev || p.mid > prev.mid) bucket.set(p.date, p);
    }
  }

  const byDateSorted = (m: Map<string, PricePoint>) =>
    [...m.values()].sort((a, b) => parseDate(a.date).getTime() - parseDate(b.date).getTime());

  return { tcg: byDateSorted(tcgByDate), ebay: byDateSorted(ebayByDate) };
}

// ────────────────────────────── range processing ──────────────────────────────

function combinedPoints(tcg: PricePoint[], ebay: PricePoint[]): PricePoint[] {
  const map = new Map<string, { t?: PricePoint; e?: PricePoint }>();
  for (const p of tcg) map.set(p.date, { ...map.get(p.date), t: p });
  for (const p of ebay) map.set(p.date, { ...map.get(p.date), e: p });

  const out: PricePoint[] = [];
  for (const [date, { t, e }] of map) {
    if (!t && !e) continue;
    const lows = [t?.low, e?.low].filter((v): v is number => typeof v === "number");
    const mids = [t?.mid, e?.mid].filter((v): v is number => typeof v === "number");
    const highs = [t?.high, e?.high].filter((v): v is number => typeof v === "number");
    const sales = (t?.sales ?? 0) + (e?.sales ?? 0);
    out.push({
      date,
      low: lows.length ? Math.min(...lows) : 0,
      mid: mids.length ? mids.reduce((a, b) => a + b, 0) / mids.length : 0,
      high: highs.length ? Math.max(...highs) : 0,
      sales: sales > 0 ? sales : null,
    });
  }
  return out.sort((a, b) => parseDate(a.date).getTime() - parseDate(b.date).getTime());
}

function bucketize(points: PricePoint[], bucket: "daily" | "weekly" | "monthly"): PricePoint[] {
  if (bucket === "daily") return points;
  const groups = new Map<string, PricePoint[]>();
  for (const p of points) {
    const d = parseDate(p.date);
    let key: string;
    if (bucket === "weekly") {
      const wk = new Date(d);
      wk.setDate(d.getDate() - d.getDay());
      key = fmtDateKey(wk);
    } else {
      key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
    }
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(p);
  }
  return [...groups.entries()]
    .map(([date, pts]) => ({
      date,
      low: medianOf(pts.map((p) => p.low)),
      mid: medianOf(pts.map((p) => p.mid)),
      high: medianOf(pts.map((p) => p.high)),
      sales: pts.reduce((s, p) => s + (p.sales ?? 0), 0) || null,
    }))
    .sort((a, b) => parseDate(a.date).getTime() - parseDate(b.date).getTime());
}

function sliceRange(points: PricePoint[], days: number): PricePoint[] {
  if (!points.length) return [];
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const start = new Date(today);
  start.setDate(today.getDate() - (days - 1));
  return points.filter((p) => {
    const d = parseDate(p.date);
    return d >= start && d <= today;
  });
}

function getSegments(points: PricePoint[], gapDays: number): PricePoint[][] {
  if (!points.length) return [];
  const segments: PricePoint[][] = [];
  let cur = [points[0]];
  for (let i = 1; i < points.length; i++) {
    const prev = parseDate(points[i - 1].date);
    const curr = parseDate(points[i].date);
    const diff = (curr.getTime() - prev.getTime()) / 86_400_000;
    if (diff > gapDays) {
      segments.push(cur);
      cur = [points[i]];
    } else {
      cur.push(points[i]);
    }
  }
  segments.push(cur);
  return segments;
}

/**
 * Vertical year-boundary markers — drawn at each Jan 1 falling inside
 * the visible window. The x-axis tick labels encode the year as a
 * 2-digit suffix ("DEC 25" → "JAN 26") which is easy to miss; an
 * explicit line + year label makes the crossover unmistakable on the
 * 90D and 1Y views. Returns empty for 7D / 30D unless the window
 * happens to straddle Jan 1.
 */
function getYearBoundaries(range: RangeKey): { dateStr: string; year: number }[] {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const start = new Date(today);
  start.setDate(today.getDate() - (RANGE_META[range].days - 1));

  const out: { dateStr: string; year: number }[] = [];
  // Iterate Jan 1 of (startYear+1) forward — Jan 1 of startYear can't
  // fall inside the window unless start IS Jan 1, which we'd skip
  // anyway (no transition to mark at the very left edge).
  for (let year = start.getFullYear() + 1; year <= today.getFullYear(); year++) {
    const boundary = new Date(year, 0, 1);
    boundary.setHours(0, 0, 0, 0);
    if (boundary >= start && boundary <= today) {
      out.push({ dateStr: fmtDateKey(boundary), year });
    }
  }
  return out;
}

function getTicks(range: RangeKey): string[] {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const start = new Date(today);
  start.setDate(today.getDate() - (RANGE_META[range].days - 1));
  const ticks: string[] = [];

  if (range === "7d") {
    for (let i = 0; i < 7; i++) {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      ticks.push(fmtDateKey(d));
    }
  } else if (range === "30d") {
    for (let i = 0; i <= 30; i += 5) {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      if (d > today) break;
      ticks.push(fmtDateKey(d));
    }
    if (ticks[ticks.length - 1] !== fmtDateKey(today)) ticks.push(fmtDateKey(today));
  } else if (range === "90d") {
    for (let i = 0; i <= 90; i += 14) {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      if (d > today) break;
      ticks.push(fmtDateKey(d));
    }
    if (ticks[ticks.length - 1] !== fmtDateKey(today)) ticks.push(fmtDateKey(today));
  } else {
    for (let i = 0; i < 12; i++) {
      const d = new Date(start);
      d.setMonth(start.getMonth() + i);
      if (d > today) break;
      ticks.push(fmtDateKey(d));
    }
    if (ticks[ticks.length - 1] !== fmtDateKey(today)) ticks.push(fmtDateKey(today));
  }
  return ticks;
}

// ────────────────────────────── component ──────────────────────────────

interface Props {
  cardId: string;
  isOnFire?: boolean;
}

export function CardPriceChart({ cardId, isOnFire = false }: Props) {
  const [tab, setTab] = useState<TabKey>("combined");
  const [range, setRange] = useState<RangeKey>("30d");
  const [history, setHistory] = useState<CardHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [hovered, setHovered] = useState<PricePoint | null>(null);
  const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // One fetch covers all four ranges — slice client-side.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getCardHistory(cardId, { days: 365 })
      .then((h) => {
        if (!cancelled) setHistory(h);
      })
      .catch(() => {
        if (!cancelled) setHistory(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [cardId]);

  const { tcg, ebay } = useMemo(() => adaptSeries(history), [history]);

  const data = useMemo(() => {
    const base =
      tab === "tcg"
        ? tcg
        : tab === "ebay"
          ? ebay
          : combinedPoints(tcg, ebay);
    const meta = RANGE_META[range];
    return bucketize(sliceRange(base, meta.days), meta.bucket);
  }, [tcg, ebay, tab, range]);

  const segments = useMemo(() => getSegments(data, RANGE_META[range].gapDays), [data, range]);

  // Quick stats summary for the selected range. Median (mid) is the
  // signal collectors care about; low/high feed the chart band already.
  // Volatility = coefficient of variation (stddev / mean) — a single
  // adjective is easier to read at a glance than a raw number.
  const rangeStats = useMemo(() => {
    const mids = data.map((p) => p.mid).filter((v) => v > 0);
    if (mids.length < 2) return null;
    const min = Math.min(...mids);
    const max = Math.max(...mids);
    const avg = mids.reduce((a, b) => a + b, 0) / mids.length;
    const variance =
      mids.reduce((sum, v) => sum + (v - avg) ** 2, 0) / mids.length;
    const stddev = Math.sqrt(variance);
    const cv = avg > 0 ? stddev / avg : 0;
    const volatility: "low" | "moderate" | "high" =
      cv < 0.1 ? "low" : cv < 0.25 ? "moderate" : "high";
    return { min, max, avg, volatility, points: mids.length };
  }, [data]);

  const ticks = useMemo(() => getTicks(range), [range]);
  const yearBoundaries = useMemo(() => getYearBoundaries(range), [range]);

  const { xScale, yScale, minVal, maxVal } = useMemo(() => {
    if (data.length === 0) {
      return { xScale: () => 0, yScale: () => 0, minVal: 0, maxVal: 0 };
    }
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const start = new Date(today);
    start.setDate(today.getDate() - (RANGE_META[range].days - 1));

    const all = data.flatMap((p) => [p.low, p.high]).filter((n) => n > 0);
    let min = Math.min(...all);
    let max = Math.max(...all);
    if (min === max) {
      min *= 0.9;
      max *= 1.1;
    }
    const pad = (max - min) * 0.08;
    min = Math.max(0, min - pad);
    max += pad;

    const xScale = (dateStr: string) => {
      const t = (parseDate(dateStr).getTime() - start.getTime()) / (today.getTime() - start.getTime());
      return M.left + t * PLOT_W;
    };
    const yScale = (val: number) => {
      const t = (val - min) / (max - min || 1);
      return M.top + PLOT_H - t * PLOT_H;
    };
    return { xScale, yScale, minVal: min, maxVal: max };
  }, [data, range]);

  const handleMove = useCallback(
    (clientX: number, clientY: number) => {
      if (!containerRef.current || data.length === 0) return;
      const rect = containerRef.current.getBoundingClientRect();
      const x = clientX - rect.left;
      const y = clientY - rect.top;
      const svgX = x * (VIEW_W / rect.width);

      if (svgX < M.left || svgX > M.left + PLOT_W) {
        setHovered(null);
        return;
      }
      let nearest: PricePoint | null = null;
      let nearestDist = Infinity;
      for (const p of data) {
        const dist = Math.abs(xScale(p.date) - svgX);
        if (dist < nearestDist) {
          nearestDist = dist;
          nearest = p;
        }
      }
      if (nearest && nearestDist < (PLOT_W / Math.max(data.length, 1)) * 1.5) {
        setHovered(nearest);
        setMousePos({ x, y });
      } else {
        setHovered(null);
      }
    },
    [data, xScale],
  );

  const onMouseMove = useCallback(
    (e: React.MouseEvent) => handleMove(e.clientX, e.clientY),
    [handleMove],
  );
  const onTouchMove = useCallback(
    (e: React.TouchEvent) => {
      const t = e.touches[0];
      if (t) {
        e.preventDefault();
        handleMove(t.clientX, t.clientY);
      }
    },
    [handleMove],
  );
  const onLeave = useCallback(() => setHovered(null), []);

  const renderBand = () =>
    segments.map((seg, i) => {
      const top = seg
        .map((p, idx) => `${idx === 0 ? "M" : "L"} ${xScale(p.date)} ${yScale(p.high)}`)
        .join(" ");
      const bottom = [...seg]
        .reverse()
        .map((p) => `L ${xScale(p.date)} ${yScale(p.low)}`)
        .join(" ");
      return (
        <path
          key={`band-${i}`}
          d={`${top} ${bottom} Z`}
          className="fill-teal-500/[0.10] dark:fill-teal-400/[0.12]"
          stroke="none"
        />
      );
    });

  const renderLine = (key: "low" | "mid" | "high") =>
    segments.map((seg, i) => {
      const d = seg
        .map((p, idx) => `${idx === 0 ? "M" : "L"} ${xScale(p.date)} ${yScale(p[key])}`)
        .join(" ");
      const isMid = key === "mid";
      return (
        <path
          key={`${key}-${i}`}
          d={d}
          fill="none"
          className={
            isMid
              ? "stroke-teal-600 dark:stroke-teal-300"
              : "stroke-teal-400/60 dark:stroke-teal-500/50"
          }
          strokeWidth={isMid ? 2.5 : 1.25}
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      );
    });

  const hoverX = hovered ? xScale(hovered.date) : null;
  const tooltipFlipX = mousePos && containerRef.current
    ? mousePos.x > containerRef.current.clientWidth / 2
    : false;
  const tooltipFlipY = mousePos ? mousePos.y < 120 : false;

  return (
    <div className="rounded-card border border-border bg-bg-surface p-4 md:p-5">
      {/* Controls */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-4">
        <div className="flex items-center gap-1 rounded-full bg-bg p-1 border border-border w-fit">
          {(["tcg", "ebay", "combined"] as TabKey[]).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={
                "px-3 py-1.5 rounded-full text-xs font-semibold transition-colors " +
                (tab === t
                  ? "bg-bg-elevated text-text-primary shadow-sm"
                  : "text-text-tertiary hover:text-text-secondary")
              }
            >
              {t === "tcg" ? "TCGplayer" : t === "ebay" ? "eBay" : "Combined"}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1">
          {(["7d", "30d", "90d", "1y"] as RangeKey[]).map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => setRange(r)}
              className={
                "px-2.5 py-1 rounded-full text-xs font-mono font-semibold transition-colors " +
                (range === r
                  ? "bg-accent-yellow text-gray-900"
                  : "text-text-tertiary hover:text-text-secondary hover:bg-bg")
              }
            >
              {RANGE_META[r].label}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      <div
        ref={containerRef}
        className="relative"
        onMouseMove={onMouseMove}
        onMouseLeave={onLeave}
        onTouchMove={onTouchMove}
        onTouchEnd={onLeave}
      >
        {isOnFire && !loading && data.length > 1 && (
          <div className="pointer-events-none absolute right-2 top-2 z-10 flex items-center gap-2">
            <div className="rounded-btn border border-border bg-bg-surface px-2.5 py-1.5 text-xs font-medium text-text-primary shadow-sm">
              This card is on fire lately! 🔥
            </div>
            <MascotMark className="h-7 w-7" />
          </div>
        )}

        <svg
          viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
          className="w-full h-auto select-none"
          style={{ touchAction: "none" }}
        >
          {/* Y grid + labels */}
          {Array.from({ length: 5 }).map((_, i) => {
            const y = M.top + (PLOT_H / 4) * i;
            const val = maxVal - ((maxVal - minVal) / 4) * i;
            return (
              <g key={i}>
                <line
                  x1={M.left}
                  y1={y}
                  x2={M.left + PLOT_W}
                  y2={y}
                  className="stroke-border"
                  strokeWidth={1}
                  strokeOpacity={0.5}
                />
                <text
                  x={M.left - 8}
                  y={y + 3}
                  textAnchor="end"
                  className="fill-text-tertiary text-[10px] font-mono"
                >
                  {fmtMoney(Math.round(val))}
                </text>
              </g>
            );
          })}

          {/* X axis line */}
          <line
            x1={M.left}
            y1={M.top + PLOT_H}
            x2={M.left + PLOT_W}
            y2={M.top + PLOT_H}
            className="stroke-border"
            strokeWidth={1}
          />

          {/* Year boundary markers — vertical dashed line + year label
              above the plot. Only renders when the visible window
              actually crosses Jan 1 (always on 1Y, sometimes 90D, rarely
              30D). Drawn before X ticks so tick labels can sit on top
              of the marker line. */}
          {yearBoundaries.map((b) => {
            const x = xScale(b.dateStr);
            return (
              <g key={`yb-${b.year}`}>
                <line
                  x1={x}
                  y1={M.top}
                  x2={x}
                  y2={M.top + PLOT_H}
                  className="stroke-text-tertiary"
                  strokeOpacity={0.35}
                  strokeWidth={1}
                  strokeDasharray="3 4"
                />
                <text
                  x={x}
                  y={M.top - 4}
                  textAnchor="middle"
                  className="fill-text-tertiary text-[9px] font-mono font-semibold uppercase tracking-wider"
                >
                  {b.year}
                </text>
              </g>
            );
          })}

          {/* X ticks */}
          {ticks.map((t, i) => {
            const x = xScale(t);
            return (
              <g key={i}>
                <line
                  x1={x}
                  y1={M.top + PLOT_H}
                  x2={x}
                  y2={M.top + PLOT_H + 4}
                  className="stroke-border"
                  strokeWidth={1}
                />
                <text
                  x={x}
                  y={M.top + PLOT_H + 18}
                  textAnchor="middle"
                  className="fill-text-tertiary text-[10px] font-mono uppercase"
                >
                  {range === "1y" ? fmtMonth(t) : fmtShort(t)}
                </text>
              </g>
            );
          })}

          {/* Data — band, low/high lines, median line */}
          {renderBand()}
          {renderLine("low")}
          {renderLine("high")}
          {renderLine("mid")}

          {/* Hover guideline */}
          {hoverX !== null && (
            <line
              x1={hoverX}
              y1={M.top}
              x2={hoverX}
              y2={M.top + PLOT_H}
              className="stroke-text-tertiary"
              strokeWidth={1}
              strokeDasharray="4 4"
            />
          )}

          {/* Hover dots */}
          {hovered && hoverX !== null && (
            <g>
              <circle
                cx={hoverX}
                cy={yScale(hovered.mid)}
                r={5}
                className="fill-teal-500 dark:fill-teal-300 stroke-bg-surface"
                strokeWidth={2}
              />
              <circle
                cx={hoverX}
                cy={yScale(hovered.low)}
                r={3}
                className="fill-teal-400/70 dark:fill-teal-500/70"
              />
              <circle
                cx={hoverX}
                cy={yScale(hovered.high)}
                r={3}
                className="fill-teal-400/70 dark:fill-teal-500/70"
              />
            </g>
          )}
        </svg>

        {/* Tooltip — follows cursor, auto-flips at edges */}
        {hovered && mousePos && (
          <div
            className="absolute pointer-events-none z-20 rounded-card border border-border bg-bg-surface/95 backdrop-blur-sm p-3 shadow-lg min-w-[160px]"
            style={{
              left: mousePos.x,
              top: mousePos.y,
              transform: `translate(${tooltipFlipX ? "-110%" : "10%"}, ${tooltipFlipY ? "10%" : "-110%"})`,
            }}
          >
            <div className="font-mono text-[10px] uppercase tracking-wider text-text-tertiary mb-1">
              {fmtShort(hovered.date)}
            </div>
            <div className="font-mono text-lg font-bold text-text-primary mb-1">
              {fmtMoney(hovered.mid)}
            </div>
            <div className="flex items-center justify-between gap-3 text-[11px] font-mono text-text-tertiary">
              <span>L · {fmtMoney(hovered.low)}</span>
              <span>H · {fmtMoney(hovered.high)}</span>
            </div>
            {hovered.sales != null && hovered.sales > 0 && (
              <div className="mt-2 pt-2 border-t border-border text-[10px] text-text-tertiary">
                {hovered.sales.toLocaleString()} listings
              </div>
            )}
          </div>
        )}

        {/* Loading / empty overlays */}
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center text-sm text-text-tertiary">
            Loading…
          </div>
        )}
        {!loading && data.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-sm text-text-tertiary">
            No price history for this range
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="mt-3 flex flex-wrap items-center gap-4 text-[11px] text-text-tertiary">
        <span className="flex items-center gap-1.5">
          <span className="h-[2px] w-4 rounded bg-teal-600 dark:bg-teal-300" />
          Median
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-3 rounded-sm bg-teal-500/15 ring-1 ring-teal-500/40 dark:ring-teal-400/40" />
          Low–High range
        </span>
      </div>

      {/* Quick range stats — numeric companion to the chart's visual band */}
      {rangeStats && (
        <p className="mt-2 text-[11px] font-mono text-text-tertiary">
          <span className="text-text-secondary font-semibold">
            {RANGE_META[range].label}
          </span>
          {" · min "}
          <span className="text-text-primary">{fmtMoney(rangeStats.min)}</span>
          {" · avg "}
          <span className="text-text-primary">{fmtMoney(rangeStats.avg)}</span>
          {" · max "}
          <span className="text-text-primary">{fmtMoney(rangeStats.max)}</span>
          {" · volatility "}
          <span
            className={
              rangeStats.volatility === "high"
                ? "text-accent-red font-semibold"
                : rangeStats.volatility === "moderate"
                  ? "text-accent-yellow font-semibold"
                  : "text-accent-green font-semibold"
            }
          >
            {rangeStats.volatility}
          </span>
        </p>
      )}
    </div>
  );
}
