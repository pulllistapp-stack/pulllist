/**
 * JP series name → English era label.
 *
 * The /sets browser groups by `Set.series` which is whatever the
 * upstream catalog stored (Japanese for JP-primary sets, English for
 * EN-primary). We append an English label in parentheses so users
 * who don't read Japanese can still recognize "Mega era" /
 * "Scarlet & Violet" / etc. at a glance.
 *
 * Map covers JP series names actually present in our DB (see
 * SELECT DISTINCT series FROM sets WHERE language='ja'). Anything
 * unmapped falls through unchanged.
 */
const JP_SERIES_EN: Record<string, string> = {
  "ポケモンカードゲーム MEGA": "Mega",
  "ポケモンカードゲーム スカーレット&バイオレット": "Scarlet & Violet",
  "プロモカード": "Promos",
  "剣と盾": "Sword & Shield",
  "サン&ムーン": "Sun & Moon",
  "XY BREAK": "XY BREAK",
  "XY": "XY",
  "PCG": "EX-era",
  "ポケモンカードe": "e-Card",
  "web": "Web",
  "VS": "VS",
  "ポケットモンスターカードゲーム": "WoTC-era",
};

/**
 * Return the display label for a series, e.g.
 *   "ポケモンカードゲーム MEGA" → "ポケモンカードゲーム MEGA (Mega)"
 *   "Sword & Shield"            → "Sword & Shield"  (no append)
 *   null / "Other"              → "Other"
 */
export function seriesLabel(series: string | null | undefined): string {
  if (!series) return "Other";
  const en = JP_SERIES_EN[series];
  // Skip the suffix when the JP name already equals (or contains) the
  // EN label — avoids "XY (XY)" / "VS (VS)" / "Sword & Shield (Sword & Shield)".
  if (!en) return series;
  if (series === en || series.includes(en)) return series;
  return `${series} (${en})`;
}
