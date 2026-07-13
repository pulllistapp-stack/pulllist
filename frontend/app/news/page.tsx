import Image from "next/image";
import Link from "next/link";
import { Metadata } from "next";
import { Calendar, ChevronLeft, ChevronRight, Eye } from "lucide-react";

import {
  CATEGORIES,
  categoryLabel,
  fetchPosts,
  NEWS_PAGE_SIZE,
  NewsCategory,
  NewsPost,
} from "@/lib/news";

export const metadata: Metadata = {
  title: "News · PullList",
  description:
    "Pokémon TCG market updates, set release guides, and price-trend analysis from the PullList team.",
};

export const dynamic = "force-dynamic";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

async function fetchViewCounts(): Promise<Record<string, number>> {
  try {
    const r = await fetch(`${API_BASE}/news/views`, { cache: "no-store" });
    if (!r.ok) return {};
    return (await r.json()) as Record<string, number>;
  } catch {
    return {};
  }
}

function isCategory(v: string | undefined): v is NewsCategory | "all" {
  return CATEGORIES.some((c) => c.key === v);
}

export default async function NewsPage({
  searchParams,
}: {
  searchParams: Promise<{ category?: string; page?: string }>;
}) {
  const params = await searchParams;
  const category: NewsCategory | "all" = isCategory(params.category)
    ? (params.category as NewsCategory | "all")
    : "all";
  const page = Math.max(1, parseInt(params.page ?? "1", 10) || 1);

  const [posts, views] = await Promise.all([
    fetchPosts(category, page),
    fetchViewCounts(),
  ]);

  // Backend caps at NEWS_PAGE_SIZE per request — if we got exactly
  // that many rows there's probably another page. If we got fewer,
  // we're on the last page. Cheap heuristic that avoids a second
  // count() query on every listing render.
  const hasNextPage = posts.length === NEWS_PAGE_SIZE;
  const hasPrevPage = page > 1;

  const buildHref = (p: number) => {
    const sp = new URLSearchParams();
    if (category !== "all") sp.set("category", category);
    if (p > 1) sp.set("page", String(p));
    const qs = sp.toString();
    return qs ? `/news?${qs}` : "/news";
  };

  // Group by date for the listing — newest day at the top, posts inside
  // grouped under their YYYY-MM-DD heading.
  const groups = posts.reduce<Record<string, NewsPost[]>>((acc, p) => {
    (acc[p.published_at] ??= []).push(p);
    return acc;
  }, {});

  return (
    <main className="mx-auto max-w-5xl px-4 py-10 sm:py-14">
      <header className="mb-8">
        <p className="font-mono text-xs uppercase tracking-widest text-text-tertiary">
          News
        </p>
        <h1 className="mt-1 text-3xl sm:text-4xl font-extrabold tracking-tight text-text-primary">
          Latest from PullList
        </h1>
        <p className="mt-2 text-sm text-text-secondary">
          Drops, market updates, and guides for serious collectors.
        </p>
      </header>

      {/* Category tabs */}
      <div className="mb-8 flex flex-wrap gap-2">
        {CATEGORIES.map((c) => (
          <Link
            key={c.key}
            href={c.key === "all" ? "/news" : `/news?category=${c.key}`}
            title={c.hint}
            className={`inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-sm font-semibold transition-colors ${
              category === c.key
                ? "border-accent-yellow/40 bg-accent-yellow/15 text-accent-yellow"
                : "border-border bg-bg-surface text-text-secondary hover:text-text-primary"
            }`}
          >
            {c.label}
          </Link>
        ))}
      </div>

      {posts.length === 0 ? (
        page > 1 ? <EmptyPageState prevHref={buildHref(page - 1)} /> : <EmptyState />
      ) : (
        <div className="space-y-10">
          {Object.entries(groups).map(([date, dayPosts]) => (
            <section key={date}>
              <h2 className="mb-3 text-sm font-bold text-text-secondary">
                {formatDate(date)}
              </h2>
              <div className="space-y-3">
                {dayPosts.map((p) => (
                  <ArticleCard
                    key={p.slug}
                    post={p}
                    viewCount={views[p.slug] ?? 0}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      {(hasPrevPage || hasNextPage) && (
        <nav className="mt-10 flex items-center justify-between border-t border-border pt-6 text-sm">
          {hasPrevPage ? (
            <Link
              href={buildHref(page - 1)}
              className="inline-flex items-center gap-1.5 rounded-btn border border-border bg-bg-surface px-4 py-2 font-semibold text-text-secondary hover:text-text-primary"
            >
              <ChevronLeft className="h-4 w-4" />
              Newer
            </Link>
          ) : (
            <span />
          )}
          <span className="font-mono text-xs text-text-tertiary">Page {page}</span>
          {hasNextPage ? (
            <Link
              href={buildHref(page + 1)}
              className="inline-flex items-center gap-1.5 rounded-btn border border-border bg-bg-surface px-4 py-2 font-semibold text-text-secondary hover:text-text-primary"
            >
              Older
              <ChevronRight className="h-4 w-4" />
            </Link>
          ) : (
            <span />
          )}
        </nav>
      )}
    </main>
  );
}

function EmptyPageState({ prevHref }: { prevHref: string }) {
  return (
    <div className="rounded-2xl border-2 border-dashed border-border bg-bg-surface/50 p-12 text-center">
      <p className="text-lg font-bold text-text-primary">No more posts</p>
      <p className="mt-2 text-sm text-text-secondary">
        You've reached the end.
      </p>
      <Link
        href={prevHref}
        className="mt-4 inline-flex items-center gap-1.5 rounded-btn border border-border bg-bg-surface px-4 py-2 text-sm font-semibold text-text-secondary hover:text-text-primary"
      >
        <ChevronLeft className="h-4 w-4" />
        Back
      </Link>
    </div>
  );
}

function ArticleCard({
  post,
  viewCount,
}: {
  post: NewsPost;
  viewCount: number;
}) {
  return (
    <Link
      href={`/news/${post.slug}`}
      className="group flex gap-4 rounded-2xl border border-border bg-bg-surface p-4 transition-all hover:border-accent-yellow/40 hover:-translate-y-0.5"
    >
      <div className="min-w-0 flex-1">
        <div className="mb-1.5 flex items-center gap-2 text-xs">
          {post.category && (
            <span className="rounded-full bg-accent-yellow/15 px-2 py-0.5 font-semibold text-accent-yellow">
              {categoryLabel(post.category)}
            </span>
          )}
        </div>
        <h3 className="text-base font-bold text-text-primary group-hover:text-accent-yellow line-clamp-2">
          {post.title}
        </h3>
        {post.excerpt && (
          <p className="mt-1 text-sm text-text-secondary line-clamp-2">
            {post.excerpt}
          </p>
        )}
        <div className="mt-2 flex items-center gap-3 text-xs font-mono text-text-tertiary">
          <span className="inline-flex items-center gap-1">
            <Calendar className="h-3 w-3" />
            {formatShortDate(post.published_at)}
          </span>
          <span className="inline-flex items-center gap-1">
            <Eye className="h-3 w-3" />
            {viewCount.toLocaleString()}
          </span>
          {post.author && <span>· {post.author}</span>}
          {post.reading_time && <span>· {post.reading_time} min read</span>}
        </div>
      </div>
      {post.thumbnail_url && (
        <div className="relative h-24 w-32 shrink-0 overflow-hidden rounded-xl bg-bg">
          <Image
            src={post.thumbnail_url}
            alt=""
            fill
            sizes="128px"
            className="object-cover"
            unoptimized
          />
        </div>
      )}
    </Link>
  );
}

function EmptyState() {
  return (
    <div className="rounded-2xl border-2 border-dashed border-border bg-bg-surface/50 p-12 text-center">
      <p className="text-lg font-bold text-text-primary">No posts yet</p>
      <p className="mt-2 text-sm text-text-secondary">
        New articles drop here regularly. Check back soon.
      </p>
    </div>
  );
}

function formatDate(isoDate: string): string {
  const [y, m, d] = isoDate.split("-");
  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  return `${months[parseInt(m, 10) - 1]} ${parseInt(d, 10)}, ${y}`;
}

function formatShortDate(isoDate: string): string {
  const [, m, d] = isoDate.split("-");
  return `${m}.${d}`;
}
