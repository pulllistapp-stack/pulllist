/**
 * Build precise external search URLs that pinpoint a specific card variant
 * rather than every card sharing the same Pokémon name.
 *
 * eBay sellers virtually always include the X/YYY card number in their titles
 * — using it dramatically tightens the result set. Set name + ptcgo_code adds
 * a final layer of disambiguation for sets with reprints (e.g. multiple "151"
 * sub-sets) and promo cards.
 */

export type SearchContext = {
  cardName: string;
  cardNumber: string | null;
  setName: string | null;
  setPrintedTotal: number | null;
  setPtcgoCode: string | null;
};

const PROMO_KEYWORDS = ["promo", "promos", "black star"];

function isPromoSet(setName: string | null): boolean {
  if (!setName) return false;
  const lower = setName.toLowerCase();
  return PROMO_KEYWORDS.some((kw) => lower.includes(kw));
}

function buildNumberPart(ctx: SearchContext): string | null {
  if (!ctx.cardNumber) return null;
  // Skip pure-numeric padding for promo-style codes (TG01, SWSH066, RC10, …).
  // For those, eBay sellers reuse the literal code, so leave it alone.
  if (!/^\d+$/.test(ctx.cardNumber)) {
    return ctx.cardNumber;
  }
  if (ctx.setPrintedTotal) {
    // eBay seller convention: pad BOTH sides to the same width.
    // "52" + "215" → "052/215"; "121" + "88" → "121/088".
    const numStr = ctx.cardNumber;
    const totalStr = String(ctx.setPrintedTotal);
    const padLength = Math.max(numStr.length, totalStr.length, 2);
    return `${numStr.padStart(padLength, "0")}/${totalStr.padStart(padLength, "0")}`;
  }
  return ctx.cardNumber;
}

export function buildSearchTerms(ctx: SearchContext): string {
  const parts: string[] = [`"${ctx.cardName}"`];

  const numberPart = buildNumberPart(ctx);
  if (numberPart) parts.push(numberPart);

  // For promo sets, prefer the short code if available — sellers commonly
  // write "SVP 052" rather than "Scarlet & Violet Black Star Promos 052".
  if (isPromoSet(ctx.setName) && ctx.setPtcgoCode) {
    parts.push(ctx.setPtcgoCode);
  } else if (ctx.setName) {
    parts.push(ctx.setName);
  }

  return parts.join(" ");
}

export function tcgplayerSearchUrl(ctx: SearchContext): string {
  const q = encodeURIComponent(buildSearchTerms(ctx));
  return `https://www.tcgplayer.com/search/pokemon/product?productLineName=pokemon&q=${q}`;
}

export function ebaySoldUrl(ctx: SearchContext): string {
  const q = encodeURIComponent(buildSearchTerms(ctx));
  // _sacat=183454 = Trading Card Games > Pokémon TCG Individual Cards
  // LH_Sold + LH_Complete = sold listings only
  return `https://www.ebay.com/sch/i.html?_nkw=${q}&_sacat=183454&LH_Sold=1&LH_Complete=1`;
}

export function ebayActiveUrl(ctx: SearchContext): string {
  const q = encodeURIComponent(buildSearchTerms(ctx));
  return `https://www.ebay.com/sch/i.html?_nkw=${q}&_sacat=183454`;
}
