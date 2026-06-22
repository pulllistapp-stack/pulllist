"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { ChevronLeft } from "lucide-react";

import { AdminGuard } from "@/components/admin/AdminGuard";
import { PostForm } from "@/components/admin/PostForm";
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
    fetchPost(slug).then(setPost);
  }, [slug]);

  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <nav className="mb-6">
        <Link
          href="/admin/news"
          className="inline-flex items-center gap-1 text-sm text-text-secondary hover:text-text-primary"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          뉴스 관리
        </Link>
      </nav>

      {post === undefined ? (
        <p className="py-12 text-center text-sm text-text-tertiary">로딩 중...</p>
      ) : post === null ? (
        <p className="py-12 text-center text-sm text-text-tertiary">
          글을 찾을 수 없습니다.
        </p>
      ) : (
        <>
          <header className="mb-8">
            <h1 className="text-3xl font-extrabold tracking-tight text-text-primary">
              글 수정
            </h1>
            <p className="mt-2 text-sm text-text-secondary">
              저장하면 변경 사항이 즉시 /news/{slug}에 반영됩니다.
            </p>
          </header>
          <PostForm mode="edit" initial={post} />
        </>
      )}
    </main>
  );
}
