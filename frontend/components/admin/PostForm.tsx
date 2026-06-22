"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { getToken } from "@/lib/auth";
import { CATEGORIES, NewsCategory, NewsPost, NewsStatus } from "@/lib/news";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

type Mode = "create" | "edit";

type Props = {
  mode: Mode;
  initial?: NewsPost | null;
};

/**
 * Shared form for both /admin/news/new and /admin/news/[slug]/edit.
 * Status dropdown (Draft / Published) lets LO save half-written posts
 * without showing them on /news, and edit draft posts the newsbot
 * dumped here. Default on create is Published — matches the pre-bot
 * "save = publish" muscle memory.
 */
export function PostForm({ mode, initial }: Props) {
  const router = useRouter();

  const [slug, setSlug] = useState(initial?.slug ?? "");
  const [title, setTitle] = useState(initial?.title ?? "");
  const [excerpt, setExcerpt] = useState(initial?.excerpt ?? "");
  const [body, setBody] = useState(initial?.body ?? "");
  const [category, setCategory] = useState<NewsCategory | "all">(
    (initial?.category as NewsCategory | undefined) ?? "news",
  );
  const [thumbnail, setThumbnail] = useState(initial?.thumbnail_url ?? "");
  const [author, setAuthor] = useState(initial?.author ?? "");
  const [publishedAt, setPublishedAt] = useState(
    initial?.published_at ?? new Date().toISOString().slice(0, 10),
  );
  const [readingTime, setReadingTime] = useState<string>(
    initial?.reading_time?.toString() ?? "",
  );
  const [status, setStatus] = useState<NewsStatus>(
    (initial?.status as NewsStatus | undefined) ?? "published",
  );

  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Auto-fill the slug while creating from a kebab-case version of the
  // title — only until the user touches it manually. Edit mode leaves
  // the slug alone (renames aren't supported by the API).
  function onTitleChange(next: string) {
    setTitle(next);
    if (mode === "create" && !slug) {
      setSlug(
        next
          .toLowerCase()
          .replace(/[^\p{Letter}\p{Number}]+/gu, "-")
          .replace(/^-+|-+$/g, "")
          .slice(0, 80),
      );
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    setSaving(true);
    try {
      const token = getToken();
      if (!token) throw new Error("Not signed in");

      const payload = {
        slug,
        title,
        body,
        excerpt: excerpt || null,
        region: "all",
        category: category === "all" ? "news" : category,
        thumbnail_url: thumbnail || null,
        author: author || null,
        published_at: publishedAt,
        reading_time: readingTime ? parseInt(readingTime, 10) : null,
        status,
        source_url: initial?.source_url ?? null,
      };

      const url =
        mode === "create"
          ? `${API_BASE}/news/posts`
          : `${API_BASE}/news/posts/${encodeURIComponent(slug)}`;
      const res = await fetch(url, {
        method: mode === "create" ? "POST" : "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `HTTP ${res.status}`);
      }
      router.push("/admin/news");
      router.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function onDelete() {
    if (mode !== "edit") return;
    if (!confirm(`Delete "${title}"? This can't be undone.`)) return;
    setSaving(true);
    try {
      const token = getToken();
      const res = await fetch(`${API_BASE}/news/posts/${encodeURIComponent(slug)}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok && res.status !== 204) {
        throw new Error(`Delete failed: ${res.status}`);
      }
      router.push("/admin/news");
      router.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setSaving(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <Field label="Title" required>
        <input
          type="text"
          value={title}
          onChange={(e) => onTitleChange(e.target.value)}
          required
          className="w-full rounded-btn border border-border bg-bg px-3 py-2 text-base font-bold text-text-primary focus:border-accent-yellow focus:outline-none"
          placeholder="Mega Evolution tier list — SR & SAR market"
        />
      </Field>

      <Field
        label="Slug (URL path)"
        hint="Auto-generated from the title. Keep it short."
        required
      >
        <input
          type="text"
          value={slug}
          onChange={(e) => setSlug(e.target.value)}
          required
          disabled={mode === "edit"}
          className="w-full rounded-btn border border-border bg-bg px-3 py-2 font-mono text-sm text-text-primary focus:border-accent-yellow focus:outline-none disabled:opacity-60"
          placeholder="mega-evolution-tier-list"
        />
      </Field>

      <Field label="Category" hint="What kind of post this is.">
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value as NewsCategory | "all")}
          className="w-full rounded-btn border border-border bg-bg px-3 py-2 text-sm text-text-primary focus:border-accent-yellow focus:outline-none"
        >
          {CATEGORIES.filter((c) => c.key !== "all").map((c) => (
            <option key={c.key} value={c.key}>
              {c.label}
              {c.hint ? ` — ${c.hint}` : ""}
            </option>
          ))}
        </select>
      </Field>

      <Field
        label="Status"
        hint="Drafts stay hidden from /news until you publish them."
      >
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as NewsStatus)}
          className="w-full rounded-btn border border-border bg-bg px-3 py-2 text-sm text-text-primary focus:border-accent-yellow focus:outline-none"
        >
          <option value="published">Published — visible on /news</option>
          <option value="draft">Draft — hidden until you publish</option>
        </select>
      </Field>

      <Field label="Excerpt" hint="The one or two lines shown on the listing card.">
        <textarea
          value={excerpt}
          onChange={(e) => setExcerpt(e.target.value)}
          rows={2}
          className="w-full rounded-btn border border-border bg-bg px-3 py-2 text-sm text-text-primary focus:border-accent-yellow focus:outline-none"
          placeholder="Short summary..."
        />
      </Field>

      <Field label="Thumbnail URL" hint="Paste an external image URL (optional).">
        <input
          type="url"
          value={thumbnail}
          onChange={(e) => setThumbnail(e.target.value)}
          className="w-full rounded-btn border border-border bg-bg px-3 py-2 font-mono text-xs text-text-primary focus:border-accent-yellow focus:outline-none"
          placeholder="https://..."
        />
      </Field>

      <Field label="Body (Markdown)" required>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          required
          rows={20}
          className="w-full rounded-btn border border-border bg-bg px-3 py-3 font-mono text-sm text-text-primary leading-relaxed focus:border-accent-yellow focus:outline-none"
          placeholder="# Heading&#10;&#10;Body markdown...&#10;&#10;## Section&#10;&#10;![](https://...) images work too"
        />
      </Field>

      <div className="grid gap-5 sm:grid-cols-3">
        <Field label="Author" hint="Defaults to your name.">
          <input
            type="text"
            value={author}
            onChange={(e) => setAuthor(e.target.value)}
            className="w-full rounded-btn border border-border bg-bg px-3 py-2 text-sm text-text-primary focus:border-accent-yellow focus:outline-none"
            placeholder="LO"
          />
        </Field>
        <Field label="Published date" required>
          <input
            type="date"
            value={publishedAt}
            onChange={(e) => setPublishedAt(e.target.value)}
            required
            className="w-full rounded-btn border border-border bg-bg px-3 py-2 text-sm text-text-primary focus:border-accent-yellow focus:outline-none"
          />
        </Field>
        <Field label="Reading time (min)">
          <input
            type="number"
            min="1"
            max="120"
            value={readingTime}
            onChange={(e) => setReadingTime(e.target.value)}
            className="w-full rounded-btn border border-border bg-bg px-3 py-2 text-sm text-text-primary focus:border-accent-yellow focus:outline-none"
            placeholder="5"
          />
        </Field>
      </div>

      {err && (
        <div className="rounded-card bg-accent-red/10 border border-accent-red/30 p-3 text-sm text-accent-red">
          {err}
        </div>
      )}

      <div className="flex items-center justify-between gap-3 pt-2">
        <div className="flex gap-2">
          <button
            type="submit"
            disabled={saving}
            className="rounded-btn bg-accent-yellow px-5 py-2.5 text-sm font-bold text-gray-900 shadow-sm shadow-accent-yellow/30 hover:brightness-110 disabled:opacity-60"
          >
            {saving
              ? "Saving..."
              : mode === "create"
                ? status === "draft"
                  ? "Save draft"
                  : "Publish"
                : "Save changes"}
          </button>
          <button
            type="button"
            onClick={() => router.push("/admin/news")}
            className="rounded-btn border border-border bg-bg-surface px-4 py-2.5 text-sm font-semibold text-text-secondary hover:text-text-primary"
          >
            Cancel
          </button>
        </div>
        {mode === "edit" && (
          <button
            type="button"
            onClick={onDelete}
            disabled={saving}
            className="rounded-btn border border-accent-red/40 bg-accent-red/10 px-4 py-2.5 text-sm font-semibold text-accent-red hover:bg-accent-red/20 disabled:opacity-60"
          >
            Delete
          </button>
        )}
      </div>
    </form>
  );
}

function Field({
  label,
  children,
  hint,
  required,
}: {
  label: string;
  children: React.ReactNode;
  hint?: string;
  required?: boolean;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-text-tertiary">
        {label}
        {required && <span className="ml-0.5 text-accent-red">*</span>}
      </label>
      {children}
      {hint && (
        <p className="mt-1 text-xs text-text-tertiary">{hint}</p>
      )}
    </div>
  );
}
