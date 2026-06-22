"use client";

import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import { AdminGuard } from "@/components/admin/AdminGuard";
import { PostForm } from "@/components/admin/PostForm";

export default function NewPostPage() {
  return (
    <AdminGuard>
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
        <header className="mb-8">
          <h1 className="text-3xl font-extrabold tracking-tight text-text-primary">
            New post
          </h1>
          <p className="mt-2 text-sm text-text-secondary">
            Publishes immediately on save.
          </p>
        </header>
        <PostForm mode="create" />
      </main>
    </AdminGuard>
  );
}
