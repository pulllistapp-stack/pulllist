import Image from "next/image";
import Link from "next/link";
import { Metadata } from "next";
import { Calendar, Eye } from "lucide-react";

import { fetchPosts, NewsPost, NewsRegion, regionLabel } from "@/lib/news";

export const metadata: Metadata = {
  title: "News · PullList",
  description:
    "Pokémon TCG market updates, set release guides, and price-trend analysis from the PullList team.",
};

export const dynamic = "force-dynamic";

const REGIONS: { key: NewsRegion; label: string }[] = [
  { key: "all", label: "전체" },
  { key: "kr", label: "🇰🇷 한국" },
  { key: "ja", label: "🇯🇵 일본" },
  { key: "us", label: "🇺🇸 미국" },
];

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

export default async function NewsPage({
  searchParams,
}: {
  searchParams: Promise<{ region?: string }>;
}) {
  const params = await searchParams;
  const region: NewsRegion =
    params.region === "kr" || params.region === "ja" || params.region === "us"
      ? params.region
      : "all";

  const [posts, views] = await Promise.all([
    fetchPosts(region),
    fetchViewCounts(),
  ]);

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
          최신 카드
        </h1>
        <p className="mt-2 text-sm text-text-secondary">
          공식 사이트 최신 소식을 한눈에
        </p>
      </header>

      {/* Region tabs */}
      <div className="mb-8 flex flex-wrap gap-2">
        {REGIONS.map((r) => (
          <Link
            key={r.key}
            href={r.key === "all" ? "/news" : `/news?region=${r.key}`}
            className={`inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-sm font-semibold transition-colors ${
              region === r.key
                ? "border-accent-yellow/40 bg-accent-yellow/15 text-accent-yellow"
                : "border-border bg-bg-surface text-text-secondary hover:text-text-primary"
            }`}
          >
            {r.label}
          </Link>
        ))}
      </div>

      {posts.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="space-y-10">
          {Object.entries(groups).map(([date, dayPosts]) => (
            <section key={date}>
              <h2 className="mb-3 text-sm font-bold text-text-secondary">
                {formatKoreanDate(date)}
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
    </main>
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
          <span className="rounded-full bg-accent-yellow/15 px-2 py-0.5 font-semibold text-accent-yellow">
            {regionLabel(post.region)}
          </span>
          {post.category && (
            <span className="rounded-full border border-border bg-bg px-2 py-0.5 font-mono text-text-tertiary">
              {post.category}
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
      <p className="text-lg font-bold text-text-primary">
        아직 작성된 글이 없어요
      </p>
      <p className="mt-2 text-sm text-text-secondary">
        곧 첫 글이 올라옵니다. 다시 들러주세요.
      </p>
    </div>
  );
}

function formatKoreanDate(isoDate: string): string {
  const [y, m, d] = isoDate.split("-");
  return `${y}년 ${parseInt(m, 10)}월 ${parseInt(d, 10)}일`;
}

function formatShortDate(isoDate: string): string {
  const [, m, d] = isoDate.split("-");
  return `${m}.${d}`;
}
