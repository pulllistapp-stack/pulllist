"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useRef, useState } from "react";
import { ImagePlus, Loader2, Upload } from "lucide-react";

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
 * Status dropdown (Draft / Published) lets an admin save half-written
 * posts without showing them on /news, and edit draft posts the
 * newsbot dumped here. Default on create is Published — matches the
 * pre-bot "save = publish" muscle memory.
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

  // Image upload state. Tracked separately for the thumbnail picker
  // and the body-insert picker so each shows its own spinner without
  // greying out the form chrome.
  const [uploadingThumb, setUploadingThumb] = useState(false);
  const [uploadingBody, setUploadingBody] = useState(false);
  const thumbInputRef = useRef<HTMLInputElement | null>(null);
  const bodyInputRef = useRef<HTMLInputElement | null>(null);
  const bodyTextareaRef = useRef<HTMLTextAreaElement | null>(null);

  /**
   * POST the file to /api/admin/upload-image and return the public
   * Blob URL. Throws on any non-2xx so callers can surface the
   * server's error message (the API route returns helpful detail —
   * "file too large", "wrong type", etc.).
   */
  async function uploadImage(file: File): Promise<string> {
    const token = getToken();
    if (!token) throw new Error("Not signed in");
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("/api/admin/upload-image", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: fd,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new Error(body?.error ?? `Upload failed: ${res.status}`);
    }
    const data = (await res.json()) as { url: string };
    return data.url;
  }

  async function onPickThumb(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // reset so picking the same file twice still fires onChange
    if (!file) return;
    setErr(null);
    setUploadingThumb(true);
    try {
      const url = await uploadImage(file);
      setThumbnail(url);
    } catch (err) {
      setErr(err instanceof Error ? err.message : String(err));
    } finally {
      setUploadingThumb(false);
    }
  }

  async function onPickBodyImage(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setErr(null);
    setUploadingBody(true);
    try {
      const url = await uploadImage(file);
      const alt = file.name.replace(/\.[^.]+$/, "");
      const snippet = `![${alt}](${url})`;
      // Insert at the textarea's caret position so the user can place
      // the image mid-paragraph; if the ref isn't ready, fall back to
      // appending at the end with surrounding blank lines.
      const ta = bodyTextareaRef.current;
      if (ta) {
        const start = ta.selectionStart;
        const end = ta.selectionEnd;
        const before = body.slice(0, start);
        const after = body.slice(end);
        // Pad with blank lines so the image renders as its own
        // paragraph in markdown (otherwise it can glue to surrounding
        // text and the rendered output looks broken).
        const padBefore = before && !before.endsWith("\n\n") ? "\n\n" : "";
        const padAfter = after && !after.startsWith("\n\n") ? "\n\n" : "";
        const next = before + padBefore + snippet + padAfter + after;
        setBody(next);
        // Move caret to just after the inserted snippet on the next
        // tick (after React re-renders the textarea with the new value).
        const caret = (before + padBefore + snippet).length;
        requestAnimationFrame(() => {
          ta.focus();
          ta.setSelectionRange(caret, caret);
        });
      } else {
        setBody((prev) => (prev ? `${prev}\n\n${snippet}\n` : snippet));
      }
    } catch (err) {
      setErr(err instanceof Error ? err.message : String(err));
    } finally {
      setUploadingBody(false);
    }
  }

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

      <Field
        label="Thumbnail"
        hint="Upload from your computer, or paste an external URL."
      >
        <div className="flex flex-col gap-2 sm:flex-row sm:items-stretch">
          <input
            type="url"
            value={thumbnail}
            onChange={(e) => setThumbnail(e.target.value)}
            className="flex-1 rounded-btn border border-border bg-bg px-3 py-2 font-mono text-xs text-text-primary focus:border-accent-yellow focus:outline-none"
            placeholder="https://..."
          />
          <input
            ref={thumbInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={onPickThumb}
          />
          <button
            type="button"
            onClick={() => thumbInputRef.current?.click()}
            disabled={uploadingThumb}
            className="inline-flex items-center justify-center gap-1.5 rounded-btn border border-border bg-bg-surface px-3 py-2 text-xs font-semibold text-text-secondary hover:text-text-primary disabled:opacity-60"
          >
            {uploadingThumb ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Uploading...
              </>
            ) : (
              <>
                <Upload className="h-3.5 w-3.5" />
                Upload
              </>
            )}
          </button>
        </div>
        {thumbnail && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={thumbnail}
            alt="Thumbnail preview"
            className="mt-2 max-h-32 rounded-card border border-border object-contain"
          />
        )}
      </Field>

      <Field label="Body (Markdown)" required>
        <div className="mb-2 flex items-center justify-between gap-2">
          <p className="text-xs text-text-tertiary">
            Insert an image at your cursor, or paste{" "}
            <code className="rounded bg-bg-surface px-1 py-0.5 font-mono text-[10px]">
              ![alt](url)
            </code>{" "}
            yourself.
          </p>
          <input
            ref={bodyInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={onPickBodyImage}
          />
          <button
            type="button"
            onClick={() => bodyInputRef.current?.click()}
            disabled={uploadingBody}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-btn border border-border bg-bg-surface px-3 py-1.5 text-xs font-semibold text-text-secondary hover:text-text-primary disabled:opacity-60"
          >
            {uploadingBody ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Uploading...
              </>
            ) : (
              <>
                <ImagePlus className="h-3.5 w-3.5" />
                Insert image
              </>
            )}
          </button>
        </div>
        <textarea
          ref={bodyTextareaRef}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          required
          rows={20}
          className="w-full rounded-btn border border-border bg-bg px-3 py-3 font-mono text-sm text-text-primary leading-relaxed focus:border-accent-yellow focus:outline-none"
          placeholder="# Heading&#10;&#10;Body markdown...&#10;&#10;![](https://...) images work too"
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
