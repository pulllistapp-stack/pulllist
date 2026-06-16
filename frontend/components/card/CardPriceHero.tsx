"use client";

import { ArrowUpRight, ShoppingCart, Star, Tag } from "lucide-react";

import type { Card } from "@/lib/api";

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
  // Simple average when both sources have data; fall back to whichever exists.
  // (Volume-weighted blend is a future improvement once Card.snapshot_count is wired.)
  const marketPrice =
    tcgMarket != null && ebayMedian != null
      ? (tcgMarket + ebayMedian) / 2
      : (tcgMarket ?? ebayMedian);

  const tcgUrl =
    card.tcgplayer_url ??
    `https://www.tcgplayer.com/search/pokemon/product?q=${encodeURIComponent(card.name)}`;
  const ebayUrl = buildEbayUrl(card);

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {/* Market Price — hero, spans full width */}
      <div className="sm:col-span-2 relative overflow-hidden rounded-card border-2 border-accent-yellow/70 bg-bg-surface p-5">
        <div className="flex items-center gap-2 mb-3">
          <Star
            className="h-4 w-4 fill-accent-yellow text-accent-yellow"
            aria-hidden
          />
          <span className="font-mono text-[11px] uppercase tracking-wider text-text-tertiary font-semibold">
            Market Price
          </span>
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
          {fmt(tcgMarket)}
        </div>
        {tcgMarket != null ? (
          <a
            href={tcgUrl}
            target="_blank"
            rel="noopener noreferrer sponsored"
            className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-teal-600 dark:text-teal-300 hover:text-teal-500 transition-colors"
          >
            Buy on TCGplayer
            <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
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
          {fmt(ebayMedian)}
        </div>
        {ebayMedian != null ? (
          <a
            href={ebayUrl}
            target="_blank"
            rel="noopener noreferrer sponsored"
            className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-teal-600 dark:text-teal-300 hover:text-teal-500 transition-colors"
          >
            Buy on eBay
            <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
          </a>
        ) : (
          <p className="mt-3 text-xs text-text-tertiary">No active listings</p>
        )}
      </div>
    </div>
  );
}
