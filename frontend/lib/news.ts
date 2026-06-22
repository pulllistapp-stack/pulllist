import fs from "fs";
import path from "path";

import matter from "gray-matter";

/**
 * Markdown-backed news posts. Authoring flow:
 *   1. Drop a .md file under `frontend/content/news/`
 *   2. Fill the frontmatter (see NewsFrontmatter)
 *   3. git push — Vercel rebuilds and the post is live
 *
 * View counts come from the backend (lightweight `news_views` table). The
 * Markdown files are the source of truth for content; the DB only stores
 * the running counter so we can rank popular posts later.
 */

export type NewsRegion = "all" | "kr" | "ja" | "us";

export type NewsFrontmatter = {
  /** kebab-case identifier, also the URL slug. Falls back to filename. */
  slug?: string;
  title: string;
  excerpt?: string;
  publishedAt: string; // YYYY-MM-DD
  author?: string;
  region: NewsRegion;
  /** Free-form chip on the listing — e.g. '읽을거리', '소식', '가이드'. */
  category?: string;
  /** Public-folder path or absolute URL. */
  thumbnail?: string;
  /** Estimated read time in minutes. Used in the card meta strip. */
  readingTime?: number;
  /** When true, hidden from listing — useful for drafts in main. */
  draft?: boolean;
  /** Optional list of card_ids the post references; future feature ties
   *  these into inline card previews when we render the body. */
  cardIds?: string[];
};

export type NewsPost = NewsFrontmatter & {
  slug: string;
  body: string;
};

const CONTENT_DIR = path.join(process.cwd(), "content", "news");

function readPosts(): NewsPost[] {
  if (!fs.existsSync(CONTENT_DIR)) return [];
  const files = fs.readdirSync(CONTENT_DIR).filter((f) => f.endsWith(".md"));
  const posts = files.map((file) => {
    const raw = fs.readFileSync(path.join(CONTENT_DIR, file), "utf8");
    const parsed = matter(raw);
    const frontmatter = parsed.data as NewsFrontmatter;
    const slug = frontmatter.slug ?? file.replace(/\.md$/, "");
    return { ...frontmatter, slug, body: parsed.content };
  });
  // Hide drafts and sort newest-first by publishedAt (ISO YYYY-MM-DD
  // sorts lexically the right way).
  return posts
    .filter((p) => !p.draft)
    .sort((a, b) => (a.publishedAt < b.publishedAt ? 1 : -1));
}

export function getAllPosts(region?: NewsRegion): NewsPost[] {
  const all = readPosts();
  if (!region || region === "all") return all;
  return all.filter((p) => p.region === region || p.region === "all");
}

export function getPost(slug: string): NewsPost | null {
  return readPosts().find((p) => p.slug === slug) ?? null;
}

export function getAllSlugs(): string[] {
  return readPosts().map((p) => p.slug);
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
