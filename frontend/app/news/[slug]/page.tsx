import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Calendar, ChevronLeft, Eye, User } from "lucide-react";
import { Metadata } from "next";
import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import remarkGfm from "remark-gfm";

import { categoryLabel, fetchPost } from "@/lib/news";
import { ViewBumper } from "./view-bumper";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const post = await fetchPost(slug);
  if (!post) return { title: "Not found · PullList" };
  return {
    title: `${post.title} · PullList`,
    description: post.excerpt ?? post.title,
    openGraph: {
      title: post.title,
      description: post.excerpt ?? post.title,
      images: post.thumbnail_url ? [post.thumbnail_url] : [],
      type: "article",
      publishedTime: post.published_at,
    },
  };
}

async function fetchViewCount(slug: string): Promise<number> {
  try {
    const r = await fetch(`${API_BASE}/news/views/${slug}`, {
      cache: "no-store",
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
  const post = await fetchPost(slug);
  if (!post) notFound();

  const viewCount = await fetchViewCount(slug);

  return (
    <main className="mx-auto max-w-3xl px-4 py-10 sm:py-14">
      <ViewBumper slug={slug} />

      <nav className="mb-6">
        <Link
          href="/news"
          className="inline-flex items-center gap-1 text-sm text-text-secondary hover:text-text-primary"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          Back to news
        </Link>
      </nav>

      <header className="mb-6">
        <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
          {post.category && (
            <span className="rounded-full bg-accent-yellow/15 px-2.5 py-0.5 font-semibold text-accent-yellow">
              {categoryLabel(post.category)}
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
            {formatDate(post.published_at)}
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
          {post.reading_time && <span>· {post.reading_time} min read</span>}
        </div>
      </header>

      {post.thumbnail_url && (
        // Drop the fixed 16:9 box — PokeBeach product shots are often
        // portrait (1206×1500 etc.) and get heavily cropped with
        // object-cover. Use object-contain inside a flex-centered
        // container so landscape and portrait sources both display in
        // full; max-h caps the rare giant portrait from dominating.
        <div className="mb-8 flex justify-center overflow-hidden rounded-2xl bg-bg-surface">
          <Image
            src={post.thumbnail_url}
            alt=""
            width={1600}
            height={900}
            sizes="(max-width: 768px) 100vw, 768px"
            className="h-auto max-h-[32rem] w-auto max-w-full object-contain"
            unoptimized
            priority
          />
        </div>
      )}

      <article className="prose-pl max-w-none">
        <ReactMarkdown
          // rehype-raw lets admin-authored HTML (e.g. flex containers
          // wrapping multiple images for side-by-side layout) render
          // instead of getting escaped. Body content only comes from
          // the bot + the admin form, so the XSS surface is internal.
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeRaw]}
          components={{
            h2: (props) => (
              <h2
                className="mt-10 mb-3 text-xl font-bold text-text-primary border-b border-border pb-2"
                {...props}
              />
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
            img: ({ src, alt }) => {
              const href = src as string;
              // Wrap the inline body image in an <a> so a click opens
              // the full-resolution source in a new tab. The src URL
              // already points at the original via weserv (no resize
              // params) so the new-tab view = native asset size. The
              // in-article render stays capped at max-h-80 for layout.
              return (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="my-6 mx-auto block w-fit max-w-full cursor-zoom-in"
                  aria-label={alt ? `Open full-size image: ${alt}` : "Open full-size image"}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={href}
                    alt={alt ?? ""}
                    className="mx-auto block max-h-80 w-auto max-w-full rounded-2xl border border-border transition-opacity hover:opacity-90"
                  />
                </a>
              );
            },
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
          Back to news
        </Link>
      </div>
    </main>
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
