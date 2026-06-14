/**
 * Pokémon TCG rarity → visual tier classification.
 *
 * Shared by FilterSidebar (chips), TrendingPage (mover rows), and any other
 * surface that needs to color-code a rarity string. Single source of truth so
 * the visual language is consistent.
 */

export type RarityTier =
  | "common"
  | "uncommon"
  | "rare"
  | "holo"
  | "ultra"
  | "illustration"
  | "sir"
  | "mega"
  | "hyper"
  | "shiny"
  | "secret"
  | "promo"
  | "ace"
  | "other";

export function rarityTier(rarity: string): RarityTier {
  const n = rarity.toLowerCase();
  if (rarity === "Common") return "common";
  if (rarity === "Uncommon") return "uncommon";
  if (rarity === "Rare") return "rare";
  if (n.includes("special illustration")) return "sir";
  if (n.includes("illustration")) return "illustration";
  if (n.includes("mega")) return "mega";
  if (n.includes("hyper") || n.includes("rainbow")) return "hyper";
  if (n.includes("shiny") || n.includes("radiant") || n.includes("amazing"))
    return "shiny";
  if (n.includes("secret")) return "secret";
  if (n.includes("promo") || n.includes("classic")) return "promo";
  if (
    n.includes("ace spec") ||
    n.includes("legend") ||
    n.includes("rare ace") ||
    n.includes("break") ||
    n.includes("prism") ||
    n.includes("prime") ||
    n.includes("lv.x") ||
    n.includes("shining")
  )
    return "ace";
  if (/(ex|gx|\bv\b|vmax|vstar|ultra|double)/i.test(rarity)) return "ultra";
  if (n.includes("holo")) return "holo";
  return "other";
}

export const RARITY_CHIP_INACTIVE: Record<RarityTier, string> = {
  common:
    "bg-bg-surface text-gray-500 dark:text-gray-400 border border-gray-300/60 dark:border-gray-600/40 hover:border-gray-400",
  uncommon:
    "bg-bg-surface text-emerald-600 dark:text-emerald-400 border border-emerald-400/30 hover:border-emerald-400/60",
  rare:
    "bg-bg-surface text-sky-600 dark:text-sky-400 border border-sky-400/30 hover:border-sky-400/60",
  holo:
    "bg-bg-surface text-indigo-600 dark:text-indigo-400 border border-indigo-400/30 hover:border-indigo-400/60",
  ultra:
    "bg-bg-surface text-violet-600 dark:text-violet-300 border border-violet-400/30 hover:border-violet-400/60",
  illustration:
    "bg-bg-surface text-pink-600 dark:text-pink-300 border border-pink-400/30 hover:border-pink-400/60",
  sir:
    "bg-gradient-to-r from-fuchsia-100/40 via-amber-100/40 to-teal-100/40 dark:from-fuchsia-900/10 dark:via-amber-900/10 dark:to-teal-900/10 text-fuchsia-700 dark:text-fuchsia-300 border border-fuchsia-400/40 hover:border-fuchsia-400/70",
  mega:
    "bg-gradient-to-r from-purple-100/40 via-red-100/40 to-amber-100/40 dark:from-purple-900/10 dark:via-red-900/10 dark:to-amber-900/10 text-red-700 dark:text-red-300 border border-red-400/40 hover:border-red-400/70",
  hyper:
    "bg-bg-surface text-amber-600 dark:text-amber-300 border border-amber-400/40 hover:border-amber-400/70",
  shiny:
    "bg-bg-surface text-cyan-600 dark:text-cyan-300 border border-cyan-400/30 hover:border-cyan-400/60",
  secret:
    "bg-bg-surface text-yellow-600 dark:text-yellow-300 border border-yellow-400/30 hover:border-yellow-400/60",
  promo:
    "bg-bg-surface text-orange-600 dark:text-orange-300 border border-orange-400/30 hover:border-orange-400/60",
  ace:
    "bg-bg-surface text-rose-600 dark:text-rose-300 border border-rose-400/30 hover:border-rose-400/60",
  other:
    "bg-bg-surface text-text-secondary border border-border hover:border-accent-yellow/40",
};

export const RARITY_CHIP_ACTIVE: Record<RarityTier, string> = {
  common: "bg-gray-500 text-white border border-gray-500",
  uncommon: "bg-emerald-500 text-white border border-emerald-500 shadow-sm shadow-emerald-500/30",
  rare: "bg-sky-500 text-white border border-sky-500 shadow-sm shadow-sky-500/30",
  holo: "bg-indigo-500 text-white border border-indigo-500 shadow-sm shadow-indigo-500/30",
  ultra: "bg-violet-500 text-white border border-violet-500 shadow-sm shadow-violet-500/30",
  illustration: "bg-pink-500 text-white border border-pink-500 shadow-sm shadow-pink-500/30",
  sir: "bg-gradient-to-r from-fuchsia-500 via-amber-400 to-teal-400 text-white border border-fuchsia-500/60 shadow-md shadow-fuchsia-500/40",
  mega: "bg-gradient-to-r from-purple-600 via-red-500 to-amber-500 text-white border border-red-500/60 shadow-md shadow-red-500/40",
  hyper: "bg-gradient-to-r from-amber-400 via-rose-400 to-violet-400 text-white border border-amber-500/60 shadow-md shadow-amber-500/40",
  shiny: "bg-cyan-500 text-white border border-cyan-500 shadow-sm shadow-cyan-500/30",
  secret: "bg-yellow-500 text-gray-900 border border-yellow-500 shadow-sm shadow-yellow-500/30",
  promo: "bg-orange-500 text-white border border-orange-500 shadow-sm shadow-orange-500/30",
  ace: "bg-rose-500 text-white border border-rose-500 shadow-sm shadow-rose-500/30",
  other: "bg-accent-yellow/15 text-accent-yellow border border-accent-yellow/30",
};

export function rarityChipClass(rarity: string, active: boolean): string {
  const tier = rarityTier(rarity);
  return active ? RARITY_CHIP_ACTIVE[tier] : RARITY_CHIP_INACTIVE[tier];
}
