"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowUpRight,
  Loader2,
  RefreshCw,
  ShoppingCart,
  Star,
  Tag,
} from "lucide-react";

import { refreshCardPrice } from "@/lib/auth";
import type { Card } from "@/lib/api";
import {
  AFFILIATE_ENABLED,
  bestTcgPlayerUrl,
  wrapEbayUrl,
  wrapTcgPlayerUrl,
} from "@/lib/affiliate";

interface Props {
  card: Card;
  tcgMarket: number | null;
  ebayMedian: number | null;
  ownedToggle: React.ReactNode;
  wishlistButton: React.ReactNode;
}

function fmt(v: number | null): string {
  if (v == null || Number.isNaN(v)) return "—";
  if (v >= 1000) {
    return `$${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
  }
  return `$${v.toFixed(2)}`;
}

function buildEbayUrl(card: Card): string {
  const q = ["pokemon", card.name, card.number, card.set_name]
    .filter(Boolean)
    .join(" ");
  return `https://www.ebay.com/sch/i.html?_nkw=${encodeURIComponent(q)}&LH_BIN=1`;
}

export function CardPriceHero({
  card,
  tcgMarket,
  ebayMedian,
  ownedToggle,
  wishlistButton,
}: Props) {
  // Refresh button — overrides the server-rendered prices when the user
  // pulls fresh data on demand. Keeps the SSR'd page fast while letting
  // power users force a re-pull. Per `feedback-hide-staleness` we never
  // surface "updated N ago" anywhere; the only freshness signal is the
  // transient "Up to date!" badge that flashes briefly on click.
  const [refreshing, setRefreshing] = useState(false);
  const [override, setOverride] = useState<{
    tcg: number | null;
    ebay: number | null;
  } | null>(null);
  const [showFresh, setShowFresh] = useState(false);
  const freshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (freshTimer.current) clearTimeout(freshTimer.current);
    };
  }, []);

  const displayedTcg = override?.tcg ?? tcgMarket;
  const displayedEbay = override?.ebay ?? ebayMedian;

  const marketPrice =
    displayedTcg != null && displayedEbay != null
      ? (displayedTcg + displayedEbay) / 2
      : (displayedTcg ?? displayedEbay);

  const onRefresh = async () => {
    if (refreshing) return;
    setRefreshing(true);
    try {
      const result = await refreshCardPrice(card.id);
      setOverride({ tcg: result.tcg_market, ebay: result.ebay_median });
    } catch {
      // Keep showing the prior price — silent failure is better than a
      // scary toast for what's effectively a "nice to have" action.
    } finally {
      setRefreshing(false);
      setShowFresh(true);
      if (freshTimer.current) clearTimeout(freshTimer.current);
      freshTimer.current = setTimeout(() => setShowFresh(false), 2500);
    }
  };

  // Prefer the canonical product URL when we know the TCGplayer product
  // id (resolved out-of-band from pokemontcg.io's redirect endpoint and
  // stored on Card.tcgplayer_product_id). Search URL is the fallback.
  const tcgUrl = wrapTcgPlayerUrl(
    bestTcgPlayerUrl({
      productId: card.tcgplayer_product_id,
      cardName: card.name,
      cardNumber: card.number,
    }),
  );
  const ebayUrl = wrapEbayUrl(buildEbayUrl(card));

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {/* Market Price — hero, spans full width */}
      <div className="sm:col-span-2 relative overflow-hidden rounded-card border-2 border-accent-yellow/70 bg-bg-surface p-5">
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-2">
            <Star
              className="h-4 w-4 fill-accent-yellow text-accent-yellow"
              aria-hidden
            />
            <span className="font-mono text-[11px] uppercase tracking-wider text-text-tertiary font-semibold">
              Market Price
            </span>
          </div>
          <div className="flex items-center gap-2">
            {showFresh && (
              <span className="inline-flex items-center gap-1 rounded-full bg-accent-green/15 text-accent-green border border-accent-green/30 px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider font-bold">
                <span aria-hidden>✓</span>
                Up to date
              </span>
            )}
            <button
              type="button"
              onClick={onRefresh}
              disabled={refreshing}
              title="Pull fresh prices from eBay"
              className="inline-flex items-center gap-1 rounded-full border border-border bg-bg-surface px-2.5 py-1 text-xs font-semibold text-text-secondary hover:border-accent-yellow/60 hover:text-text-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {refreshing ? (
                <>
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Refreshing
                </>
              ) : (
                <>
                  <RefreshCw className="h-3 w-3" />
                  Refresh
                </>
              )}
            </button>
          </div>
        </div>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="font-mono text-4xl font-extrabold tracking-tight text-text-primary">
              {fmt(marketPrice)}
            </div>
            <p className="mt-1 text-xs text-text-tertiary">
              {marketPrice != null
                ? "Consensus across active sources"
                : "No pricing data yet for this card"}
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            {ownedToggle}
            {wishlistButton}
          </div>
        </div>
      </div>

      {/* TCGplayer */}
      <div className="rounded-card border border-border bg-bg-surface p-4">
        <div className="flex items-center gap-2 mb-3">
          <div className="h-7 w-7 rounded-btn bg-accent-yellow/15 flex items-center justify-center">
            <ShoppingCart
              className="h-3.5 w-3.5 text-accent-yellow"
              aria-hidden
            />
          </div>
          <div className="flex flex-col">
            <span className="font-mono text-[11px] uppercase tracking-wider text-text-tertiary font-semibold">
              TCGplayer
            </span>
            <span className="font-mono text-[9px] uppercase tracking-wider text-text-tertiary/70">
              Market
            </span>
          </div>
        </div>
        <div className="font-mono text-2xl font-bold text-text-primary">
          {fmt(displayedTcg)}
        </div>
        {displayedTcg != null ? (
          <a
            href={tcgUrl}
            target="_blank"
            rel="noopener noreferrer sponsored"
            className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-teal-600 dark:text-teal-300 hover:text-teal-500 transition-colors"
          >
            Buy on TCGplayer
            <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
            {AFFILIATE_ENABLED && (
              <span
                className="rounded-sm bg-text-tertiary/15 px-1 py-0.5 text-[9px] font-mono uppercase tracking-wider text-text-tertiary"
                title="Affiliate link — PullList may earn a commission"
              >
                Ad
              </span>
            )}
          </a>
        ) : (
          <p className="mt-3 text-xs text-text-tertiary">
            Pricing not yet available
          </p>
        )}
      </div>

      {/* eBay */}
      <div className="rounded-card border border-border bg-bg-surface p-4">
        <div className="flex items-center gap-2 mb-3">
          <div className="h-7 w-7 rounded-btn bg-teal-400/15 flex items-center justify-center">
            <Tag
              className="h-3.5 w-3.5 text-teal-500 dark:text-teal-300"
              aria-hidden
            />
          </div>
          <div className="flex flex-col">
            <span className="font-mono text-[11px] uppercase tracking-wider text-text-tertiary font-semibold">
              eBay
            </span>
            <span className="font-mono text-[9px] uppercase tracking-wider text-text-tertiary/70">
              Median
            </span>
          </div>
        </div>
        <div className="font-mono text-2xl font-bold text-text-primary">
          {fmt(displayedEbay)}
        </div>
        {displayedEbay != null ? (
          <a
            href={ebayUrl}
            target="_blank"
            rel="noopener noreferrer sponsored"
            className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-teal-600 dark:text-teal-300 hover:text-teal-500 transition-colors"
          >
            Buy on eBay
            <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
            {AFFILIATE_ENABLED && (
              <span
                className="rounded-sm bg-text-tertiary/15 px-1 py-0.5 text-[9px] font-mono uppercase tracking-wider text-text-tertiary"
                title="Affiliate link — PullList may earn a commission"
              >
                Ad
              </span>
            )}
          </a>
        ) : (
          <p className="mt-3 text-xs text-text-tertiary">No active listings</p>
        )}
      </div>
    </div>
  );
}
