/**
 * Affiliate link wrappers — single source of truth for outbound TCGplayer
 * + eBay URLs. Every Buy-on-X click should run through one of these so
 * trackable commission lands in the right partner program. When the env
 * vars are absent (local dev, or before the IDs are wired) the helpers
 * fall through to the raw URL so the user still ends up on the right
 * page — they just don't earn us commission.
 *
 * Env (set in Vercel for prod, .env.local for dev):
 *   NEXT_PUBLIC_TCGPLAYER_AFFILIATE_PARAMS  — Static query string Impact
 *     attaches to any TCGplayer URL for direct-link tracking. Copy from
 *     the redirect of an Impact "Create a link" short URL, keeping
 *     everything from `irpid=` onward (omit the per-click `irclickid`).
 *     Example value:
 *       irpid=7410135&irgwc=1&afsrc=1&utm_source=impact&utm_medium=affiliate&utm_campaign=pulllist
 *
 *   NEXT_PUBLIC_EBAY_CAMPAIGN_ID            — Numeric EPN campaign id
 *     (e.g. 5339157076). Find in https://partnernetwork.ebay.com →
 *     Campaigns.
 *
 *   NEXT_PUBLIC_EBAY_MKRID                  — Marketplace rotator id.
 *     Defaults to "711-53200-19255-0" (US site).
 */

const TCGPLAYER_PARAMS =
  process.env.NEXT_PUBLIC_TCGPLAYER_AFFILIATE_PARAMS ?? "";
const EBAY_CAMPAIGN_ID = process.env.NEXT_PUBLIC_EBAY_CAMPAIGN_ID ?? "";
const EBAY_MKRID =
  process.env.NEXT_PUBLIC_EBAY_MKRID ?? "711-53200-19255-0";
const EBAY_TOOLID = "10001"; // Standard for Direct Linking / Smart Link

export const TCG_AFFILIATE_ENABLED = TCGPLAYER_PARAMS.length > 0;
export const EBAY_AFFILIATE_ENABLED = EBAY_CAMPAIGN_ID.length > 0;

/** True when at least one affiliate program is wired. UI uses this to
 *  show the "Ad" badge only when commissions are actually being
 *  tracked. */
export const AFFILIATE_ENABLED =
  TCG_AFFILIATE_ENABLED || EBAY_AFFILIATE_ENABLED;

/**
 * Wraps any TCGplayer URL with the Impact direct-link query string so
 * the click is tracked against our partner account. We use Impact's
 * "GoCo" / direct-link model (irpid + irgwc + utm_*) rather than the
 * partner.tcgplayer.com redirect because we have many destinations
 * and don't want to mint a vanity URL per product.
 *
 * Falls through to the raw URL when the env is unset (local dev, or
 * before the params are set in Vercel).
 */
export function wrapTcgPlayerUrl(rawUrl: string): string {
  if (!rawUrl) return rawUrl;
  if (!TCGPLAYER_PARAMS) return rawUrl;
  try {
    const url = new URL(rawUrl);
    // Strip any pre-existing Impact params on the URL so a re-wrap
    // doesn't duplicate them (we own these keys now).
    [
      "irpid",
      "irgwc",
      "afsrc",
      "utm_source",
      "utm_medium",
      "utm_campaign",
      "sharedid",
      "irclickid",
    ].forEach((k) => url.searchParams.delete(k));
    // Append our params. URLSearchParams handles encoding correctly.
    const incoming = new URLSearchParams(TCGPLAYER_PARAMS);
    incoming.forEach((value, key) => {
      url.searchParams.set(key, value);
    });
    return url.toString();
  } catch {
    return rawUrl;
  }
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
