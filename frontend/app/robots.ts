import type { MetadataRoute } from "next";

// Vercel serves the site from `www.pulllist.org` and 308-redirects the
// apex `pulllist.org`. Point robots.txt + host at the canonical www
// form so Google Search Console doesn't see a redirect on the sitemap
// URL — a redirect there gets flagged as "couldn't fetch."
const CANONICAL_SITE = "https://www.pulllist.org";
const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, "") ?? CANONICAL_SITE;

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
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
