import type { MetadataRoute } from "next";

// Vercel serves the site from `www.pulllist.org` and 308-redirects the
// apex `pulllist.org`. Point robots.txt + host at the canonical www
// form so Google Search Console doesn't see a redirect on the sitemap
// URL — a redirect there gets flagged as "couldn't fetch."
const CANONICAL_SITE = "https://www.pulllist.org";
const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, "") ?? CANONICAL_SITE;

// LLM training / AI answer engines — blocked to keep curated catalog
// content out of training corpora and out of AI answer summaries that
// bypass site visits (AdSense/EPN/Impact revenue depends on real
// visitors clicking through).
const LLM_BOTS = [
  "GPTBot",
  "ChatGPT-User",
  "OAI-SearchBot",
  "ClaudeBot",
  "anthropic-ai",
  "Google-Extended",
  "Applebot-Extended",
  "CCBot",
  "PerplexityBot",
  "Amazonbot",
  "Bytespider",
  "Diffbot",
];

// 3rd-party SEO crawlers — we don't use their dashboards, so their
// crawl budget is a pure infrastructure tax with no return.
const SEO_BOTS = [
  "AhrefsBot",
  "SemrushBot",
  "DotBot",
  "PetalBot",
  "DataForSeoBot",
  "MJ12bot",
  "BLEXBot",
];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        // Behind-auth user surfaces. Public profiles use /p/<token>
        // (non-enumerable) so that path stays crawlable on purpose.
        disallow: ["/me/", "/portfolio", "/wishlist", "/scan", "/api/"],
      },
      // Explicit disallow rules for LLM and 3rd-party SEO crawlers.
      // Policy-respecting bots honor these; non-compliant ones are
      // caught later via visit_logs.bot_name + rate-limit fallbacks.
      ...LLM_BOTS.map((ua) => ({ userAgent: ua, disallow: "/" })),
      ...SEO_BOTS.map((ua) => ({ userAgent: ua, disallow: "/" })),
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
