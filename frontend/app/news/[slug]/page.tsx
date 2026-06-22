import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Calendar, ChevronLeft, Eye, User } from "lucide-react";
import { Metadata } from "next";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { getAllSlugs, getPost, regionLabel } from "@/lib/news";
import { ViewBumper } from "./view-bumper";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

export async function generateStaticParams() {
  return getAllSlugs().map((slug) => ({ slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const post = getPost(slug);
  if (!post) return { title: "Not found · PullList" };
  return {
    title: `${post.title} · PullList`,
    description: post.excerpt ?? post.title,
    openGraph: {
      title: post.title,
      description: post.excerpt ?? post.title,
      images: post.thumbnail ? [post.thumbnail] : [],
      type: "article",
      publishedTime: post.publishedAt,
    },
  };
}

async function fetchViewCount(slug: string): Promise<number> {
  try {
    const r = await fetch(`${API_BASE}/news/views/${slug}`, {
      next: { revalidate: 60 },
    });
    if (!r.ok) return 0;
    const data = (await r.json()) as { view_count: number };
    return data.view_count ?? 0;
  } catch {
    return 0;
  }
}

export default async function NewsArticlePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const post = getPost(slug);
  if (!post) notFound();

  const viewCount = await fetchViewCount(slug);

  return (
    <main className="mx-auto max-w-3xl px-4 py-10 sm:py-14">
      {/* Client-side hook that pings the backend once on mount to bump
          the counter. SSR view stays read-only. */}
      <ViewBumper slug={slug} />

      <nav className="mb-6">
        <Link
          href="/news"
          className="inline-flex items-center gap-1 text-sm text-text-secondary hover:text-text-primary"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          뉴스 목록
        </Link>
      </nav>

      {/* Header */}
      <header className="mb-6">
        <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded-full bg-accent-yellow/15 px-2.5 py-0.5 font-semibold text-accent-yellow">
            {regionLabel(post.region)}
          </span>
          {post.category && (
            <span className="rounded-full border border-border bg-bg-surface px-2.5 py-0.5 font-mono text-text-tertiary">
              {post.category}
            </span>
          )}
        </div>
        <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-text-primary leading-tight">
          {post.title}
        </h1>
        {post.excerpt && (
          <p className="mt-4 text-base text-text-secondary leading-relaxed">
            {post.excerpt}
          </p>
        )}

        <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-border pt-4 text-xs font-mono text-text-tertiary">
          <span className="inline-flex items-center gap-1">
            <Calendar className="h-3.5 w-3.5" />
            {formatKoreanDate(post.publishedAt)}
          </span>
          {post.author && (
            <span className="inline-flex items-center gap-1">
              <User className="h-3.5 w-3.5" />
              {post.author}
            </span>
          )}
          <span className="inline-flex items-center gap-1">
            <Eye className="h-3.5 w-3.5" />
            {viewCount.toLocaleString()}
          </span>
          {post.readingTime && <span>· {post.readingTime} min read</span>}
        </div>
      </header>

      {post.thumbnail && (
        <div className="relative mb-8 aspect-video w-full overflow-hidden rounded-2xl bg-bg-surface">
          <Image
            src={post.thumbnail}
            alt=""
            fill
            sizes="(max-width: 768px) 100vw, 768px"
            className="object-cover"
            unoptimized
            priority
          />
        </div>
      )}

      {/* Body — Markdown with GFM (tables, strikethrough, task lists). */}
      <article className="prose-pl prose-headings:font-bold prose-headings:text-text-primary prose-p:text-text-secondary prose-p:leading-relaxed prose-a:text-teal-500 prose-strong:text-text-primary prose-li:text-text-secondary prose-img:rounded-xl max-w-none">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            h2: (props) => (
              <h2 className="mt-10 mb-3 text-xl font-bold text-text-primary border-b border-border pb-2" {...props} />
            ),
            h3: (props) => (
              <h3 className="mt-7 mb-2 text-base font-bold text-text-primary" {...props} />
            ),
            p: (props) => (
              <p className="my-4 text-sm sm:text-base text-text-secondary leading-relaxed" {...props} />
            ),
            ul: (props) => (
              <ul className="my-4 list-disc pl-6 space-y-1.5 text-sm sm:text-base text-text-secondary" {...props} />
            ),
            ol: (props) => (
              <ol className="my-4 list-decimal pl-6 space-y-1.5 text-sm sm:text-base text-text-secondary" {...props} />
            ),
            a: ({ href, ...props }) => (
              <a
                href={href}
                className="text-teal-500 underline underline-offset-2 hover:text-teal-400"
                target={href?.startsWith("http") ? "_blank" : undefined}
                rel={href?.startsWith("http") ? "noopener noreferrer" : undefined}
                {...props}
              />
            ),
            img: ({ src, alt }) => (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={src as string}
                alt={alt ?? ""}
                className="my-6 rounded-2xl border border-border w-full"
              />
            ),
            code: ({ inline, className, children, ...props }: {
              inline?: boolean;
              className?: string;
              children?: React.ReactNode;
            }) => {
              if (inline) {
                return (
                  <code className="rounded bg-bg-surface border border-border px-1.5 py-0.5 text-xs font-mono" {...props}>
                    {children}
                  </code>
                );
              }
              return (
                <pre className="my-4 rounded-xl border border-border bg-bg-surface p-4 overflow-x-auto">
                  <code className={`text-xs font-mono ${className ?? ""}`} {...props}>
                    {children}
                  </code>
                </pre>
              );
            },
          }}
        >
          {post.body}
        </ReactMarkdown>
      </article>

      <div className="mt-12 border-t border-border pt-6 text-xs text-text-tertiary">
        <Link
          href="/news"
          className="inline-flex items-center gap-1 hover:text-text-primary"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          뉴스 목록으로 돌아가기
        </Link>
      </div>
    </main>
  );
}

function formatKoreanDate(isoDate: string): string {
  const [y, m, d] = isoDate.split("-");
  return `${y}년 ${parseInt(m, 10)}월 ${parseInt(d, 10)}일`;
}
