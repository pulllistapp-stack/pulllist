import type { MetadataRoute } from "next";

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, "") ?? "https://pulllist.org";

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
