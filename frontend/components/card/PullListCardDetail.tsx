"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useTheme } from "next-themes";
import {
  ArrowDownRight,
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Loader2,
  Moon,
  Plus,
  Search,
  ShoppingCart,
  Sparkles,
  Sun,
  Tag,
} from "lucide-react";

import { LiveListings } from "@/components/card/LiveListings";
import { OwnedToggle } from "@/components/OwnedToggle";
import { getCardHistory, type Card, type CardHistory, type CardNeighbors } from "@/lib/api";
import { cn } from "@/lib/utils";

/* ============================================================
   Brand helpers — palette tuned for white light mode
   ============================================================ */
const surface =
  "rounded-xl border border-gray-200 bg-white dark:border-[#2D3543] dark:bg-[#1A1F29]";
const muted = "text-gray-500 dark:text-zinc-400";
const faint = "text-gray-400 dark:text-zinc-500";
const heading = "text-gray-900 dark:text-zinc-50";

function fmtUSD(v: number | null | undefined) {
  if (v == null) return "—";
  return `$${Number(v).toFixed(2)}`;
}
function fmtEUR(v: number | null | undefined) {
  if (v == null) return "—";
  return `€${Number(v).toFixed(2)}`;
}

/* ============================================================
   Mascot mark
   ============================================================ */
function MascotMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "relative inline-block overflow-hidden rounded-full ring-2 ring-amber-300/60",
        className,
      )}
    >
      <Image
        src="/pullist-mascot.png"
        alt="PullList mascot"
        fill
        className="object-cover"
        sizes="80px"
        unoptimized
      />
    </span>
  );
}

/* ============================================================
   Theme toggle
   ============================================================ */
function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const isDark = resolvedTheme === "dark";
  return (
    <button
      aria-label="Toggle theme"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-gray-200 bg-white text-gray-600 transition-colors hover:bg-gray-50 dark:border-[#2D3543] dark:bg-[#1A1F29] dark:text-zinc-300 dark:hover:bg-[#222834]"
    >
      {mounted && isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}

/* ============================================================
   Source badge
   ============================================================ */
function SourceBadge({ source }: { source: string }) {
  const styles: Record<string, string> = {
    TCGplayer:
      "bg-amber-100 text-amber-800 ring-amber-300 dark:bg-amber-400/15 dark:text-amber-300 dark:ring-amber-400/30",
    eBay: "bg-teal-100 text-teal-800 ring-teal-300 dark:bg-teal-400/15 dark:text-teal-300 dark:ring-teal-400/30",
    Cardmarket:
      "bg-gray-100 text-gray-700 ring-gray-300 dark:bg-zinc-700/30 dark:text-zinc-300 dark:ring-zinc-600",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-bold ring-1",
        styles[source] ?? styles.Cardmarket,
      )}
    >
      {source}
    </span>
  );
}

/* ============================================================
   Delta pill
   ============================================================ */
function Delta({ value }: { value: number | null }) {
  if (value == null) return <span className={cn("text-xs", faint)}>—</span>;
  const up = value >= 0;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 text-xs font-semibold",
        up
          ? "text-emerald-600 dark:text-emerald-400"
          : "text-rose-500 dark:text-rose-400",
      )}
    >
      {up ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
      {Math.abs(value).toFixed(1)}%
    </span>
  );
}

/* ============================================================
   Cheapest hero
   ============================================================ */
type CheapestData = {
  price: number;
  source: "TCGplayer" | "eBay";
  url: string;
};

function CheapestHero({ data, ownedToggle }: { data: CheapestData | null; ownedToggle: React.ReactNode }) {
  if (!data) {
    return (
      <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-5 dark:border-[#2D3543] dark:bg-[#1A1F29]">
        <p className={cn("text-sm", muted)}>No price data yet for this card.</p>
        {ownedToggle}
      </div>
    );
  }
  return (
    <div className="relative overflow-hidden rounded-xl border border-amber-300 bg-gradient-to-b from-amber-50 to-white p-5 dark:border-amber-400/30 dark:from-amber-400/10 dark:to-[#1A1F29]">
      <Sparkles className="absolute right-3 top-3 h-4 w-4 text-amber-400/70" aria-hidden />
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-amber-700 dark:text-amber-400">
          <Tag className="h-3.5 w-3.5" />
          Cheapest listing
        </span>
        <SourceBadge source={data.source} />
      </div>
      <div className="mt-3 flex items-end gap-2">
        <span className="font-mono text-5xl font-extrabold text-amber-500 dark:text-amber-400">
          {fmtUSD(data.price)}
        </span>
      </div>
      <p className={cn("mt-1 text-sm", muted)}>
        From <span className="font-medium text-gray-800 dark:text-zinc-200">{data.source}</span>
      </p>
      <div className="mt-4 flex flex-col gap-2 sm:flex-row">
        <a
          href={data.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex flex-1 items-center justify-center gap-2 rounded-full bg-gray-900 px-4 py-3 text-sm font-bold text-white transition-colors hover:bg-gray-800 dark:bg-zinc-100 dark:text-gray-900 dark:hover:bg-white"
        >
          <ShoppingCart className="h-4 w-4" />
          Buy on {data.source}
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
        {ownedToggle}
      </div>
    </div>
  );
}

/* ============================================================
   Price chart (real data)
   ============================================================ */
const RANGES = [
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
  { label: "1y", days: 365 },
] as const;

const SOURCE_COLORS = {
  tcgplayer: "#60a5fa",
  ebay: "#5BC9C2",
  cardmarket: "#FFCB05",
} as const;

function PriceChart({ cardId, height = 300, isOnFire = false }: { cardId: string; height?: number; isOnFire?: boolean }) {
  const [days, setDays] = useState(30);
  const [history, setHistory] = useState<CardHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [sourceTab, setSourceTab] = useState<"TCGplayer" | "eBay" | "Combined">("Combined");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getCardHistory(cardId, { days })
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
  }, [cardId, days]);

  const { points, sources, latest, delta, pct } = useMemo(() => {
    if (!history) return { points: [], sources: [] as string[], latest: null, delta: null, pct: null };
    const byDate: Record<string, Record<string, number>> = {};
    const srcSet = new Set<string>();
    for (const [key, series] of Object.entries(history.series)) {
      const source = key.split(":")[0];
      srcSet.add(source);
      for (const p of series) {
        if (p.market == null) continue;
        if (!byDate[p.date]) byDate[p.date] = {};
        const prev = byDate[p.date][source];
        if (prev == null || p.market > prev) byDate[p.date][source] = p.market;
      }
    }
    const dates = Object.keys(byDate).sort();
    const points = dates.map((d) => ({ date: d, ...byDate[d] }));
    const sources = Array.from(srcSet);

    // Headline based on active source tab
    const primary =
      sourceTab === "TCGplayer" ? "tcgplayer" : sourceTab === "eBay" ? "ebay" : sources[0] ?? "tcgplayer";
    const firstVal = points[0]?.[primary as keyof (typeof points)[number]];
    const latestVal = points[points.length - 1]?.[primary as keyof (typeof points)[number]];
    const latest = typeof latestVal === "number" ? latestVal : null;
    const first = typeof firstVal === "number" ? firstVal : null;
    const delta = latest != null && first != null ? latest - first : null;
    const pct = delta != null && first != null && first > 0 ? (delta / first) * 100 : null;
    return { points, sources, latest, delta, pct };
  }, [history, sourceTab]);

  // SVG chart geometry
  const W = 600;
  const PAD = 8;

  const chartLines = useMemo(() => {
    if (points.length < 1) return null;
    const showTcg = sourceTab !== "eBay" && sources.includes("tcgplayer");
    const showEbay = sourceTab !== "TCGplayer" && sources.includes("ebay");
    const visibleKeys = [showTcg && "tcgplayer", showEbay && "ebay"].filter(Boolean) as string[];
    if (!visibleKeys.length) return null;
    const allVals: number[] = [];
    for (const p of points) {
      for (const k of visibleKeys) {
        const v = (p as any)[k];
        if (typeof v === "number") allVals.push(v);
      }
    }
    if (!allVals.length) return null;
    const min = Math.min(...allVals) * 0.985;
    const max = Math.max(...allVals) * 1.015;
    const range = max - min || 1;

    const path = (key: string) => {
      const valid = points
        .map((p) => ({ d: p.date, v: (p as any)[key] }))
        .filter((p) => typeof p.v === "number");
      if (!valid.length) return "";
      return valid
        .map((p, i) => {
          const x = PAD + (i / Math.max(valid.length - 1, 1)) * (W - PAD * 2);
          const y = PAD + (1 - (p.v - min) / range) * (height - PAD * 2);
          return `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
        })
        .join(" ");
    };

    const area = (key: string) => {
      const line = path(key);
      if (!line) return "";
      return `${line} L${(W - PAD).toFixed(2)},${height} L${PAD},${height} Z`;
    };

    const primaryKey = sourceTab === "eBay" ? "ebay" : "tcgplayer";
    const primaryColor = sourceTab === "eBay" ? SOURCE_COLORS.ebay : SOURCE_COLORS.tcgplayer;

    return { showTcg, showEbay, path, area, primaryKey, primaryColor };
  }, [points, sources, sourceTab, height]);

  const up = (delta ?? 0) >= 0;

  return (
    <div className={cn(surface, "p-4")}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-gray-400 dark:text-zinc-500">
            Price history
          </p>
          <div className="mt-1 flex items-baseline gap-2">
            <span className={cn("font-mono text-2xl font-semibold", heading)}>
              {latest != null ? fmtUSD(latest) : "—"}
            </span>
            {delta != null && pct != null && points.length > 1 && (
              <span
                className={cn(
                  "text-sm font-semibold",
                  up ? "text-emerald-600 dark:text-emerald-400" : "text-rose-500 dark:text-rose-400",
                )}
              >
                {up ? "+" : ""}
                {fmtUSD(delta)} ({up ? "+" : ""}
                {pct.toFixed(1)}%)
              </span>
            )}
          </div>
        </div>
        <div className="flex gap-1 rounded-full border border-gray-200 bg-gray-50 p-1 dark:border-[#2D3543] dark:bg-[#0F1419]">
          {RANGES.map((r) => (
            <button
              key={r.days}
              onClick={() => setDays(r.days)}
              className={cn(
                "rounded-full px-2.5 py-1 text-xs font-semibold transition-colors",
                days === r.days
                  ? "bg-amber-400 text-amber-950"
                  : "text-gray-500 hover:text-gray-800 dark:text-zinc-400 dark:hover:text-zinc-200",
              )}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-3 flex gap-4 border-b border-gray-200 dark:border-[#2D3543]">
        {(["TCGplayer", "eBay", "Combined"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setSourceTab(s)}
            className={cn(
              "-mb-px border-b-2 pb-2 text-xs font-semibold transition-colors",
              sourceTab === s
                ? "border-teal-400 text-teal-600 dark:text-teal-300"
                : "border-transparent text-gray-400 hover:text-gray-700 dark:text-zinc-500 dark:hover:text-zinc-300",
            )}
          >
            {s}
          </button>
        ))}
      </div>

      <div className="relative mt-4" style={{ height }}>
        {isOnFire && !loading && points.length > 1 && (
          <div className="pointer-events-none absolute right-2 top-2 z-10 flex items-center gap-2">
            <div className="rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs font-medium text-gray-800 shadow-md dark:border-[#2D3543] dark:bg-[#1A1F29] dark:text-zinc-100">
              This card is on fire lately! 🔥
            </div>
            <MascotMark className="h-7 w-7" />
          </div>
        )}
        {loading ? (
          <div className="h-full flex items-center justify-center text-sm text-gray-400">Loading…</div>
        ) : points.length === 0 ? (
          <div className="h-full flex items-center justify-center text-sm text-gray-400">
            No price history yet. Daily snapshots will appear here.
          </div>
        ) : !chartLines ? (
          <div className="h-full flex items-center justify-center text-sm text-gray-400">
            No data for selected source.
          </div>
        ) : (
          <svg
            viewBox={`0 0 ${W} ${height}`}
            preserveAspectRatio="none"
            className="h-full w-full"
            role="img"
            aria-label="Price history line chart"
          >
            <defs>
              <linearGradient id="pl-area" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={chartLines.primaryColor} stopOpacity="0.22" />
                <stop offset="100%" stopColor={chartLines.primaryColor} stopOpacity="0" />
              </linearGradient>
            </defs>
            {[0.25, 0.5, 0.75].map((g) => (
              <line
                key={g}
                x1={0}
                x2={W}
                y1={height * g}
                y2={height * g}
                className="stroke-gray-200 dark:stroke-[#1F2937]"
                strokeWidth={1}
              />
            ))}
            <path d={chartLines.area(chartLines.primaryKey)} fill="url(#pl-area)" stroke="none" />
            {chartLines.showTcg && (
              <path
                d={chartLines.path("tcgplayer")}
                fill="none"
                stroke={SOURCE_COLORS.tcgplayer}
                strokeWidth={2.5}
                strokeLinejoin="round"
                strokeLinecap="round"
              />
            )}
            {chartLines.showEbay && (
              <path
                d={chartLines.path("ebay")}
                fill="none"
                stroke={SOURCE_COLORS.ebay}
                strokeWidth={2.5}
                strokeLinejoin="round"
                strokeLinecap="round"
              />
            )}
          </svg>
        )}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-gray-500 dark:text-zinc-400">
        {chartLines?.showTcg && (
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ background: SOURCE_COLORS.tcgplayer }} />
            TCGplayer
          </span>
        )}
        {chartLines?.showEbay && (
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ background: SOURCE_COLORS.ebay }} />
            eBay
          </span>
        )}
      </div>
    </div>
  );
}

/* ============================================================
   Secondary prices
   ============================================================ */
type SecondaryPrice = {
  source: string;
  label: string;
  value: number | null;
  currency: "USD" | "EUR";
  delta: number | null;
  spark: number[];
  sparkColor: string;
};

function Sparkline({ points, color }: { points: number[]; color: string }) {
  if (points.length < 2) {
    return (
      <svg width={70} height={24} viewBox="0 0 70 24" className="opacity-30" aria-hidden>
        {[0.25, 0.5, 0.75].map((t) => (
          <line key={t} x1={0} x2={70} y1={24 * t} y2={24 * t} stroke={color} strokeOpacity="0.25" strokeWidth={1} />
        ))}
      </svg>
    );
  }
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const w = 70;
  const h = 24;
  const d = points
    .map((v, i) => {
      const x = (i / (points.length - 1)) * w;
      const y = h - ((v - min) / range) * h;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="overflow-visible" aria-hidden>
      <path d={d} fill="none" stroke={color} strokeWidth={1.6} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

function SecondaryPrices({ items }: { items: SecondaryPrice[] }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {items.map((p) => (
        <div key={p.source + p.label} className={cn(surface, "p-4")}>
          <div className="flex items-center justify-between">
            <p className={cn("text-xs font-medium", muted)}>
              {p.source} <span className={faint}>· {p.label}</span>
            </p>
            <Delta value={p.delta} />
          </div>
          <div className="mt-2 flex items-end justify-between gap-2">
            <p className={cn("font-mono text-xl font-bold", heading)}>
              {p.value == null ? "—" : p.currency === "USD" ? fmtUSD(p.value) : fmtEUR(p.value)}
            </p>
            <Sparkline points={p.spark} color={p.sparkColor} />
          </div>
        </div>
      ))}
    </div>
  );
}

/* ============================================================
   Main component
   ============================================================ */
type Props = {
  card: Card;
  alternates: Card[];
  neighbors: CardNeighbors;
  initialEbayMedian: number | null;
  ebayDelta7d: number | null;
  tcgDelta7d: number | null;
  cardmarketDelta7d: number | null;
  ebaySpark7d: number[];
  tcgSpark7d: number[];
  cardmarketSpark7d: number[];
};

export function PullListCardDetail({
  card,
  alternates,
  neighbors,
  initialEbayMedian,
  ebayDelta7d,
  tcgDelta7d,
  cardmarketDelta7d,
  ebaySpark7d,
  tcgSpark7d,
  cardmarketSpark7d,
}: Props) {
  // Derive cheapest from available price data
  const cheapest: CheapestData | null = useMemo(() => {
    const candidates: { price: number; source: "TCGplayer" | "eBay"; url: string }[] = [];
    if (card.tcgplayer_prices) {
      for (const variant of Object.values(card.tcgplayer_prices)) {
        const low = variant?.low;
        if (typeof low === "number" && low > 0) {
          candidates.push({
            price: low,
            source: "TCGplayer",
            url:
              card.tcgplayer_url ||
              `https://www.tcgplayer.com/search/pokemon/product?q=${encodeURIComponent(card.name)}`,
          });
        }
      }
    }
    if (initialEbayMedian != null && initialEbayMedian > 0) {
      const q = [
        "pokemon",
        card.name,
        card.number,
        card.set_name,
      ]
        .filter(Boolean)
        .join(" ");
      candidates.push({
        price: initialEbayMedian,
        source: "eBay",
        url: `https://www.ebay.com/sch/i.html?_nkw=${encodeURIComponent(q)}&LH_BIN=1`,
      });
    }
    if (!candidates.length) return null;
    return candidates.sort((a, b) => a.price - b.price)[0];
  }, [card, initialEbayMedian]);

  const tcgMid = useMemo(() => {
    if (!card.tcgplayer_prices) return null;
    const variants = Object.values(card.tcgplayer_prices);
    for (const v of variants) {
      if (typeof v?.market === "number") return v.market;
      if (typeof v?.mid === "number") return v.mid;
    }
    return null;
  }, [card]);

  const cardmarketTrend = card.cardmarket_prices?.trendPrice ?? null;

  const secondaryPrices: SecondaryPrice[] = [
    {
      source: "TCGplayer",
      label: "Market",
      value: tcgMid,
      currency: "USD",
      delta: tcgDelta7d,
      spark: tcgSpark7d,
      sparkColor: "#60a5fa",
    },
    {
      source: "Cardmarket",
      label: "Trend",
      value: cardmarketTrend,
      currency: "EUR",
      delta: cardmarketDelta7d,
      spark: cardmarketSpark7d,
      sparkColor: "#FFCB05",
    },
    {
      source: "eBay",
      label: "Median",
      value: initialEbayMedian,
      currency: "USD",
      delta: ebayDelta7d,
      spark: ebaySpark7d,
      sparkColor: "#5BC9C2",
    },
  ];

  const types = card.types ?? [];

  return (
    <main className="min-h-screen bg-white text-gray-900 dark:bg-[#0F1419] dark:text-zinc-100">
      <div className="mx-auto flex max-w-6xl flex-col gap-8 px-4 py-8 pb-28 lg:pb-8">
        {/* Breadcrumb (theme toggle lives in TopNav site-wide — no duplicate here) */}
        <nav
          aria-label="Breadcrumb"
          className={cn("flex flex-wrap items-center gap-1 text-xs", faint)}
        >
          <Link href="/" className="hover:text-teal-600 dark:hover:text-teal-400">
            Home
          </Link>
          <ChevronRight className="h-3 w-3 opacity-60" />
          <Link href="/sets" className="hover:text-teal-600 dark:hover:text-teal-400">
            Sets
          </Link>
          <ChevronRight className="h-3 w-3 opacity-60" />
          <Link
            href={`/sets/${card.set_id}`}
            className="hover:text-teal-600 dark:hover:text-teal-400"
          >
            {card.set_name ?? card.set_id}
          </Link>
          <ChevronRight className="h-3 w-3 opacity-60" />
          <span className="font-medium text-gray-700 dark:text-zinc-300">{card.name}</span>
        </nav>

        {/* Prev/Next nav */}
        <div className="flex items-center justify-between gap-2">
          {neighbors.prev ? (
            <Link
              href={`/cards/${neighbors.prev.id}`}
              className="flex flex-1 min-w-0 items-center gap-2 rounded-full border border-gray-200 bg-white px-2.5 py-1.5 transition-colors hover:border-teal-300 dark:border-[#2D3543] dark:bg-[#1A1F29] dark:hover:border-teal-500/50"
            >
              <ChevronLeft className={cn("h-4 w-4 shrink-0", faint)} />
              <div className="min-w-0">
                <p className={cn("truncate text-[11px]", faint)}>Prev</p>
                <p className="truncate text-xs font-medium text-gray-700 dark:text-zinc-300">
                  {neighbors.prev.name} · {neighbors.prev.number}
                </p>
              </div>
            </Link>
          ) : (
            <div className="flex-1" />
          )}
          {neighbors.next ? (
            <Link
              href={`/cards/${neighbors.next.id}`}
              className="flex flex-1 min-w-0 items-center justify-end gap-2 rounded-full border border-gray-200 bg-white px-2.5 py-1.5 text-right transition-colors hover:border-teal-300 dark:border-[#2D3543] dark:bg-[#1A1F29] dark:hover:border-teal-500/50"
            >
              <div className="min-w-0">
                <p className={cn("truncate text-[11px]", faint)}>Next</p>
                <p className="truncate text-xs font-medium text-gray-700 dark:text-zinc-300">
                  {neighbors.next.name} · {neighbors.next.number}
                </p>
              </div>
              <ChevronRight className={cn("h-4 w-4 shrink-0", faint)} />
            </Link>
          ) : (
            <div className="flex-1" />
          )}
        </div>

        {/* Hero */}
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-[320px_1fr]">
          <div
            className="group mx-auto w-full [perspective:1000px]"
            style={{ maxWidth: 320 }}
          >
            <div
              className={cn(
                "relative aspect-[5/7] overflow-hidden rounded-xl border transition-all duration-500 ease-out",
                // light mode: noticeable layered shadow that anchors the card on white bg
                "border-gray-200 bg-white shadow-[0_20px_50px_-12px_rgba(0,0,0,0.25),0_8px_20px_-6px_rgba(0,0,0,0.12)]",
                // dark mode: glow ring for rares
                "dark:border-[#2D3543] dark:bg-[#1A1F29] dark:shadow-none",
                card.rarity?.toLowerCase().includes("rare") &&
                  "dark:ring-2 dark:ring-teal-400/40 dark:shadow-[0_0_40px_-8px_rgba(91,201,194,0.5)]",
                // tilt-on-hover (3D-ish using rotateY + slight rotateX + scale)
                "group-hover:[transform:perspective(1000px)_rotateY(8deg)_rotateX(-3deg)_scale(1.03)]",
                "group-hover:shadow-[0_30px_60px_-12px_rgba(0,0,0,0.35),0_15px_30px_-8px_rgba(255,203,5,0.25)]",
                "dark:group-hover:ring-amber-400/60",
              )}
            >
              {card.image_large ? (
                <Image
                  src={card.image_large}
                  alt={`${card.name} ${card.number ?? ""}`}
                  fill
                  priority
                  className="object-cover"
                  sizes="(max-width: 1024px) 320px, 360px"
                  unoptimized
                />
              ) : (
                <div className="flex h-full items-center justify-center text-gray-300 dark:text-zinc-700">
                  no image
                </div>
              )}

              {/* Shimmer sweep — diagonal highlight that travels across the card on hover */}
              <div
                aria-hidden
                className="pointer-events-none absolute inset-0 -translate-x-full opacity-0 transition-all duration-700 ease-out group-hover:translate-x-full group-hover:opacity-100"
                style={{
                  background:
                    "linear-gradient(115deg, transparent 30%, rgba(255,255,255,0.6) 50%, transparent 70%)",
                  mixBlendMode: "overlay",
                }}
              />

              {/* Sparkles — appear on hover, drift and twinkle */}
              <Sparkles
                aria-hidden
                className="pointer-events-none absolute right-3 top-3 h-5 w-5 text-amber-300 opacity-0 transition-opacity duration-300 drop-shadow-[0_0_6px_rgba(255,203,5,0.8)] group-hover:opacity-100 group-hover:[animation:pl-sparkle_1.8s_ease-in-out_infinite]"
              />
              <Sparkles
                aria-hidden
                className="pointer-events-none absolute bottom-4 left-3 h-4 w-4 text-amber-200 opacity-0 transition-opacity duration-500 drop-shadow-[0_0_6px_rgba(255,203,5,0.6)] group-hover:opacity-100 group-hover:[animation:pl-sparkle_1.8s_ease-in-out_infinite_0.4s]"
              />
            </div>
          </div>

          <div className="flex flex-col gap-5">
            <div>
              <h1 className={cn("text-balance text-2xl font-extrabold tracking-tight lg:text-4xl", heading)}>
                {card.name}
              </h1>
              <p className={cn("mt-1 text-sm", muted)}>
                {card.number ?? "—"} · {card.set_name ?? card.set_id}
              </p>
            </div>

            <div className="flex flex-wrap gap-1.5">
              {card.rarity && (
                <span className="inline-flex items-center rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-800 ring-1 ring-amber-300 dark:bg-amber-400/15 dark:text-amber-300 dark:ring-amber-400/30">
                  {card.rarity}
                </span>
              )}
              {types.map((t) => (
                <span
                  key={t}
                  className="inline-flex items-center rounded-full bg-teal-100 px-2.5 py-1 text-xs font-semibold text-teal-800 ring-1 ring-teal-300 dark:bg-teal-400/15 dark:text-teal-300 dark:ring-teal-400/30"
                >
                  {t}
                </span>
              ))}
              {card.subtypes?.map((s) => (
                <span
                  key={s}
                  className="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-1 text-xs font-semibold text-gray-600 dark:bg-[#222834] dark:text-zinc-300"
                >
                  {s}
                </span>
              ))}
            </div>

            <CheapestHero
              data={cheapest}
              ownedToggle={<OwnedToggle cardId={card.id} variant="hero" />}
            />
          </div>
        </div>

        {/* Price chart */}
        <PriceChart
          cardId={card.id}
          height={300}
          isOnFire={Math.max(ebayDelta7d ?? 0, tcgDelta7d ?? 0, cardmarketDelta7d ?? 0) >= 10}
        />

        {/* Secondary prices */}
        <SecondaryPrices items={secondaryPrices} />

        {/* Live listings (real-time eBay) */}
        <LiveListings cardId={card.id} />

        {/* Empty state mascot if we have very little data */}
        {!cheapest && (
          <div className="rounded-xl border-2 border-dashed border-gray-200 bg-gray-50/50 p-10 text-center dark:border-[#2D3543] dark:bg-[#1A1F29]/50">
            <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-teal-100 dark:bg-teal-400/15">
              <Search className="h-7 w-7 text-teal-600 dark:text-teal-400" />
              <MascotMark className="-ml-3 -mt-6 h-8 w-8" />
            </div>
            <p className={cn("mt-4 text-base font-bold", heading)}>No active price snapshot yet</p>
            <p className={cn("mt-1 mx-auto max-w-md text-sm", muted)}>
              We&apos;re hunting prices for you 🔍. Our dragon scouts are checking auction history as we speak!
            </p>
          </div>
        )}

        {/* Other versions */}
        {alternates.length > 0 && (
          <section>
            <h2 className={cn("mb-3 text-sm font-bold", heading)}>
              Other versions of {card.name}
              <span className={cn("ml-2 font-normal", faint)}>· {alternates.length}</span>
            </h2>
            <div className="grid grid-cols-3 gap-3 lg:grid-cols-6">
              {alternates.map((v) => (
                <Link key={v.id} href={`/cards/${v.id}`} className="group">
                  <div className="relative aspect-[5/7] overflow-hidden rounded-lg border border-gray-200 bg-white transition-all group-hover:border-teal-300 group-hover:shadow-lg group-hover:shadow-gray-200/60 dark:border-[#2D3543] dark:bg-[#1A1F29] dark:group-hover:border-teal-500/50">
                    {v.image_small ? (
                      <Image
                        src={v.image_small}
                        alt={v.name}
                        fill
                        className="object-cover"
                        sizes="(max-width:1024px) 30vw, 15vw"
                        unoptimized
                      />
                    ) : (
                      <div className="flex h-full items-center justify-center text-gray-300">no image</div>
                    )}
                  </div>
                  <p className={cn("mt-1.5 truncate text-xs", muted)}>{v.number ?? "—"}</p>
                  {v.market_price_usd != null && (
                    <p className="font-mono text-xs font-bold text-amber-500 dark:text-amber-400">
                      {fmtUSD(v.market_price_usd)}
                    </p>
                  )}
                </Link>
              ))}
            </div>
          </section>
        )}
      </div>

      {/* Sticky mobile CTA */}
      {cheapest && (
        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-gray-200 bg-white/95 px-4 py-3 backdrop-blur lg:hidden dark:border-[#2D3543] dark:bg-[#0F1419]/95">
          <div className="mx-auto flex max-w-6xl items-center gap-3">
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-400">
                Cheapest
              </p>
              <p className="font-mono text-lg font-extrabold text-amber-500 dark:text-amber-400">
                {fmtUSD(cheapest.price)}
              </p>
            </div>
            <a
              href={cheapest.url}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-auto inline-flex flex-1 items-center justify-center gap-2 rounded-full bg-amber-400 px-4 py-3 text-sm font-bold text-amber-950 hover:bg-amber-300"
            >
              <ShoppingCart className="h-4 w-4" />
              Buy on {cheapest.source}
            </a>
          </div>
        </div>
      )}
    </main>
  );
}
