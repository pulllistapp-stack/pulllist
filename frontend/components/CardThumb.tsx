"use client";

import Image from "next/image";
import Link from "next/link";

import type { Card } from "@/lib/api";

import { useCollection } from "./CollectionProvider";
import { RarityChip } from "./RarityChip";

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
          <div className="flex h-full items-center justify-center text-text-tertiary text-xs">
            no image
          </div>
        )}

        {/* Corner price tag — Variant-style amber pill overlaying the art */}
        {priceLabel && (
          <span className="absolute top-1.5 right-1.5 rounded-full bg-accent-yellow px-2 py-0.5 shadow-md ring-1 ring-amber-700/20">
            <span className="font-mono text-[11px] font-bold text-amber-950 leading-none">
              {priceLabel}
            </span>
          </span>
        )}

        {/* Owned indicator — moved to top-left to clear room for price tag */}
        {owned && (
          <span
            className="absolute top-1.5 left-1.5 inline-flex items-center justify-center w-5 h-5 rounded-full bg-accent-green text-bg text-xs font-bold shadow-md ring-1 ring-emerald-700/20"
            title="In your collection"
          >
            ✓
          </span>
        )}
      </div>

      <div className="mt-2 px-1 flex flex-col gap-1">
        <div className="text-xs font-mono text-text-tertiary">
          #{card.number ?? "—"}
        </div>
        <div className="text-sm font-medium truncate" title={card.name}>
          {card.name}
        </div>
        <RarityChip rarity={card.rarity} />
      </div>
    </Link>
  );
}
