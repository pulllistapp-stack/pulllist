type Props = {
  rarity: string | null | undefined;
  size?: "sm" | "md";
};

const RARITY_COLORS: Record<string, string> = {
  Common: "bg-text-tertiary/20 text-text-secondary",
  Uncommon: "bg-accent-green/15 text-accent-green",
  Rare: "bg-accent-blue/15 text-accent-blue",
  "Rare Holo": "bg-accent-blue/20 text-accent-blue",
  "Rare Holo EX": "bg-accent-yellow/20 text-accent-yellow",
  "Rare Holo GX": "bg-accent-yellow/20 text-accent-yellow",
  "Rare Holo V": "bg-accent-yellow/20 text-accent-yellow",
  "Rare Holo VMAX": "bg-accent-yellow/25 text-accent-yellow",
  "Rare Ultra": "bg-accent-yellow/25 text-accent-yellow",
  "Rare Secret": "bg-accent-red/20 text-accent-red",
  "Rare Rainbow": "bg-accent-red/20 text-accent-red",
  "Illustration Rare": "bg-accent-yellow/25 text-accent-yellow",
  "Special Illustration Rare": "bg-accent-red/20 text-accent-red",
  "Hyper Rare": "bg-accent-red/25 text-accent-red",
  Promo: "bg-text-tertiary/20 text-text-secondary",
};

export function RarityChip({ rarity, size = "sm" }: Props) {
  if (!rarity) return null;
  const cls = RARITY_COLORS[rarity] ?? "bg-text-tertiary/20 text-text-secondary";
  const sizeCls = size === "md" ? "text-xs px-2.5 py-1" : "text-[10px] px-1.5 py-0.5";
  return (
    <span className={`inline-flex items-center rounded-chip font-mono uppercase tracking-wider ${sizeCls} ${cls}`}>
      {rarity}
    </span>
  );
}
