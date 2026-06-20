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

export function CardThumb({ card, priority = false }: Props) {
  const { has } = useCollection();
  const owned = has(card.id);
  const priceLabel = fmtPriceTag(card.market_price_usd);

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
