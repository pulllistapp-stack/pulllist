import type { MetadataRoute } from "next";

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, "") ?? "https://pulllist.org";
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "https://api.pulllist.org/api/v1";

type SetLite = { id: string; release_date?: string | null };

/**
 * Generated dynamically at build (and every revalidate window) so new sets
 * land in the sitemap as soon as the backend serves them. We deliberately
 * don't enumerate every card - 12k card URLs would inflate the sitemap and
 * slow crawls without lifting indexed page count meaningfully; the set
 * pages already link to every card and Google follows them.
 */
// 86400 = 60 * 60 * 24, but Next.js 16's segment-config validator wants a
// literal here, not an expression — using the math form throws "Invalid
// segment configuration export" at build time.
export const revalidate = 86400; // 1 day

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();

  const staticPages: MetadataRoute.Sitemap = [
    { url: `${SITE_URL}/`, lastModified: now, priority: 1.0 },
    { url: `${SITE_URL}/sets`, lastModified: now, priority: 0.9 },
    { url: `${SITE_URL}/cards`, lastModified: now, priority: 0.8 },
    { url: `${SITE_URL}/trending`, lastModified: now, priority: 0.7 },
    { url: `${SITE_URL}/search`, lastModified: now, priority: 0.5 },
    { url: `${SITE_URL}/login`, lastModified: now, priority: 0.3 },
    { url: `${SITE_URL}/signup`, lastModified: now, priority: 0.3 },
  ];

  // Best-effort set pages. If the API is asleep/down we still serve the
  // static section instead of failing the whole build.
  let setPages: MetadataRoute.Sitemap = [];
  try {
    const res = await fetch(`${API_BASE}/sets`, { next: { revalidate } });
    if (res.ok) {
      const sets = (await res.json()) as SetLite[];
      setPages = sets.map((s) => ({
        url: `${SITE_URL}/sets/${s.id}`,
        // Backend doesn't track per-set updated_at; release_date is the
        // best proxy we have for "when did this content last change".
        lastModified: s.release_date ? new Date(s.release_date) : now,
        priority: 0.6,
      }));
    }
  } catch {
    // swallow - static section is enough to keep crawlers happy
  }

  return [...staticPages, ...setPages];
}
