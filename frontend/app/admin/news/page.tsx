"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Edit2,
  Eye,
  EyeOff,
  Plus,
  Send,
  Trash2,
} from "lucide-react";

import { AdminGuard } from "@/components/admin/AdminGuard";
import { getToken } from "@/lib/auth";
import {
  ADMIN_PAGE_SIZE,
  AdminStatusFilter,
  categoryLabel,
  fetchPostsAdmin,
  NewsPost,
} from "@/lib/news";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

const STATUS_FILTERS: { value: AdminStatusFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "published", label: "Published" },
  { value: "draft", label: "Drafts" },
  { value: "hidden", label: "Hidden" },
];

export default function AdminNewsListPage() {
  return (
    <AdminGuard>
      <AdminNewsListContent />
    </AdminGuard>
  );
}

function AdminNewsListContent() {
  const [posts, setPosts] = useState<NewsPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<AdminStatusFilter>("all");

  const load = useCallback(async () => {
    const token = getToken();
    if (!token) return;
    setLoading(true);
    const next = await fetchPostsAdmin(token, page, statusFilter);
    setPosts(next);
    setLoading(false);
  }, [page, statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  // Any status filter change resets to page 1 — otherwise a filter
  // that has fewer pages than the current one lands on an empty view.
  useEffect(() => {
    setPage(1);
  }, [statusFilter]);

  // Shared PUT helper — every status-flip button (Publish / Hide /
  // Unhide) is 'set the status field to X and PUT the rest of the
  // post back unchanged', so factoring it once keeps the buttons
  // one-liners.
  async function setStatus(
    post: NewsPost,
    newStatus: "draft" | "published" | "hidden",
  ) {
    const token = getToken();
    if (!token) return;
    setBusy(post.slug);
    try {
      const res = await fetch(
        `${API_BASE}/news/posts/${encodeURIComponent(post.slug)}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            slug: post.slug,
            title: post.title,
            body: post.body,
            excerpt: post.excerpt,
            region: post.region,
            category: post.category,
            thumbnail_url: post.thumbnail_url,
            author: post.author,
            published_at: post.published_at,
            reading_time: post.reading_time,
            status: newStatus,
            source_url: post.source_url ?? null,
          }),
        },
      );
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `HTTP ${res.status}`);
      }
      await load();
    } catch (e) {
      alert(
        `Couldn't update: ${e instanceof Error ? e.message : String(e)}`,
      );
    } finally {
      setBusy(null);
    }
  }

  async function deleteNow(post: NewsPost) {
    if (!confirm(`Delete "${post.title}"? This can't be undone.`)) return;
    const token = getToken();
    if (!token) return;
    setBusy(post.slug);
    try {
      const res = await fetch(
        `${API_BASE}/news/posts/${encodeURIComponent(post.slug)}`,
        {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        },
      );
      if (!res.ok && res.status !== 204) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `HTTP ${res.status}`);
      }
      await load();
    } catch (e) {
      alert(
        `Couldn't delete: ${e instanceof Error ? e.message : String(e)}`,
      );
    } finally {
      setBusy(null);
    }
  }

  // Same 'received exactly PAGE_SIZE rows' heuristic as the public
  // feed — cheap way to know there's probably a next page without a
  // second count() query per render.
  const hasNextPage = posts.length === ADMIN_PAGE_SIZE;
  const hasPrevPage = page > 1;

  return (
    <main className="mx-auto max-w-5xl px-4 py-10">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0 flex-1">
          <p className="font-mono text-xs uppercase tracking-widest text-text-tertiary">
            Admin
          </p>
          <h1 className="mt-1 text-3xl font-extrabold tracking-tight text-text-primary">
            Manage news
          </h1>
          <p className="mt-1 text-sm text-text-secondary">
            Create, edit, hide, or delete posts. Drafts (from the newsbot
            or manual saves) sit here until you publish them. Hidden
            posts stay in the DB but never render on /news.
          </p>
        </div>
        <Link
          href="/admin/news/new"
          className="shrink-0 inline-flex items-center gap-1.5 rounded-btn bg-accent-yellow px-4 py-2 text-sm font-bold text-gray-900 shadow-sm shadow-accent-yellow/30 hover:brightness-110"
        >
          <Plus className="h-4 w-4" />
          New post
        </Link>
      </header>

      {/* Status filter tabs — small chips, don't dominate the header row */}
      <div className="mb-4 flex flex-wrap gap-1.5">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            onClick={() => setStatusFilter(f.value)}
            className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${
              statusFilter === f.value
                ? "bg-accent-yellow/20 text-accent-yellow"
                : "bg-bg-surface text-text-tertiary hover:text-text-secondary"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="py-12 text-center text-sm text-text-tertiary">Loading...</p>
      ) : posts.length === 0 ? (
        <div className="rounded-2xl border-2 border-dashed border-border bg-bg-surface/50 p-12 text-center">
          <p className="text-base font-bold text-text-primary">
            {page > 1 ? "No more posts on this page" : "No posts match this filter"}
          </p>
          <p className="mt-2 text-sm text-text-secondary">
            {page > 1
              ? "Go back to page 1 or switch the filter."
              : "Hit the button above to write your first one."}
          </p>
        </div>
      ) : (
        <ul className="space-y-2">
          {posts.map((p) => {
            const isDraft = p.status === "draft";
            const isHidden = p.status === "hidden";
            return (
              <li
                key={p.slug}
                className={`rounded-card border bg-bg-surface p-3 ${
                  isDraft
                    ? "border-accent-yellow/40 bg-accent-yellow/[0.04]"
                    : isHidden
                      ? "border-text-tertiary/40 bg-bg-surface/70 opacity-70"
                      : "border-border"
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex items-center gap-2 text-xs">
                      {isDraft && (
                        <span className="rounded-full bg-accent-yellow/20 px-2 py-0.5 font-bold uppercase tracking-wider text-accent-yellow">
                          Draft
                        </span>
                      )}
                      {isHidden && (
                        <span className="rounded-full bg-text-tertiary/20 px-2 py-0.5 font-bold uppercase tracking-wider text-text-tertiary">
                          Hidden
                        </span>
                      )}
                      {p.category && (
                        <span className="rounded-full bg-accent-yellow/15 px-2 py-0.5 font-semibold text-accent-yellow">
                          {categoryLabel(p.category)}
                        </span>
                      )}
                      <span className="font-mono text-text-tertiary">
                        {p.published_at}
                      </span>
                      {p.source_url && (
                        <a
                          href={p.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="truncate font-mono text-text-tertiary hover:text-text-secondary"
                          title={p.source_url}
                        >
                          src ↗
                        </a>
                      )}
                    </div>
                    <p className="truncate text-sm font-bold text-text-primary">
                      {p.title}
                    </p>
                    <p className="truncate font-mono text-xs text-text-tertiary">
                      /news/{p.slug}
                    </p>
                  </div>
                  <div className="flex flex-shrink-0 gap-1">
                    {isDraft && (
                      <button
                        type="button"
                        onClick={() => setStatus(p, "published")}
                        disabled={busy === p.slug}
                        title="Publish this draft"
                        className="inline-flex items-center gap-1 rounded-btn bg-accent-yellow px-2 py-1.5 sm:px-3 text-xs font-bold text-gray-900 shadow-sm shadow-accent-yellow/30 hover:brightness-110 disabled:opacity-60"
                      >
                        <Send className="h-3 w-3" />
                        <span className="hidden sm:inline">
                          {busy === p.slug ? "..." : "Publish"}
                        </span>
                      </button>
                    )}
                    {p.status === "published" && (
                      <button
                        type="button"
                        onClick={() => setStatus(p, "hidden")}
                        disabled={busy === p.slug}
                        title="Hide from /news without deleting"
                        className="inline-flex items-center gap-1 rounded-btn border border-border bg-bg-surface px-2 py-1.5 sm:px-3 text-xs font-semibold text-text-secondary hover:text-text-primary disabled:opacity-60"
                      >
                        <EyeOff className="h-3 w-3" />
                        <span className="hidden sm:inline">
                          {busy === p.slug ? "..." : "Hide"}
                        </span>
                      </button>
                    )}
                    {isHidden && (
                      <button
                        type="button"
                        onClick={() => setStatus(p, "published")}
                        disabled={busy === p.slug}
                        title="Restore to /news"
                        className="inline-flex items-center gap-1 rounded-btn bg-accent-yellow px-2 py-1.5 sm:px-3 text-xs font-bold text-gray-900 shadow-sm shadow-accent-yellow/30 hover:brightness-110 disabled:opacity-60"
                      >
                        <Eye className="h-3 w-3" />
                        <span className="hidden sm:inline">
                          {busy === p.slug ? "..." : "Unhide"}
                        </span>
                      </button>
                    )}
                    <Link
                      // Drafts + hidden 404 on the public /news/{slug}
                      // route — route admins through the auth-aware
                      // preview page instead so they can still see them.
                      href={
                        isDraft || isHidden
                          ? `/admin/news/${p.slug}/preview`
                          : `/news/${p.slug}`
                      }
                      title="View post"
                      className="inline-flex items-center gap-1 rounded-btn border border-border bg-bg-surface px-2 py-1.5 sm:px-3 text-xs font-semibold text-text-secondary hover:text-text-primary"
                    >
                      <Eye className="h-3 w-3" />
                      <span className="hidden sm:inline">View</span>
                    </Link>
                    <Link
                      href={`/admin/news/${p.slug}/edit`}
                      title="Edit post"
                      className="inline-flex items-center gap-1 rounded-btn border border-accent-yellow/40 bg-accent-yellow/10 px-2 py-1.5 sm:px-3 text-xs font-semibold text-accent-yellow hover:bg-accent-yellow/15"
                    >
                      <Edit2 className="h-3 w-3" />
                      <span className="hidden sm:inline">Edit</span>
                    </Link>
                    <button
                      type="button"
                      onClick={() => deleteNow(p)}
                      disabled={busy === p.slug}
                      title={`Delete "${p.title}"`}
                      className="inline-flex items-center gap-1 rounded-btn border border-accent-red/40 bg-accent-red/10 px-2 py-1.5 sm:px-3 text-xs font-semibold text-accent-red hover:bg-accent-red/20 disabled:opacity-60"
                    >
                      <Trash2 className="h-3 w-3" />
                      {busy === p.slug && (
                        <span className="hidden sm:inline">...</span>
                      )}
                    </button>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {(hasPrevPage || hasNextPage) && !loading && (
        <nav className="mt-6 flex items-center justify-between text-sm">
          {hasPrevPage ? (
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="inline-flex items-center gap-1.5 rounded-btn border border-border bg-bg-surface px-3 py-1.5 font-semibold text-text-secondary hover:text-text-primary"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              Prev
            </button>
          ) : (
            <span />
          )}
          <span className="font-mono text-xs text-text-tertiary">Page {page}</span>
          {hasNextPage ? (
            <button
              type="button"
              onClick={() => setPage((p) => p + 1)}
              className="inline-flex items-center gap-1.5 rounded-btn border border-border bg-bg-surface px-3 py-1.5 font-semibold text-text-secondary hover:text-text-primary"
            >
              Next
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          ) : (
            <span />
          )}
        </nav>
      )}
    </main>
  );
}
