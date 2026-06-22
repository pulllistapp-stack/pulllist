"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Edit2, Plus } from "lucide-react";

import { AdminGuard } from "@/components/admin/AdminGuard";
import { categoryLabel, fetchPosts, NewsPost } from "@/lib/news";

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

  useEffect(() => {
    fetchPosts("all").then((p) => {
      setPosts(p);
      setLoading(false);
    });
  }, []);

  return (
    <main className="mx-auto max-w-5xl px-4 py-10">
      <header className="mb-6 flex items-end justify-between gap-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-text-tertiary">
            Admin
          </p>
          <h1 className="mt-1 text-3xl font-extrabold tracking-tight text-text-primary">
            Manage news
          </h1>
          <p className="mt-1 text-sm text-text-secondary">
            Create, edit, and delete posts.
          </p>
        </div>
        <Link
          href="/admin/news/new"
          className="inline-flex items-center gap-1.5 rounded-btn bg-accent-yellow px-4 py-2 text-sm font-bold text-gray-900 shadow-sm shadow-accent-yellow/30 hover:brightness-110"
        >
          <Plus className="h-4 w-4" />
          New post
        </Link>
      </header>

      {loading ? (
        <p className="py-12 text-center text-sm text-text-tertiary">Loading...</p>
      ) : posts.length === 0 ? (
        <div className="rounded-2xl border-2 border-dashed border-border bg-bg-surface/50 p-12 text-center">
          <p className="text-base font-bold text-text-primary">
            No posts yet
          </p>
          <p className="mt-2 text-sm text-text-secondary">
            Hit the button above to write your first one.
          </p>
        </div>
      ) : (
        <ul className="space-y-2">
          {posts.map((p) => (
            <li
              key={p.slug}
              className="rounded-card border border-border bg-bg-surface p-3"
            >
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="mb-1 flex items-center gap-2 text-xs">
                    {p.category && (
                      <span className="rounded-full bg-accent-yellow/15 px-2 py-0.5 font-semibold text-accent-yellow">
                        {categoryLabel(p.category)}
                      </span>
                    )}
                    <span className="font-mono text-text-tertiary">
                      {p.published_at}
                    </span>
                  </div>
                  <p className="truncate text-sm font-bold text-text-primary">
                    {p.title}
                  </p>
                  <p className="truncate font-mono text-xs text-text-tertiary">
                    /news/{p.slug}
                  </p>
                </div>
                <div className="flex flex-shrink-0 gap-1">
                  <Link
                    href={`/news/${p.slug}`}
                    className="rounded-btn border border-border bg-bg-surface px-3 py-1.5 text-xs font-semibold text-text-secondary hover:text-text-primary"
                  >
                    View
                  </Link>
                  <Link
                    href={`/admin/news/${p.slug}/edit`}
                    className="inline-flex items-center gap-1 rounded-btn border border-accent-yellow/40 bg-accent-yellow/10 px-3 py-1.5 text-xs font-semibold text-accent-yellow hover:bg-accent-yellow/15"
                  >
                    <Edit2 className="h-3 w-3" />
                    Edit
                  </Link>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
