import type { MetadataRoute } from "next";

// Canonical form is www.pulllist.org (Vercel 308-redirects the apex).
// Emitting non-www URLs in the sitemap forces Google to follow a
// redirect on every entry, which shows up as "Couldn't fetch" errors
// in Search Console.
const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, "") ??
  "https://www.pulllist.org";
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "https://api.pulllist.org/api/v1";

type SetLite = { id: string; release_date?: string | null };
type ProductLite = { id: string; updated_at?: string | null };
type SeriesLite = { slug: string };
type NewsLite = { slug: string; published_at?: string | null };

/**
 * Rebuilt daily. Every published news post, every set page, every product
 * detail, and every series landing goes into the sitemap so Google can
 * find them via a single crawl-queue submission instead of guessing which
 * pages to spider from the home page. Card URLs are intentionally left
 * out — 21k routes would blow crawl budget for pages Google will end up
 * finding via /sets/[id] anyway; when card-page traffic becomes the
 * bottleneck we'll add a chase-only slice ($30+, ~2.7k URLs).
 */
export const revalidate = 86400; // 1 day (60 * 60 * 24)

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();

  const staticPages: MetadataRoute.Sitemap = [
    { url: `${SITE_URL}/`, lastModified: now, priority: 1.0 },
    { url: `${SITE_URL}/sets`, lastModified: now, priority: 0.9 },
    { url: `${SITE_URL}/cards`, lastModified: now, priority: 0.8 },
    { url: `${SITE_URL}/products`, lastModified: now, priority: 0.8 },
    { url: `${SITE_URL}/series`, lastModified: now, priority: 0.7 },
    { url: `${SITE_URL}/news`, lastModified: now, priority: 0.8 },
    { url: `${SITE_URL}/trending`, lastModified: now, priority: 0.7 },
    { url: `${SITE_URL}/drops`, lastModified: now, priority: 0.6 },
    { url: `${SITE_URL}/search`, lastModified: now, priority: 0.5 },
    { url: `${SITE_URL}/pricing`, lastModified: now, priority: 0.4 },
    { url: `${SITE_URL}/login`, lastModified: now, priority: 0.3 },
    { url: `${SITE_URL}/signup`, lastModified: now, priority: 0.3 },
  ];

  const opts = { next: { revalidate } } as const;

  // Backend list endpoints wrap results differently — /sets returns a
  // top-level array, /products and /series return `{items: [...]}`,
  // /news/posts returns a top-level array. `pluck` handles both shapes so
  // one helper covers all four fetches.
  async function pluck<T>(url: string): Promise<T[]> {
    try {
      const r = await fetch(url, opts);
      if (!r.ok) return [];
      const j = await r.json();
      if (Array.isArray(j)) return j as T[];
      if (j && Array.isArray(j.items)) return j.items as T[];
      return [];
    } catch {
      return [];
    }
  }

  // Products endpoint hard-caps page_size at 60 regardless of the limit
  // param, so we paginate through until a short page signals the end.
  // 30 pages is a safety cap so a runaway backend can't drown the build.
  async function pluckPaginated<T>(baseUrl: string, maxPages = 30): Promise<T[]> {
    const all: T[] = [];
    for (let page = 1; page <= maxPages; page++) {
      const batch = await pluck<T>(`${baseUrl}${baseUrl.includes("?") ? "&" : "?"}page=${page}`);
      if (batch.length === 0) break;
      all.push(...batch);
      if (batch.length < 60) break; // last page short-circuit
    }
    return all;
  }

  const [sets, products, series, news] = await Promise.all([
    pluck<SetLite>(`${API_BASE}/sets`),
    pluckPaginated<ProductLite>(`${API_BASE}/products`),
    pluck<SeriesLite>(`${API_BASE}/series`),
    // /news/posts caps limit at 100 (server-side validation, 422s over).
    // Only ~56 published posts today so this covers everything with room.
    pluck<NewsLite>(`${API_BASE}/news/posts?limit=100`),
  ]);

  const setPages = sets.map((s) => ({
    url: `${SITE_URL}/sets/${s.id}`,
    lastModified: s.release_date ? new Date(s.release_date) : now,
    priority: 0.6,
  }));

  const productPages = products.map((p) => ({
    url: `${SITE_URL}/products/${p.id}`,
    lastModified: p.updated_at ? new Date(p.updated_at) : now,
    priority: 0.5,
  }));

  const seriesPages = series.map((s) => ({
    url: `${SITE_URL}/series/${s.slug}`,
    lastModified: now,
    priority: 0.6,
  }));

  // News is our strongest fresh-content signal to Google — priority 0.7
  // matches /trending so daily crawls prioritize it alongside price feeds.
  const newsPages = news.map((n) => ({
    url: `${SITE_URL}/news/${n.slug}`,
    lastModified: n.published_at ? new Date(n.published_at) : now,
    priority: 0.7,
  }));

  return [
    ...staticPages,
    ...setPages,
    ...seriesPages,
    ...newsPages,
    ...productPages,
  ];
}
