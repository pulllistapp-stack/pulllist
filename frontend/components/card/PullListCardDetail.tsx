"use client";

import Image from "next/image";
import Link from "next/link";
import { useMemo, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Search,
  ShoppingCart,
  Star,
} from "lucide-react";

import {
  bestTcgPlayerUrl,
  wrapEbayUrl,
  wrapTcgPlayerUrl,
} from "@/lib/affiliate";

import { CardPriceChart } from "@/components/card/CardPriceChart";
import { CardPriceHero } from "@/components/card/CardPriceHero";
import { ImageMagnifier } from "@/components/card/ImageMagnifier";
import { LiveListings } from "@/components/card/LiveListings";
import { MascotMark } from "@/components/card/Mascot";
import { VariantTabs } from "@/components/card/VariantTabs";
import type { CardVariant } from "@/lib/auth";
import {
  availableVariants,
  priceForVariant,
} from "@/lib/variant";
import { OwnedToggle } from "@/components/OwnedToggle";
import { RarityChip } from "@/components/RarityChip";
import { WishlistHeart } from "@/components/WishlistHeart";
import { type Card, type CardNeighbors } from "@/lib/api";
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
/* ============================================================
   Inline chart was extracted to ./CardPriceChart (with band, hover
   tooltip, and range bucketing). Cheapest-listing hero, source badge,
   delta pill, sparkline + secondary-prices grid were superseded by
   ./CardPriceHero. Theme toggle now lives only in the global TopNav.
   ============================================================ */
// PriceChart inline component removed — now lives in ./CardPriceChart with
// low/high lines + Kream-style hover tooltip + range bucketing.

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
  ebaySpark7d: number[];
  tcgSpark7d: number[];
};

export function PullListCardDetail({
  card,
  alternates,
  neighbors,
  initialEbayMedian,
  ebayDelta7d,
  tcgDelta7d,
  ebaySpark7d,
  tcgSpark7d,
}: Props) {
  // Derive cheapest from available price data (used by the sticky mobile CTA).
  const cheapest: { price: number; source: "TCGplayer" | "eBay"; url: string } | null = useMemo(() => {
    const candidates: { price: number; source: "TCGplayer" | "eBay"; url: string }[] = [];
    if (card.tcgplayer_prices) {
      for (const variant of Object.values(card.tcgplayer_prices)) {
        const low = variant?.low;
        if (typeof low === "number" && low > 0) {
          candidates.push({
            price: low,
            source: "TCGplayer",
            url: wrapTcgPlayerUrl(
              bestTcgPlayerUrl({
                productId: card.tcgplayer_product_id,
                cardName: card.name,
                cardNumber: card.number,
              }),
            ),
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
        url: wrapEbayUrl(
          `https://www.ebay.com/sch/i.html?_nkw=${encodeURIComponent(q)}&LH_BIN=1`,
        ),
      });
    }
    if (!candidates.length) return null;
    return candidates.sort((a, b) => a.price - b.price)[0];
  }, [card, initialEbayMedian]);

  // Which TCGplayer print variants does this card actually have data
  // for? Modern SV commons usually ship {normal, reverseHolofoil};
  // vintage WotC ships {holofoil} or {1stEditionHolofoil, unlimited}.
  // The variant tabs only show the ones we have, so the user never
  // sees a "1st Edition" tab on a SV-era release.
  const variants: CardVariant[] = useMemo(
    () => availableVariants(card.tcgplayer_prices),
    [card.tcgplayer_prices],
  );
  const [selectedVariant, setSelectedVariant] = useState<CardVariant>(
    variants[0] ?? "normal",
  );

  // tcgMid for the selected variant. Hero updates when the user clicks
  // a different tab. Falls back to the card-level denormalized price
  // if the variant has no data (e.g. JP cards where we only ever store
  // one price).
  const tcgMid = useMemo(
    () =>
      priceForVariant(
        card.tcgplayer_prices,
        selectedVariant,
        card.market_price_usd,
      ),
    [card.tcgplayer_prices, selectedVariant, card.market_price_usd],
  );

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
                // dark mode: dedicated teal-tinted glow so the card visibly floats on the dark bg
                "dark:border-[#2D3543] dark:bg-[#1A1F29] dark:shadow-[0_20px_50px_-12px_rgba(91,201,194,0.18),0_8px_20px_-6px_rgba(0,0,0,0.6)]",
                // extra glow for rare cards
                card.rarity?.toLowerCase().includes("rare") &&
                  "dark:ring-2 dark:ring-teal-400/40 dark:shadow-[0_20px_50px_-12px_rgba(91,201,194,0.4),0_0_40px_-6px_rgba(91,201,194,0.5)]",
                // tilt-on-hover (3D-ish using rotateY + slight rotateX + scale)
                "group-hover:[transform:perspective(1000px)_rotateY(8deg)_rotateX(-3deg)_scale(1.03)]",
                // hover shadows tuned per theme
                "group-hover:shadow-[0_30px_60px_-12px_rgba(0,0,0,0.35),0_15px_30px_-8px_rgba(255,203,5,0.25)]",
                "dark:group-hover:shadow-[0_30px_60px_-12px_rgba(255,203,5,0.25),0_15px_30px_-8px_rgba(91,201,194,0.35)]",
                "dark:group-hover:ring-amber-400/60",
              )}
            >
              {card.image_large ? (
                <ImageMagnifier
                  src={card.image_large}
                  alt={`${card.name} ${card.number ?? ""}`}
                  sizes="(max-width: 1024px) 320px, 360px"
                  className="absolute inset-0"
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

              {/* Twinkling stars — 5 different anchors, alternating amber/mint, staggered delays */}
              <Star
                aria-hidden
                fill="currentColor"
                strokeWidth={0}
                className="pointer-events-none absolute right-[8%] top-[10%] h-5 w-5 text-amber-400 opacity-0 drop-shadow-[0_0_8px_rgba(255,203,5,0.9)] group-hover:[animation:pl-sparkle_2s_ease-in-out_infinite]"
              />
              <Star
                aria-hidden
                fill="currentColor"
                strokeWidth={0}
                className="pointer-events-none absolute left-[12%] top-[28%] h-4 w-4 text-teal-400 opacity-0 drop-shadow-[0_0_8px_rgba(91,201,194,0.9)] group-hover:[animation:pl-sparkle_2s_ease-in-out_infinite_0.35s]"
              />
              <Star
                aria-hidden
                fill="currentColor"
                strokeWidth={0}
                className="pointer-events-none absolute right-[14%] top-[55%] h-3.5 w-3.5 text-amber-300 opacity-0 drop-shadow-[0_0_6px_rgba(255,203,5,0.8)] group-hover:[animation:pl-sparkle_2s_ease-in-out_infinite_0.7s]"
              />
              <Star
                aria-hidden
                fill="currentColor"
                strokeWidth={0}
                className="pointer-events-none absolute left-[18%] bottom-[18%] h-5 w-5 text-teal-300 opacity-0 drop-shadow-[0_0_8px_rgba(91,201,194,0.85)] group-hover:[animation:pl-sparkle_2s_ease-in-out_infinite_1.05s]"
              />
              <Star
                aria-hidden
                fill="currentColor"
                strokeWidth={0}
                className="pointer-events-none absolute right-[22%] bottom-[8%] h-4 w-4 text-amber-200 opacity-0 drop-shadow-[0_0_6px_rgba(255,203,5,0.7)] group-hover:[animation:pl-sparkle_2s_ease-in-out_infinite_1.4s]"
              />
            </div>
          </div>

          <div className="flex flex-col gap-5">
            <div className="min-w-0">
              <h1 className={cn("text-balance text-2xl font-extrabold tracking-tight lg:text-4xl", heading)}>
                {card.name}
              </h1>
              <p className={cn("mt-1 text-sm", muted)}>
                {card.number ?? "—"} · {card.set_name ?? card.set_id}
              </p>
            </div>

            <div className="flex flex-wrap gap-1.5">
              {card.rarity && <RarityChip rarity={card.rarity} size="md" />}
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

            {variants.length > 1 && (
              <div className="mb-3">
                <VariantTabs
                  variants={variants}
                  selected={selectedVariant}
                  onChange={setSelectedVariant}
                />
              </div>
            )}

            <CardPriceHero
              card={card}
              tcgMarket={tcgMid}
              ebayMedian={initialEbayMedian}
              ownedToggle={
                <OwnedToggle
                  cardId={card.id}
                  variant="hero"
                  printVariant={selectedVariant}
                  card={card}
                />
              }
              wishlistButton={
                <WishlistHeart
                  cardId={card.id}
                  variant="inline"
                  printVariant={selectedVariant}
                />
              }
            />
          </div>
        </div>

        {/* Price chart */}
        <CardPriceChart
          cardId={card.id}
          isOnFire={Math.max(ebayDelta7d ?? 0, tcgDelta7d ?? 0) >= 10}
        />

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
