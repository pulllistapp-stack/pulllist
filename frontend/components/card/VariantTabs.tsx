"use client";

import { cn } from "@/lib/utils";
import type { CardVariant } from "@/lib/auth";
import { VARIANT_LABELS } from "@/lib/variant";

type Props = {
  variants: CardVariant[];
  selected: CardVariant;
  onChange: (variant: CardVariant) => void;
  className?: string;
};

/**
 * Pill-row of print variants for a card. Only renders when the card
 * has more than one variant with pricing — single-variant cards (JP
 * imports, some modern commons) don't need the picker. Mirrors the
 * region tabs visual language so it reads as a meta-selector.
 */
export function VariantTabs({
  variants,
  selected,
  onChange,
  className,
}: Props) {
  if (variants.length < 2) return null;
  return (
    <div
      role="tablist"
      aria-label="Print variant"
      className={cn(
        "inline-flex rounded-full border border-border bg-bg-surface p-1",
        className,
      )}
    >
      {variants.map((v) => {
        const active = v === selected;
        return (
          <button
            key={v}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(v)}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-semibold transition-colors",
              active
                ? "bg-bg-elevated text-text-primary shadow-sm"
                : "text-text-secondary hover:text-text-primary",
            )}
          >
            {VARIANT_LABELS[v] ?? v}
          </button>
        );
      })}
    </div>
  );
}
