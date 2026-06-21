/**
 * Per-variant pricing helpers + display labels.
 *
 * Mirrors backend/app/services/variant_pricing.py — the card detail
 * page and Add-to-collection modal need to know which variants this
 * card actually has prices for, and what to display for each tab.
 */
import type { CardVariant } from "@/lib/auth";

/** Type guard for a TCGplayer-style prices block. */
type VariantBlock = {
  market?: number | null;
  mid?: number | null;
  low?: number | null;
  high?: number | null;
};

type TcgPlayerPrices = Partial<Record<CardVariant, VariantBlock>>;

const FALLBACK_ORDER: CardVariant[] = [
  "normal",
  "holofoil",
  "reverseHolofoil",
  "1stEditionHolofoil",
  "1stEdition",
  "unlimitedHolofoil",
  "unlimited",
];

/** Short human label per variant — what tab buttons show. */
export const VARIANT_LABELS: Record<CardVariant, string> = {
  normal: "Normal",
  holofoil: "Holo",
  reverseHolofoil: "Reverse Holo",
  "1stEdition": "1st Ed",
  "1stEditionHolofoil": "1st Ed Holo",
  unlimited: "Unlimited",
  unlimitedHolofoil: "Unlimited Holo",
};

/** Return the market price for a variant from a TCGplayer prices block.
 *  Falls back through the priority order, then to a denormalized
 *  card-level price if provided. Returns null when no source has data.
 */
export function priceForVariant(
  prices: unknown,
  variant: CardVariant | null | undefined,
  fallbackMarketPrice?: number | null,
): number | null {
  if (prices && typeof prices === "object") {
    const p = prices as TcgPlayerPrices;

    const tryKey = (k: CardVariant): number | null => {
      const v = p[k];
      if (!v) return null;
      const m = v.market ?? v.mid;
      return typeof m === "number" && m > 0 ? m : null;
    };

    if (variant) {
      const direct = tryKey(variant);
      if (direct != null) return direct;
    }
    for (const k of FALLBACK_ORDER) {
      if (k === variant) continue;
      const v = tryKey(k);
      if (v != null) return v;
    }
  }
  return fallbackMarketPrice ?? null;
}

/** Which variants actually have a market price for this card. Used to
 *  decide which variant tabs to render — there's no point showing a
 *  "1st Edition" tab for a modern SV card. */
export function availableVariants(prices: unknown): CardVariant[] {
  if (!prices || typeof prices !== "object") return [];
  const p = prices as TcgPlayerPrices;
  const out: CardVariant[] = [];
  for (const k of FALLBACK_ORDER) {
    const v = p[k];
    if (!v) continue;
    const m = v.market ?? v.mid;
    if (typeof m === "number" && m > 0) out.push(k);
  }
  return out;
}
