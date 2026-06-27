"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { ChevronLeft } from "lucide-react";

import { AdminGuard } from "@/components/admin/AdminGuard";
import { PostForm } from "@/components/admin/PostForm";
import { getToken } from "@/lib/auth";
import { fetchPost, NewsPost } from "@/lib/news";

export default function EditPostPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = use(params);
  return (
    <AdminGuard>
      <EditPostContent slug={slug} />
    </AdminGuard>
  );
}

function EditPostContent({ slug }: { slug: string }) {
  const [post, setPost] = useState<NewsPost | null | undefined>(undefined);

  useEffect(() => {
    // Pass the admin bearer token so the GET resolves drafts too —
    // without it the public route 404s anything not published yet.
    fetchPost(slug, getToken() ?? undefined).then(setPost);
  }, [slug]);

  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <nav className="mb-6">
        <Link
          href="/admin/news"
          className="inline-flex items-center gap-1 text-sm text-text-secondary hover:text-text-primary"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          Manage news
        </Link>
      </nav>

      {post === undefined ? (
        <p className="py-12 text-center text-sm text-text-tertiary">Loading...</p>
      ) : post === null ? (
        <p className="py-12 text-center text-sm text-text-tertiary">
          Post not found.
        </p>
      ) : (
        <>
          <header className="mb-8">
            <h1 className="text-3xl font-extrabold tracking-tight text-text-primary">
              Edit post
            </h1>
            <p className="mt-2 text-sm text-text-secondary">
              Changes go live immediately at /news/{slug}.
            </p>
          </header>
          <PostForm mode="edit" initial={post} />
        </>
      )}
    </main>
  );
}
