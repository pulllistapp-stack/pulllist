import type { CardVariant } from "@/lib/auth";

type Props = {
  variant: CardVariant;
  size?: "sm" | "xs";
};

/**
 * Per-variant visual badge.
 *
 * Owners frequently keep the same card in multiple printings — base print
 * plus reverse-holo, or a sealed 1st-edition alongside the unlimited reprint.
 * Without a label the Portfolio and Wishlist rows render identically, so the
 * "do I already have this exact one?" check fails silently. The chip is the
 * smallest unit of disambiguation: short label, colour-coded family, and
 * suppressed entirely for `normal` so the default print stays clutter-free.
 *
 * Reuse: Portfolio vault grid (per row), Wishlist row, future "owned" pill
 * on card thumbnails.
 */
const VARIANT_META: Record<
  Exclude<CardVariant, "normal">,
  { label: string; cls: string }
> = {
  holofoil: {
    label: "Holo",
    cls:
      "bg-gradient-to-r from-fuchsia-500/15 via-amber-500/15 to-teal-500/15 " +
      "text-fuchsia-700 dark:text-fuchsia-300 border-fuchsia-400/40",
  },
  reverseHolofoil: {
    label: "Rev Holo",
    cls:
      "bg-gradient-to-r from-slate-400/15 to-zinc-400/15 " +
      "text-slate-700 dark:text-slate-200 border-slate-400/40",
  },
  "1stEdition": {
    label: "1st Ed",
    cls:
      "bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-400/40",
  },
  "1stEditionHolofoil": {
    label: "1st Ed Holo",
    cls:
      "bg-gradient-to-r from-amber-500/15 via-fuchsia-500/15 to-teal-500/15 " +
      "text-amber-700 dark:text-amber-300 border-amber-400/50",
  },
  unlimited: {
    label: "Unl",
    cls: "bg-zinc-500/10 text-zinc-700 dark:text-zinc-300 border-zinc-400/30",
  },
  unlimitedHolofoil: {
    label: "Unl Holo",
    cls:
      "bg-gradient-to-r from-fuchsia-500/10 via-amber-500/10 to-teal-500/10 " +
      "text-zinc-700 dark:text-zinc-200 border-zinc-400/40",
  },
};

export function VariantChip({ variant, size = "xs" }: Props) {
  // Don't render anything for the default print — would just be noise on
  // every single row.
  if (variant === "normal") return null;
  const meta = VARIANT_META[variant];
  if (!meta) return null;
  const sizeCls =
    size === "xs"
      ? "text-[9px] px-1.5 py-0.5"
      : "text-[10px] px-2 py-0.5";
  return (
    <span
      className={
        "inline-flex items-center rounded-full font-mono font-semibold " +
        "uppercase tracking-wider border " +
        sizeCls +
        " " +
        meta.cls
      }
      title={meta.label}
    >
      {meta.label}
    </span>
  );
}
