"use client";

import Link from "next/link";
import { useEffect, useState, use } from "react";
import { Calendar, ChevronLeft, Edit2, User } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { AdminGuard } from "@/components/admin/AdminGuard";
import { getToken } from "@/lib/auth";
import { categoryLabel, fetchPost, NewsPost } from "@/lib/news";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

/**
 * Admin-only draft preview. Same rendering as the public /news/{slug}
 * route but client-rendered so it can pass the admin bearer token —
 * draft posts 404 on the public path. SEO / OG tags are intentionally
 * absent here; this URL is never meant to be public.
 */
export default function NewsPreviewPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = use(params);
  return (
    <AdminGuard>
      <PreviewContent slug={slug} />
    </AdminGuard>
  );
}

function PreviewContent({ slug }: { slug: string }) {
  const [post, setPost] = useState<NewsPost | null>(null);
  const [loading, setLoading] = useState(true);
  const [publishing, setPublishing] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    fetchPost(slug, token).then((p) => {
      setPost(p);
      setLoading(false);
    });
  }, [slug]);

  async function publishNow() {
    if (!post) return;
    const token = getToken();
    if (!token) return;
    setPublishing(true);
    setErr(null);
    try {
      const res = await fetch(
        `${API_BASE}/news/posts/${encodeURIComponent(post.slug)}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ ...post, status: "published" }),
        },
      );
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `HTTP ${res.status}`);
      }
      window.location.href = `/news/${post.slug}`;
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setPublishing(false);
    }
  }

  if (loading) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-14">
        <p className="text-center text-sm text-text-tertiary">Loading…</p>
      </main>
    );
  }
  if (!post) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-14">
        <p className="text-center text-sm text-text-tertiary">
          Post not found.
        </p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-10 sm:py-14">
      <nav className="mb-6">
        <Link
          href="/admin/news"
          className="inline-flex items-center gap-1 text-sm text-text-secondary hover:text-text-primary"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          Back to admin
        </Link>
      </nav>

      <div className="mb-6 rounded-card border border-accent-yellow/40 bg-accent-yellow/[0.06] p-3">
        <div className="flex items-center justify-between gap-3">
          <div className="text-xs">
            <span className="rounded-full bg-accent-yellow/20 px-2 py-0.5 font-bold uppercase tracking-wider text-accent-yellow">
              {post.status === "draft" ? "Draft preview" : "Already published"}
            </span>
            <span className="ml-2 font-mono text-text-tertiary">
              /news/{post.slug}
            </span>
          </div>
          <div className="flex gap-1">
            <Link
              href={`/admin/news/${post.slug}/edit`}
              className="inline-flex items-center gap-1 rounded-btn border border-border bg-bg-surface px-3 py-1.5 text-xs font-semibold text-text-secondary hover:text-text-primary"
            >
              <Edit2 className="h-3 w-3" />
              Edit
            </Link>
            {post.status === "draft" && (
              <button
                type="button"
                onClick={publishNow}
                disabled={publishing}
                className="rounded-btn bg-accent-yellow px-3 py-1.5 text-xs font-bold text-gray-900 shadow-sm shadow-accent-yellow/30 hover:brightness-110 disabled:opacity-60"
              >
                {publishing ? "Publishing…" : "Publish now"}
              </button>
            )}
          </div>
        </div>
        {err && (
          <p className="mt-2 text-xs text-accent-red">Couldn&apos;t publish: {err}</p>
        )}
      </div>

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
            {post.published_at}
          </span>
          {post.author && (
            <span className="inline-flex items-center gap-1">
              <User className="h-3.5 w-3.5" />
              {post.author}
            </span>
          )}
          {post.reading_time && <span>· {post.reading_time} min read</span>}
        </div>
      </header>

      {post.thumbnail_url && (
        // Match the public detail page — object-contain inside a
        // flex-centered box so portrait product shots aren't cropped.
        // Bypass next/image: admin preview doesn't need the loader.
        <div className="mb-8 flex justify-center overflow-hidden rounded-2xl bg-bg-surface">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={post.thumbnail_url}
            alt=""
            className="h-auto max-h-[32rem] w-auto max-w-full object-contain"
          />
        </div>
      )}

      <article className="prose-pl max-w-none">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            h2: (props) => (
              <h2
                className="mt-10 mb-3 text-xl font-bold text-text-primary border-b border-border pb-2"
                {...props}
              />
            ),
            h3: (props) => (
              <h3
                className="mt-7 mb-2 text-base font-bold text-text-primary"
                {...props}
              />
            ),
            p: (props) => (
              <p
                className="my-4 text-sm sm:text-base text-text-secondary leading-relaxed"
                {...props}
              />
            ),
            ul: (props) => (
              <ul
                className="my-4 list-disc pl-6 space-y-1.5 text-sm sm:text-base text-text-secondary"
                {...props}
              />
            ),
            ol: (props) => (
              <ol
                className="my-4 list-decimal pl-6 space-y-1.5 text-sm sm:text-base text-text-secondary"
                {...props}
              />
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
              // Match the public detail page — card/product shots get
              // max-h cap + centered so portrait cards don't blow up.
              <img
                src={src as string}
                alt={alt ?? ""}
                className="my-6 mx-auto block max-h-80 w-auto max-w-full rounded-2xl border border-border"
              />
            ),
          }}
        >
          {post.body}
        </ReactMarkdown>
      </article>
    </main>
  );
}
