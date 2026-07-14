"use client";

import Image from "next/image";
import Link from "next/link";

import type { Card } from "@/lib/api";

import { useCollection } from "./CollectionProvider";
import { RarityChip } from "./RarityChip";
import { WishlistHeart } from "./WishlistHeart";

type Props = {
  card: Card;
  priority?: boolean;
};

function fmtPriceTag(price: number | null | undefined): string | null {
  if (price == null) return null;
  if (price >= 10000) return `$${(price / 1000).toFixed(1)}k`;
  if (price >= 1000) return `$${(price / 1000).toFixed(2)}k`;
  return `$${price.toFixed(2)}`;
}

/**
 * Does this card have a reverse-holo variant on TCGplayer? Reverse
 * holos share the card id but sell as a distinct SKU, so surfacing
 * the fact on the grid tile saves users a click to figure out whether
 * they need to hunt down a second copy.
 *
 * Heuristic: `tcgplayer_prices` contains a `reverseHolofoil` key with
 * ANY price signal (market / mid / low / high). Cards that only carry
 * a `normal` or `holofoil` entry return false. First-edition + shiny
 * vault variants get skipped by design — those are separate cards in
 * our catalog, not variants of the same id.
 */
function hasReverseHoloVariant(card: Card): boolean {
  const prices = card.tcgplayer_prices?.reverseHolofoil;
  if (!prices) return false;
  return (
    prices.market != null ||
    prices.mid != null ||
    prices.low != null ||
    prices.high != null
  );
}

export function CardThumb({ card, priority = false }: Props) {
  const { has } = useCollection();
  const owned = has(card.id);
  const priceLabel = fmtPriceTag(card.market_price_usd);
  const hasReverseHolo = hasReverseHoloVariant(card);

  return (
    <Link
      href={`/cards/${card.id}`}
      className={`group relative flex flex-col rounded-card border p-2 transition-all duration-200 ${
        owned
          ? "bg-accent-green/5 border-accent-green/30 hover:border-accent-green/60"
          : "bg-bg-surface border-border hover:border-accent-yellow/40 hover:shadow-md hover:shadow-accent-yellow/10"
      }`}
    >
      <div className="relative aspect-[245/342] w-full overflow-hidden rounded-md bg-bg">
        {card.image_small ? (
          <Image
            src={card.image_small}
            alt={card.name}
            fill
            sizes="(max-width: 768px) 33vw, 200px"
            className="object-contain group-hover:scale-[1.03] transition-transform duration-300"
            unoptimized
            priority={priority}
            loading={priority ? "eager" : "lazy"}
          />
        ) : (
          // Vintage JP catalog (PMCG-era, late 90s sets) has no image data
          // upstream from TCGdex - render a styled card-back instead of bare
          // "no image" text so the grid stays visually consistent.
          <div className="flex h-full flex-col items-center justify-center gap-1 p-3 text-center bg-gradient-to-br from-bg/40 to-accent-yellow/[0.06] border border-dashed border-border/50">
            <span className="font-bold text-sm text-text-primary/80 leading-tight line-clamp-3">
              {card.name}
            </span>
            <span className="font-mono text-[10px] uppercase tracking-wider text-text-tertiary mt-1">
              No artwork
            </span>
          </div>
        )}

        {/* Owned indicator stays as a tiny corner badge — doesn't cover artwork */}
        {owned && (
          <span
            className="absolute top-1.5 left-1.5 inline-flex items-center justify-center w-5 h-5 rounded-full bg-accent-green text-bg text-xs font-bold shadow-md ring-1 ring-emerald-700/20"
            title="In your collection"
          >
            ✓
          </span>
        )}

        {/* Wishlist heart — opposite corner from the owned badge */}
        <div className="absolute top-1.5 right-1.5">
          <WishlistHeart cardId={card.id} variant="corner" />
        </div>

        {/* Reverse-holo indicator — continuous shine + "RH" chip on
            the bottom edge so browsers can spot RH-eligible cards
            without opening the detail page. Purely visual overlay;
            doesn't block clicks (pointer-events: none). */}
        {hasReverseHolo && (
          <>
            <span
              aria-hidden
              className="pointer-events-none absolute inset-0 overflow-hidden rounded-md"
            >
              <span className="reverse-holo-shine" />
            </span>
            <span
              className="absolute bottom-1.5 right-1.5 rounded-full bg-gradient-to-br from-cyan-300 via-fuchsia-300 to-yellow-200 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-gray-900 shadow-md shadow-fuchsia-500/20 ring-1 ring-white/30"
              title="Reverse Holo variant available"
            >
              RH
            </span>
          </>
        )}
      </div>

      <div className="mt-2 px-1 flex flex-col gap-1">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-mono text-text-tertiary">
            #{card.number ?? "—"}
          </span>
          {priceLabel && (
            <span className="font-mono text-xs font-bold text-accent-yellow">
              {priceLabel}
            </span>
          )}
        </div>
        <div className="text-sm font-medium truncate" title={card.name}>
          {card.name}
        </div>
        <RarityChip rarity={card.rarity} />
      </div>
    </Link>
  );
}
