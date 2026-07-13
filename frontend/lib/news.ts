/**
 * News posts live in the DB and are managed via /admin/news. This
 * module is the typed client + label helpers shared between the
 * public /news pages and the admin UI.
 *
 * Category replaces the old region (KR/JP/US) dimension — the audience
 * cares more about WHAT a post is about (drop, market, guide…) than
 * which catalog it covers. Region stays on the DB row for forward
 * flexibility but isn't surfaced in the UI right now.
 */

export type NewsCategory =
  | "drops"
  | "market"
  | "tcg"
  | "center"
  | "guide"
  | "news";

export type NewsStatus = "draft" | "published";

export type NewsPost = {
  slug: string;
  title: string;
  body: string;
  excerpt: string | null;
  region: string;
  category: NewsCategory | string | null;
  thumbnail_url: string | null;
  author: string | null;
  published_at: string; // YYYY-MM-DD
  reading_time: number | null;
  // Optional in TS because legacy callers + the public listing don't
  // depend on them; the API always returns them post-migration.
  status?: NewsStatus;
  source_url?: string | null;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

export const NEWS_PAGE_SIZE = 12;

export async function fetchPosts(
  category?: NewsCategory | "all",
  page: number = 1,
): Promise<NewsPost[]> {
  const params = new URLSearchParams();
  if (category && category !== "all") params.set("category", category);
  params.set("limit", String(NEWS_PAGE_SIZE));
  params.set("offset", String((Math.max(1, page) - 1) * NEWS_PAGE_SIZE));
  try {
    const r = await fetch(`${API_BASE}/news/posts?${params}`, {
      cache: "no-store",
    });
    if (!r.ok) return [];
    return (await r.json()) as NewsPost[];
  } catch {
    return [];
  }
}

/**
 * Admin-only — includes drafts. Sends the bearer token so the API can
 * authorise the include_drafts toggle; without the token the endpoint
 * silently strips drafts (it does NOT 403), so a missing token here
 * means the admin sees a partial list instead of a hard failure.
 */
export async function fetchPostsAdmin(token: string): Promise<NewsPost[]> {
  try {
    const r = await fetch(`${API_BASE}/news/posts?include_drafts=true`, {
      cache: "no-store",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!r.ok) return [];
    return (await r.json()) as NewsPost[];
  } catch {
    return [];
  }
}

export async function fetchPost(
  slug: string,
  token?: string,
): Promise<NewsPost | null> {
  // Pass token when present so admin callers can preview drafts —
  // the public /news/{slug} page never has one (server component, no
  // browser localStorage), so it stays on the published-only path.
  try {
    const r = await fetch(`${API_BASE}/news/posts/${encodeURIComponent(slug)}`, {
      cache: "no-store",
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    if (!r.ok) return null;
    return (await r.json()) as NewsPost;
  } catch {
    return null;
  }
}

export const CATEGORIES: { key: NewsCategory | "all"; label: string; hint?: string }[] = [
  { key: "all", label: "All" },
  { key: "drops", label: "Drops", hint: "New set releases & schedules" },
  { key: "market", label: "Market", hint: "Prices, trends, analysis" },
  { key: "tcg", label: "Pokémon TCG", hint: "Card lore, artists, history" },
  { key: "center", label: "Pokémon Center", hint: "Official store events & merch" },
  { key: "guide", label: "Guide", hint: "Grading, sleeving, beginner tips" },
  { key: "news", label: "News", hint: "General announcements" },
];

const CATEGORY_LABEL: Record<string, string> = Object.fromEntries(
  CATEGORIES.map((c) => [c.key, c.label]),
);

export function categoryLabel(category: string | null | undefined): string {
  if (!category) return "News";
  return CATEGORY_LABEL[category] ?? category;
}
