/**
 * Affiliate link wrappers — single source of truth for outbound TCGplayer
 * + eBay URLs. Every Buy-on-X click should run through one of these so
 * trackable commission lands in the right partner program. When the env
 * vars are absent (local dev, or before the IDs are wired) the helpers
 * fall through to the raw URL so the user still ends up on the right
 * page — they just don't earn us commission.
 *
 * Env (set in Vercel for prod, .env.local for dev):
 *   NEXT_PUBLIC_TCGPLAYER_DEEP_LINK   — Impact deep-link prefix. Example
 *     formats Impact uses:
 *       https://tcgplayer.pxf.io/c/<USER_ID>/<CAMPAIGN_ID>/<RANDOM>?u=
 *     or:
 *       https://goto.tcgplayer.com/c/<USER_ID>/<CAMPAIGN_ID>/<RANDOM>?u=
 *     The trailing `?u=` is required — wrapTcgPlayerUrl appends the
 *     URL-encoded target. Find the exact prefix in the Impact dashboard
 *     under "Create a link" or "Tracking Links".
 *
 *   NEXT_PUBLIC_EBAY_CAMPAIGN_ID      — Numeric EPN campaign id (e.g.
 *     5338746789). Find in https://partnernetwork.ebay.com → Campaigns.
 *
 *   NEXT_PUBLIC_EBAY_MKRID            — Marketplace rotator id. Defaults
 *     to "711-53200-19255-0" (US site).
 */

const TCGPLAYER_DEEP_LINK = process.env.NEXT_PUBLIC_TCGPLAYER_DEEP_LINK ?? "";
const EBAY_CAMPAIGN_ID = process.env.NEXT_PUBLIC_EBAY_CAMPAIGN_ID ?? "";
const EBAY_MKRID =
  process.env.NEXT_PUBLIC_EBAY_MKRID ?? "711-53200-19255-0";
const EBAY_TOOLID = "10001"; // Standard for Direct Linking / Smart Link

/** True when both affiliate programs are wired. Used by the UI to show
 *  the FTC disclosure ("Affiliate link") only when commissions are
 *  actually earned. */
export const AFFILIATE_ENABLED =
  TCGPLAYER_DEEP_LINK.length > 0 || EBAY_CAMPAIGN_ID.length > 0;

export const TCG_AFFILIATE_ENABLED = TCGPLAYER_DEEP_LINK.length > 0;
export const EBAY_AFFILIATE_ENABLED = EBAY_CAMPAIGN_ID.length > 0;

/**
 * Wraps any TCGplayer URL with the Impact deep-link prefix so the click
 * is tracked against our partner account. Falls through to the raw URL
 * when the prefix is unset (local dev, or before the deep link is set
 * in Vercel env). The Impact format ends in `?u=` (or sometimes `&u=`)
 * and expects a URL-encoded target.
 */
export function wrapTcgPlayerUrl(rawUrl: string): string {
  if (!rawUrl) return rawUrl;
  if (!TCGPLAYER_DEEP_LINK) return rawUrl;
  return `${TCGPLAYER_DEEP_LINK}${encodeURIComponent(rawUrl)}`;
}

/**
 * Wraps any eBay URL with the EPN Smart Link parameters (campid +
 * toolid + mkrid). Works for both item pages (/itm/...) and search
 * (/sch/...). Re-uses existing query params; replaces ours if present.
 */
export function wrapEbayUrl(rawUrl: string): string {
  if (!rawUrl) return rawUrl;
  if (!EBAY_CAMPAIGN_ID) return rawUrl;
  try {
    const url = new URL(rawUrl);
    url.searchParams.set("campid", EBAY_CAMPAIGN_ID);
    url.searchParams.set("toolid", EBAY_TOOLID);
    url.searchParams.set("mkrid", EBAY_MKRID);
    return url.toString();
  } catch {
    // Malformed URL — return as-is so the user still lands somewhere.
    return rawUrl;
  }
}
