import { rarityChipClass } from "@/lib/rarity";

type Props = {
  rarity: string | null | undefined;
  size?: "sm" | "md";
};

/**
 * Decorative rarity label used on card thumbnails, detail headers, and mover
 * rows. Always renders in the "inactive" (label) style of the shared rarity
 * tier system — it's a tag, not an interactive filter chip. Color logic is
 * centralized in `lib/rarity.ts` so the look stays consistent everywhere a
 * rarity appears.
 */
export function RarityChip({ rarity, size = "sm" }: Props) {
  if (!rarity) return null;
  const sizeCls =
    size === "md" ? "text-xs px-2.5 py-1" : "text-[10px] px-1.5 py-0.5";
  return (
    <span
      className={`inline-flex items-center rounded-chip font-mono uppercase tracking-wider ${sizeCls} ${rarityChipClass(
        rarity,
        false,
      )}`}
      title={rarity}
    >
      {rarity}
    </span>
  );
}
