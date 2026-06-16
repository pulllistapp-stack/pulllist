import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Bell, Heart, Lock, Sparkles, Target, TrendingUp } from "lucide-react";

import { AssetMixDonut } from "@/components/AssetMixDonut";
import { RarityChip } from "@/components/RarityChip";
import type { PublicPortfolio } from "@/lib/api";

export const dynamic = "force-dynamic";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

async function fetchPublic(token: string): Promise<PublicPortfolio | null> {
  try {
    const res = await fetch(`${API_BASE}/p/${encodeURIComponent(token)}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });
    if (!res.ok) return null;
    return (await res.json()) as PublicPortfolio;
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const data = await fetchPublic(token);
  if (!data) return { title: "Portfolio not found · PullList" };
  const value =
    data.estimated_value_usd != null
      ? `· $${data.estimated_value_usd.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
      : "";
  return {
    title: `${data.display_name}'s vault · PullList`,
    description: `${data.unique_cards} cards across ${data.sets_touched} sets ${value}`,
    openGraph: {
      title: `${data.display_name}'s Pokémon TCG vault`,
      description: `${data.unique_cards} cards · ${data.sets_touched} sets ${value}`,
      type: "profile",
    },
  };
}

export default async function PublicPortfolioPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const data = await fetchPublic(token);
  if (!data) notFound();

  const assetMixSlices = data.asset_mix.map((s, i) => ({
    label: s.label,
    value: s.value,
    color: PALETTE_PUBLIC[i % PALETTE_PUBLIC.length],
  }));
  const assetMixTotal = data.asset_mix.reduce((acc, s) => acc + s.value, 0);

  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:py-12">
      {/* Hero */}
      <header className="mb-8 flex flex-col sm:flex-row sm:items-start gap-4">
        <div className="inline-flex h-20 w-20 shrink-0 items-center justify-center rounded-full bg-accent-yellow/15 ring-2 ring-accent-yellow/30">
          <Image
            src="/pullist-mascot.png"
            alt=""
            width={70}
            height={70}
            className="object-contain"
            unoptimized
            priority
          />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-mono uppercase tracking-widest text-text-tertiary">
            <Sparkles className="inline h-3 w-3 mr-1 text-accent-yellow" />
            Public vault
          </p>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-text-primary mt-0.5">
            {data.display_name}&apos;s vault
          </h1>
          {data.bio && (
            <p className="mt-2 text-sm text-text-secondary leading-relaxed max-w-xl">
              {data.bio}
            </p>
          )}
        </div>
      </header>

      {/* Stats strip */}
      <div className="mb-8 grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatTile label="Cards" value={data.unique_cards.toLocaleString()} sub="unique" />
        <StatTile label="Total qty" value={data.total_qty.toLocaleString()} sub="copies" />
        <StatTile label="Sets" value={data.sets_touched.toString()} sub="touched" />
        <StatTile
          label="Value"
          value={
            data.estimated_value_usd != null
              ? `$${data.estimated_value_usd.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
              : "—"
          }
          sub={
            data.estimated_value_usd != null
              ? "current market"
              : "owner kept private"
          }
          highlight={data.estimated_value_usd != null}
        />
      </div>

      {/* Asset mix + growth (if shared) */}
      <div className="mb-8 grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-card bg-bg-surface border border-border p-5">
          <h2 className="mb-4 text-sm font-mono uppercase tracking-wider text-text-tertiary">
            Asset mix
          </h2>
          <AssetMixDonut slices={assetMixSlices} total={assetMixTotal} />
        </div>

        {data.growth && data.growth.length >= 2 ? (
          <div className="rounded-card bg-bg-surface border border-border p-5">
            <h2 className="mb-2 text-sm font-mono uppercase tracking-wider text-text-tertiary">
              Portfolio growth
            </h2>
            <GrowthMiniChart points={data.growth} />
          </div>
        ) : (
          <div className="rounded-card bg-bg-surface border border-border p-5 flex items-center justify-center text-center min-h-[12rem]">
            <div>
              <Lock className="mx-auto h-5 w-5 text-text-tertiary mb-2" />
              <p className="text-xs text-text-tertiary">
                Growth chart kept private
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Top cards */}
      {data.top_cards.length > 0 && (
        <section className="mb-10">
          <h2 className="mb-4 text-xl font-bold text-text-primary">
            Top cards
            <span className="ml-2 text-sm font-normal text-text-tertiary">
              · by market value
            </span>
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
            {data.top_cards.map((c) => (
              <PublicCardTile key={c.card_id} card={c} />
            ))}
          </div>
        </section>
      )}

      {/* Set completion */}
      {data.set_completion.length > 0 && (
        <section className="mb-10">
          <h2 className="mb-4 text-xl font-bold text-text-primary">
            Set completion
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {data.set_completion.map((s) => (
              <SetCompletionBar key={s.set_id} completion={s} />
            ))}
          </div>
        </section>
      )}

      {/* Full grid (if shared) */}
      {data.all_cards && data.all_cards.length > 0 && (
        <section className="mb-10">
          <h2 className="mb-4 text-xl font-bold text-text-primary">
            Full vault
            <span className="ml-2 text-sm font-normal text-text-tertiary">
              · {data.all_cards.length} cards
            </span>
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
            {data.all_cards.map((c) => (
              <PublicCardTile key={c.card_id} card={c} />
            ))}
          </div>
        </section>
      )}

      {/* Wishlist (if shared) */}
      {data.wishlist && data.wishlist.length > 0 && (
        <section className="mb-10">
          <h2 className="mb-4 text-xl font-bold text-text-primary inline-flex items-center gap-2">
            <Heart className="h-5 w-5 text-rose-500 fill-rose-500" />
            Wishlist
            <span className="ml-1 text-sm font-normal text-text-tertiary">
              · what they&apos;re chasing
            </span>
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {data.wishlist.map((w) => (
              <WishlistRow key={w.card_id} item={w} />
            ))}
          </div>
        </section>
      )}

      {/* CTA back to PullList */}
      <div className="mt-12 rounded-3xl border border-border bg-gradient-to-br from-accent-yellow/10 via-amber-200/5 to-teal-400/10 p-8 sm:p-10 text-center">
        <Sparkles className="mx-auto h-6 w-6 text-amber-400 mb-3" />
        <p className="text-lg font-extrabold text-text-primary">
          Start your own vault
        </p>
        <p className="mt-1 text-sm text-text-secondary">
          Free forever. Track every pull, watch prices, share with friends.
        </p>
        <Link
          href="/signup"
          className="mt-5 inline-flex items-center gap-2 rounded-full bg-accent-yellow text-gray-900 font-bold px-6 py-2.5 text-sm hover:brightness-105 shadow-md shadow-accent-yellow/30 transition-all"
        >
          Create your free PullList
        </Link>
      </div>
    </main>
  );
}

// ────────── view components ──────────

const PALETTE_PUBLIC = [
  "#FCC419",
  "#5BC9C2",
  "#FF6B9D",
  "#A78BFA",
  "#34D399",
  "#F472B6",
  "#FB923C",
  "#60A5FA",
];

function StatTile({
  label,
  value,
  sub,
  highlight,
}: {
  label: string;
  value: string;
  sub?: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-2xl border bg-bg-surface p-4 ${
        highlight ? "border-accent-yellow/40" : "border-border"
      }`}
    >
      <p className="text-[10px] font-mono uppercase tracking-widest text-text-tertiary">
        {label}
      </p>
      <p className="mt-1 text-2xl font-extrabold text-text-primary">{value}</p>
      {sub && <p className="text-[11px] font-mono text-text-tertiary">{sub}</p>}
    </div>
  );
}

function PublicCardTile({
  card,
}: {
  card: NonNullable<PublicPortfolio["top_cards"]>[number];
}) {
  return (
    <Link
      href={`/cards/${card.card_id}`}
      className="group block rounded-card border border-border bg-bg-surface p-2 transition-all duration-200 hover:border-accent-yellow/40 hover:-translate-y-0.5"
    >
      <div className="relative aspect-[245/342] w-full overflow-hidden rounded-md bg-bg">
        {card.image_small ? (
          <Image
            src={card.image_small}
            alt={card.name}
            fill
            sizes="(max-width: 768px) 50vw, 200px"
            className="object-contain group-hover:scale-[1.03] transition-transform duration-300"
            unoptimized
          />
        ) : (
          <div className="flex h-full items-center justify-center text-text-tertiary text-xs">
            no image
          </div>
        )}
        {card.qty > 1 && (
          <span className="absolute top-1.5 right-1.5 rounded-full bg-bg/80 backdrop-blur-sm px-1.5 py-0.5 text-[10px] font-mono font-bold text-text-primary ring-1 ring-border">
            ×{card.qty}
          </span>
        )}
      </div>
      <div className="mt-2 px-1 flex items-center justify-between gap-2">
        <span className="text-xs font-mono text-text-tertiary">
          #{card.number ?? "—"}
        </span>
        {card.market_price_usd != null && (
          <span className="font-mono text-xs font-bold text-accent-yellow">
            ${card.market_price_usd.toFixed(2)}
          </span>
        )}
      </div>
      <p className="mt-0.5 px-1 text-sm font-medium truncate" title={card.name}>
        {card.name}
      </p>
      {card.rarity && (
        <div className="mt-1 px-1">
          <RarityChip rarity={card.rarity} />
        </div>
      )}
    </Link>
  );
}

function SetCompletionBar({
  completion,
}: {
  completion: PublicPortfolio["set_completion"][number];
}) {
  const pct = Math.max(0, Math.min(100, completion.completion_pct));
  return (
    <Link
      href={`/sets/${completion.set_id}`}
      className="block rounded-2xl border border-border bg-bg-surface p-4 hover:border-accent-yellow/40 transition-colors"
    >
      <div className="flex items-center justify-between gap-2 mb-2">
        <p className="text-sm font-bold text-text-primary truncate">
          {completion.set_name}
        </p>
        <span className="text-xs font-mono text-text-tertiary shrink-0">
          {completion.owned_unique} / {completion.total_cards}
        </span>
      </div>
      <div className="relative h-2 rounded-full bg-bg overflow-hidden">
        <div
          className="absolute inset-y-0 left-0 bg-gradient-to-r from-accent-yellow to-amber-400 rounded-full"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="mt-1 text-[11px] font-mono text-text-tertiary text-right">
        {pct.toFixed(1)}%
      </p>
    </Link>
  );
}

function WishlistRow({
  item,
}: {
  item: NonNullable<PublicPortfolio["wishlist"]>[number];
}) {
  const targetMet =
    item.max_price_usd != null &&
    item.market_price_usd != null &&
    item.market_price_usd <= item.max_price_usd;
  return (
    <Link
      href={`/cards/${item.card_id}`}
      className="flex gap-3 rounded-2xl border border-border bg-bg-surface p-3 hover:border-rose-400/40 transition-colors"
    >
      <div className="relative h-20 w-14 shrink-0 overflow-hidden rounded-md bg-bg">
        {item.image_small ? (
          <Image
            src={item.image_small}
            alt={item.name}
            fill
            className="object-contain"
            sizes="56px"
            unoptimized
          />
        ) : null}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-bold text-text-primary">
          {item.name}
        </p>
        <p className="text-xs text-text-tertiary truncate font-mono">
          {item.set_name}
        </p>
        <div className="mt-1.5 flex items-center gap-2 text-xs">
          {item.market_price_usd != null && (
            <span className="font-mono text-text-secondary">
              ${item.market_price_usd.toFixed(2)}
            </span>
          )}
          {item.max_price_usd != null && (
            <span className="font-mono text-text-tertiary">
              target ${item.max_price_usd.toFixed(2)}
            </span>
          )}
          {targetMet && (
            <span className="inline-flex items-center gap-0.5 rounded-full bg-accent-green/15 text-accent-green border border-accent-green/30 px-1.5 py-0.5 text-[10px] font-bold uppercase">
              <Target className="h-2.5 w-2.5" /> Met
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}

function GrowthMiniChart({
  points,
}: {
  points: NonNullable<PublicPortfolio["growth"]>;
}) {
  const W = 600;
  const H = 180;
  const padX = 12;
  const padY = 16;
  const innerW = W - padX * 2;
  const innerH = H - padY * 2;

  const values = points.map((p) => p.value);
  const minV = Math.min(...values);
  const maxV = Math.max(...values);
  const range = maxV - minV;
  const lo = range < 0.01 ? minV - 1 : minV - range * 0.08;
  const hi = range < 0.01 ? maxV + 1 : maxV + range * 0.12;
  const span = hi - lo || 1;

  const coords = points.map((p, i) => ({
    x:
      padX +
      (points.length === 1 ? innerW / 2 : (i * innerW) / (points.length - 1)),
    y: padY + innerH - ((p.value - lo) / span) * innerH,
  }));

  const up = points[points.length - 1].value >= points[0].value;
  const strokeColor = up ? "rgb(34 197 94)" : "rgb(239 68 68)";
  const fillColor = up
    ? "rgba(34, 197, 94, 0.12)"
    : "rgba(239, 68, 68, 0.10)";
  const lineD = coords
    .map((c, i) => `${i === 0 ? "M" : "L"}${c.x},${c.y}`)
    .join(" ");
  const areaD = `${lineD} L${coords[coords.length - 1].x},${padY + innerH} L${coords[0].x},${padY + innerH} Z`;

  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        <TrendingUp
          className={`h-4 w-4 ${up ? "text-accent-green" : "text-accent-red"}`}
        />
        <span
          className={`text-xs font-mono ${up ? "text-accent-green" : "text-accent-red"}`}
        >
          {up ? "+" : ""}
          ${(points[points.length - 1].value - points[0].value).toFixed(2)}
        </span>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-44"
        preserveAspectRatio="none"
      >
        <line
          x1={padX}
          x2={W - padX}
          y1={padY + innerH}
          y2={padY + innerH}
          stroke="currentColor"
          strokeOpacity={0.08}
        />
        <path d={areaD} fill={fillColor} />
        <path
          d={lineD}
          fill="none"
          stroke={strokeColor}
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle
          cx={coords[coords.length - 1].x}
          cy={coords[coords.length - 1].y}
          r={4}
          fill={strokeColor}
        />
      </svg>
      <div className="mt-2 flex items-center justify-between text-[11px] font-mono text-text-tertiary">
        <span>{points[0].date}</span>
        <span>{points[points.length - 1].date}</span>
      </div>
    </div>
  );
}
