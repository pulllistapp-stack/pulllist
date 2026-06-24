"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  Crown,
  Flame,
  Medal,
  Trophy,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

import { getTrending, type TrendingMover, type TrendingTier } from "@/lib/api";
import { rarityChipClass } from "@/lib/rarity";
import { MascotLoader } from "@/components/MascotLoader";

const PERIODS = [
  { label: "1d", days: 1 },
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
] as const;

const SOURCES = [
  { key: "ebay", label: "eBay" },
  { key: "tcgplayer", label: "TCGplayer" },
] as const;

// Price tier floors — filters out penny-stock noise. Default $5 hides
// bulk-card chatter while keeping real chase-card movement visible.
const PRICE_TIERS = [
  { label: "$5+", value: 5 },
  { label: "$10+", value: 10 },
  { label: "$50+", value: 50 },
  { label: "$100+", value: 100 },
  { label: "$1000+", value: 1000 },
] as const;

// Rarity tier — separates pack-pull market from chase-card market. Bulk
// covers Common through Double Rare; Chase covers Ultra Rare and above
// plus all promo categories. Mixing them makes a $5 Common +50% mover
// drown in a $500 SIR +50% mover noise so the toggle's the right primitive.
const TIERS: { key: TrendingTier; label: string; sub: string }[] = [
  { key: "all", label: "All", sub: "Every rarity" },
  { key: "bulk", label: "Bulk", sub: "Common — Double Rare" },
  { key: "chase", label: "Chase", sub: "Ultra Rare & up + promos" },
];

// Tier defaults — bulk cards trade at much lower price points, so the
// shared $5 floor would empty the bulk view. Pick a sensible starting
// minimum per tier; users can override via the price pill row.
const TIER_DEFAULT_MIN_PRICE: Record<TrendingTier, number> = {
  all: 5,
  bulk: 5,
  chase: 10,
};

type Direction = "up" | "down";

export default function TrendingPage() {
  const [periodDays, setPeriodDays] = useState(7);
  const [source, setSource] = useState<(typeof SOURCES)[number]["key"]>("ebay");
  const [direction, setDirection] = useState<Direction>("up");
  const [tier, setTier] = useState<TrendingTier>("all");
  // Default $5 floor — surfaces real chase-card movement, hides bulk noise.
  // Top tiers ($100+ / $1000+) shift attention to vintage holy grails + slabs.
  const [minPrice, setMinPrice] = useState<number>(5);
  const [movers, setMovers] = useState<TrendingMover[]>([]);
  const [eligible, setEligible] = useState(0);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  // Switching tier resets the price floor to a tier-appropriate default —
  // a $5 floor on Bulk empties the page; a $1 floor on Chase shows nothing
  // worth looking at.
  function switchTier(next: TrendingTier) {
    setTier(next);
    setMinPrice(TIER_DEFAULT_MIN_PRICE[next]);
  }

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    getTrending({
      periodDays,
      source,
      direction,
      limit: 25,
      minPriceUsd: minPrice,
      tier,
    })
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
  }, [periodDays, source, direction, minPrice, tier]);

  const top3 = movers.slice(0, 3);
  const rest = movers.slice(3);

  return (
    <main className="relative mx-auto max-w-6xl px-4 py-10 sm:py-14">
      {/* Atmospheric glow */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-32 left-1/4 h-80 w-80 rounded-full bg-accent-yellow/10 blur-3xl"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute top-40 right-1/4 h-80 w-80 rounded-full bg-teal-400/10 blur-3xl"
      />

      {/* Hero */}
      <div className="relative mb-10">
        <div className="flex items-center gap-3 mb-3">
          <span
            className={`inline-flex h-12 w-12 items-center justify-center rounded-2xl ${
              direction === "up"
                ? "bg-accent-green/15 text-accent-green"
                : "bg-accent-red/15 text-accent-red"
            }`}
          >
            {direction === "up" ? (
              <TrendingUp className="h-6 w-6" />
            ) : (
              <TrendingDown className="h-6 w-6" />
            )}
          </span>
          <div>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-text-primary">
              Trending
            </h1>
            <p className="text-sm text-text-secondary">
              Biggest {direction === "up" ? "gainers" : "losers"} across snapshot data.
            </p>
          </div>
        </div>

        {/* Tier toggle — most decision-shaping filter, lives on its own row */}
        <div className="mt-5 inline-flex rounded-full border border-border bg-bg-surface p-1">
          {TIERS.map((t) => (
            <button
              key={t.key}
              onClick={() => switchTier(t.key)}
              title={t.sub}
              className={`rounded-full px-4 py-2 text-xs font-semibold transition-colors ${
                tier === t.key
                  ? "bg-accent-yellow text-gray-900 shadow-sm shadow-accent-yellow/30"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Filter row */}
        <div className="mt-3 flex flex-wrap items-center gap-3">
          {/* Direction tabs */}
          <div className="inline-flex rounded-full border border-border bg-bg-surface p-1">
            <DirectionPill
              active={direction === "up"}
              accent="green"
              onClick={() => setDirection("up")}
            >
              <ArrowUp className="h-3.5 w-3.5" /> Gainers
            </DirectionPill>
            <DirectionPill
              active={direction === "down"}
              accent="red"
              onClick={() => setDirection("down")}
            >
              <ArrowDown className="h-3.5 w-3.5" /> Losers
            </DirectionPill>
          </div>

          {/* Period pills */}
          <div className="inline-flex rounded-full border border-border bg-bg-surface p-1">
            {PERIODS.map((p) => (
              <button
                key={p.days}
                onClick={() => setPeriodDays(p.days)}
                className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-colors ${
                  periodDays === p.days
                    ? "bg-accent-yellow text-gray-900 shadow-sm shadow-accent-yellow/30"
                    : "text-text-secondary hover:text-text-primary"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Source pills */}
          <div className="inline-flex rounded-full border border-border bg-bg-surface p-1">
            {SOURCES.map((s) => (
              <button
                key={s.key}
                onClick={() => setSource(s.key)}
                className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-colors ${
                  source === s.key
                    ? "bg-bg-elevated text-text-primary"
                    : "text-text-secondary hover:text-text-primary"
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>

          {/* Price floor pills — filters out penny-stock noise */}
          <div className="inline-flex rounded-full border border-border bg-bg-surface p-1">
            {PRICE_TIERS.map((tier) => (
              <button
                key={tier.value}
                onClick={() => setMinPrice(tier.value)}
                className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-colors ${
                  minPrice === tier.value
                    ? "bg-accent-green/15 text-accent-green shadow-sm shadow-accent-green/20"
                    : "text-text-secondary hover:text-text-primary"
                }`}
              >
                {tier.label}
              </button>
            ))}
          </div>
        </div>

        {/* Stats banner */}
        <div className="mt-4 flex items-center gap-2 text-xs font-mono text-text-tertiary">
          <Flame className="h-3.5 w-3.5 text-amber-500" />
          <span>
            <span className="text-text-primary font-semibold">
              {movers.length}
            </span>{" "}
            shown · {eligible.toLocaleString()} eligible · {periodDays}d window ·{" "}
            {source === "ebay" ? "eBay" : "TCGplayer"} ·{" "}
            <span className="text-accent-green font-semibold">${minPrice}+</span>
            {tier !== "all" && (
              <>
                {" "}·{" "}
                <span className="text-accent-yellow font-semibold">
                  {tier === "bulk" ? "Bulk tier" : "Chase tier"}
                </span>
              </>
            )}
          </span>
        </div>
      </div>

      {err && (
        <div className="rounded-card bg-accent-red/10 border border-accent-red/30 p-4 text-sm mb-4">
          {err}
        </div>
      )}

      {loading ? (
        <MascotLoader size="lg" className="py-20" />
      ) : movers.length === 0 ? (
        <EmptyState periodDays={periodDays} />
      ) : (
        <div className="space-y-8">
          {/* Top 3 podium */}
          {top3.length > 0 && (
            <section>
              <h2 className="mb-3 text-xs font-mono uppercase tracking-wider text-text-tertiary">
                Top {top3.length}
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {top3.map((m, i) => (
                  <PodiumCard
                    key={m.card_id}
                    mover={m}
                    rank={i + 1}
                    direction={direction}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Rest of list */}
          {rest.length > 0 && (
            <section>
              <h2 className="mb-3 text-xs font-mono uppercase tracking-wider text-text-tertiary">
                Next {rest.length}
              </h2>
              <ol className="flex flex-col gap-2">
                {rest.map((m, i) => (
                  <MoverRow
                    key={m.card_id}
                    mover={m}
                    rank={i + 4}
                    direction={direction}
                  />
                ))}
              </ol>
            </section>
          )}
        </div>
      )}
    </main>
  );
}

// ────────── components ──────────

function DirectionPill({
  active,
  accent,
  onClick,
  children,
}: {
  active: boolean;
  accent: "green" | "red";
  onClick: () => void;
  children: React.ReactNode;
}) {
  const activeClass =
    accent === "green"
      ? "bg-accent-green/15 text-accent-green shadow-sm shadow-accent-green/20"
      : "bg-accent-red/15 text-accent-red shadow-sm shadow-accent-red/20";
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold transition-colors ${
        active ? activeClass : "text-text-secondary hover:text-text-primary"
      }`}
    >
      {children}
    </button>
  );
}

function RankBadge({ rank }: { rank: number }) {
  const styles: Record<number, { bg: string; icon: React.ReactNode }> = {
    1: {
      bg: "bg-gradient-to-br from-amber-300 to-yellow-500 text-amber-950 shadow-md shadow-amber-500/40",
      icon: <Crown className="h-3.5 w-3.5" />,
    },
    2: {
      bg: "bg-gradient-to-br from-slate-200 to-slate-400 text-slate-800 shadow-md shadow-slate-400/30",
      icon: <Trophy className="h-3.5 w-3.5" />,
    },
    3: {
      bg: "bg-gradient-to-br from-orange-300 to-orange-500 text-orange-950 shadow-md shadow-orange-500/30",
      icon: <Medal className="h-3.5 w-3.5" />,
    },
  };
  const s = styles[rank];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold font-mono uppercase tracking-wider ${s.bg}`}
    >
      {s.icon} #{rank}
    </span>
  );
}

function PodiumCard({
  mover,
  rank,
  direction,
}: {
  mover: TrendingMover;
  rank: number;
  direction: Direction;
}) {
  const up = direction === "up";
  const deltaColor = up ? "text-accent-green" : "text-accent-red";

  // Subtle border tint for 1st place to make it pop
  const borderTint =
    rank === 1
      ? "border-amber-400/40"
      : rank === 2
        ? "border-slate-400/30"
        : "border-orange-400/30";

  return (
    <Link
      href={`/cards/${mover.card_id}`}
      className={`group relative flex items-center gap-3 rounded-2xl border ${borderTint} bg-bg-surface p-4 transition-all duration-200 hover:-translate-y-1 hover:border-accent-yellow/50 hover:shadow-lg hover:shadow-accent-yellow/10`}
    >
      <div className="absolute -top-2 -left-2">
        <RankBadge rank={rank} />
      </div>

      <div className="relative h-24 w-16 shrink-0 overflow-hidden rounded-md bg-bg">
        {mover.image_small && (
          <Image
            src={mover.image_small}
            alt={mover.name ?? ""}
            fill
            className="object-contain"
            sizes="64px"
            unoptimized
          />
        )}
      </div>

      <div className="min-w-0 flex-1">
        <p
          className="truncate text-sm font-bold text-text-primary"
          title={mover.name ?? mover.card_id}
        >
          {mover.name ?? mover.card_id}
        </p>
        <p className="truncate text-xs text-text-tertiary font-mono mt-0.5">
          {mover.set_name ?? "?"} · #{mover.number ?? "—"}
        </p>
        {mover.rarity && (
          <span
            className={`mt-2 inline-block rounded-chip px-1.5 py-0.5 text-[10px] font-medium ${rarityChipClass(
              mover.rarity,
              false,
            )}`}
          >
            {mover.rarity}
          </span>
        )}
        <div className="mt-2 flex items-baseline gap-2">
          <span className={`text-xl font-extrabold ${deltaColor}`}>
            {up ? "+" : ""}
            {mover.delta_pct.toFixed(1)}%
          </span>
          <span className="text-xs font-mono text-text-secondary">
            ${mover.latest_price.toFixed(2)}
          </span>
        </div>
        <PriceArc
          from={mover.oldest_price}
          to={mover.latest_price}
          up={up}
        />
      </div>
    </Link>
  );
}

function MoverRow({
  mover,
  rank,
  direction,
}: {
  mover: TrendingMover;
  rank: number;
  direction: Direction;
}) {
  const up = direction === "up";
  return (
    <li>
      <Link
        href={`/cards/${mover.card_id}`}
        className="group flex items-center gap-3 rounded-card border border-border bg-bg-surface p-3 transition-all duration-200 hover:border-accent-yellow/40 hover:-translate-y-0.5"
      >
        <span className="w-6 text-center font-mono text-xs text-text-tertiary">
          #{rank}
        </span>

        <div className="relative h-14 w-10 shrink-0 overflow-hidden rounded-md bg-bg">
          {mover.image_small && (
            <Image
              src={mover.image_small}
              alt={mover.name ?? ""}
              fill
              className="object-contain"
              sizes="40px"
              unoptimized
            />
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <div className="truncate text-sm font-semibold text-text-primary">
              {mover.name ?? mover.card_id}
            </div>
            {mover.rarity && (
              <span
                className={`shrink-0 rounded-chip px-1.5 py-0.5 text-[10px] font-medium ${rarityChipClass(
                  mover.rarity,
                  false,
                )}`}
              >
                {mover.rarity}
              </span>
            )}
          </div>
          <div className="truncate text-xs text-text-tertiary font-mono mt-0.5">
            {mover.set_name ?? "?"} · #{mover.number ?? "—"}
          </div>
        </div>

        {/* Tiny price arc */}
        <div className="hidden sm:block">
          <PriceArc
            from={mover.oldest_price}
            to={mover.latest_price}
            up={up}
          />
        </div>

        <div className="text-right shrink-0">
          <div className="font-mono text-sm font-bold text-text-primary">
            ${mover.latest_price.toFixed(2)}
          </div>
          <div
            className={`text-xs font-semibold ${
              up ? "text-accent-green" : "text-accent-red"
            }`}
          >
            {up ? "▲" : "▼"} {Math.abs(mover.delta_pct).toFixed(1)}%
          </div>
        </div>
      </Link>
    </li>
  );
}

/**
 * Tiny 2-point sparkline showing oldest → latest. We don't have the full
 * series on the trending payload, so this is a min/max-anchored slope hint
 * rather than a true sparkline. Cheap and conveys direction at a glance.
 */
function PriceArc({
  from,
  to,
  up,
}: {
  from: number;
  to: number;
  up: boolean;
}) {
  if (!from || !to) return null;
  const w = 48;
  const h = 18;
  const pad = 2;
  // Use the larger of the two as the upper bound so both points fit.
  const lo = Math.min(from, to);
  const hi = Math.max(from, to);
  const range = hi - lo || 1;
  const y = (v: number) => h - pad - ((v - lo) / range) * (h - pad * 2);
  const stroke = up ? "rgb(34 197 94)" : "rgb(239 68 68)";
  return (
    <svg width={w} height={h} aria-hidden className="overflow-visible">
      <polyline
        points={`${pad},${y(from)} ${w - pad},${y(to)}`}
        fill="none"
        stroke={stroke}
        strokeWidth={2}
        strokeLinecap="round"
      />
      <circle cx={pad} cy={y(from)} r={2} fill={stroke} opacity={0.5} />
      <circle cx={w - pad} cy={y(to)} r={2.5} fill={stroke} />
    </svg>
  );
}

function SkeletonList() {
  return (
    <div className="space-y-6">
      {/* Podium skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="flex items-center gap-3 rounded-2xl border border-border bg-bg-surface p-4 animate-pulse"
          >
            <div className="h-24 w-16 rounded-md bg-bg" />
            <div className="flex-1 space-y-2">
              <div className="h-3 w-3/4 rounded bg-bg" />
              <div className="h-2 w-1/2 rounded bg-bg" />
              <div className="h-5 w-2/3 rounded bg-bg mt-2" />
            </div>
          </div>
        ))}
      </div>

      {/* Rows skeleton */}
      <div className="space-y-2">
        {[0, 1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="flex items-center gap-3 rounded-card border border-border bg-bg-surface p-3 animate-pulse"
          >
            <div className="h-14 w-10 rounded-md bg-bg" />
            <div className="flex-1 space-y-2">
              <div className="h-3 w-1/2 rounded bg-bg" />
              <div className="h-2 w-1/3 rounded bg-bg" />
            </div>
            <div className="space-y-2 text-right">
              <div className="h-3 w-12 rounded bg-bg" />
              <div className="h-2 w-10 rounded bg-bg" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function EmptyState({ periodDays }: { periodDays: number }) {
  return (
    <div className="rounded-2xl border-2 border-dashed border-border bg-bg-surface/50 p-12 text-center">
      <Flame
        aria-hidden
        className="mx-auto h-12 w-12 text-text-tertiary mb-4 opacity-60"
      />
      <p className="text-lg font-bold text-text-primary">
        Not enough data yet
      </p>
      <p className="mt-2 text-sm text-text-secondary max-w-md mx-auto">
        Cards need at least 2 snapshots in the {periodDays}d window. Once the daily
        cron has run a few more times, this page fills in with real movers.
      </p>
    </div>
  );
}
