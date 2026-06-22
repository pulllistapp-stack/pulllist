/**
 * News posts now live in the DB and are managed via /admin/news.
 * This module is the typed client + a small label helper shared between
 * the public /news pages and the admin UI.
 */

export type NewsRegion = "all" | "kr" | "ja" | "us";

export type NewsPost = {
  slug: string;
  title: string;
  body: string;
  excerpt: string | null;
  region: NewsRegion;
  category: string | null;
  thumbnail_url: string | null;
  author: string | null;
  published_at: string; // YYYY-MM-DD
  reading_time: number | null;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

export async function fetchPosts(region?: NewsRegion): Promise<NewsPost[]> {
  const qs = region && region !== "all" ? `?region=${region}` : "";
  try {
    const r = await fetch(`${API_BASE}/news/posts${qs}`, {
      cache: "no-store",
    });
    if (!r.ok) return [];
    return (await r.json()) as NewsPost[];
  } catch {
    return [];
  }
}

export async function fetchPost(slug: string): Promise<NewsPost | null> {
  try {
    const r = await fetch(`${API_BASE}/news/posts/${encodeURIComponent(slug)}`, {
      cache: "no-store",
    });
    if (!r.ok) return null;
    return (await r.json()) as NewsPost;
  } catch {
    return null;
  }
}

const REGION_LABELS: Record<NewsRegion, { kr: string; chip: string }> = {
  all: { kr: "전체", chip: "🌐 전체" },
  kr: { kr: "한국", chip: "🇰🇷 한국" },
  ja: { kr: "일본", chip: "🇯🇵 일본" },
  us: { kr: "미국", chip: "🇺🇸 미국" },
};

export function regionLabel(region: NewsRegion): string {
  return REGION_LABELS[region]?.kr ?? region;
}

export function regionChipLabel(region: NewsRegion): string {
  return REGION_LABELS[region]?.chip ?? region;
}
