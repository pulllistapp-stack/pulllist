"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { getToken } from "@/lib/auth";
import { NewsPost, NewsRegion } from "@/lib/news";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

type Mode = "create" | "edit";

type Props = {
  mode: Mode;
  initial?: NewsPost | null;
};

/**
 * Shared form for both /admin/news/new and /admin/news/[slug]/edit.
 * No draft state — saving always publishes (per LO). No live preview
 * either — the textarea is plain Markdown, hit Publish to see it on
 * the live /news page.
 */
export function PostForm({ mode, initial }: Props) {
  const router = useRouter();

  const [slug, setSlug] = useState(initial?.slug ?? "");
  const [title, setTitle] = useState(initial?.title ?? "");
  const [excerpt, setExcerpt] = useState(initial?.excerpt ?? "");
  const [body, setBody] = useState(initial?.body ?? "");
  const [region, setRegion] = useState<NewsRegion>(initial?.region ?? "all");
  const [category, setCategory] = useState(initial?.category ?? "");
  const [thumbnail, setThumbnail] = useState(initial?.thumbnail_url ?? "");
  const [author, setAuthor] = useState(initial?.author ?? "");
  const [publishedAt, setPublishedAt] = useState(
    initial?.published_at ?? new Date().toISOString().slice(0, 10),
  );
  const [readingTime, setReadingTime] = useState<string>(
    initial?.reading_time?.toString() ?? "",
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
        region,
        category: category || null,
        thumbnail_url: thumbnail || null,
        author: author || null,
        published_at: publishedAt,
        reading_time: readingTime ? parseInt(readingTime, 10) : null,
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
    if (!confirm(`정말 "${title}" 글을 삭제할까?`)) return;
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
      <Field label="제목" required>
        <input
          type="text"
          value={title}
          onChange={(e) => onTitleChange(e.target.value)}
          required
          className="w-full rounded-btn border border-border bg-bg px-3 py-2 text-base font-bold text-text-primary focus:border-accent-yellow focus:outline-none"
          placeholder="일판 메가에볼루션 SR/SAR 시세 정리"
        />
      </Field>

      <Field
        label="Slug (URL 경로)"
        hint="자동 생성 — 그대로 두거나 짧고 명확하게 수정"
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

      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="지역">
          <select
            value={region}
            onChange={(e) => setRegion(e.target.value as NewsRegion)}
            className="w-full rounded-btn border border-border bg-bg px-3 py-2 text-sm text-text-primary focus:border-accent-yellow focus:outline-none"
          >
            <option value="all">전체</option>
            <option value="kr">한국</option>
            <option value="ja">일본</option>
            <option value="us">미국</option>
          </select>
        </Field>
        <Field label="카테고리" hint="자유 텍스트 — 소개 / 가이드 / 시세 등">
          <input
            type="text"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="w-full rounded-btn border border-border bg-bg px-3 py-2 text-sm text-text-primary focus:border-accent-yellow focus:outline-none"
            placeholder="소개"
          />
        </Field>
      </div>

      <Field label="요약 (Excerpt)" hint="리스트 카드에 보이는 한두 줄">
        <textarea
          value={excerpt}
          onChange={(e) => setExcerpt(e.target.value)}
          rows={2}
          className="w-full rounded-btn border border-border bg-bg px-3 py-2 text-sm text-text-primary focus:border-accent-yellow focus:outline-none"
          placeholder="한 줄 요약..."
        />
      </Field>

      <Field label="썸네일 URL" hint="외부 이미지 주소를 붙여넣기 (선택)">
        <input
          type="url"
          value={thumbnail}
          onChange={(e) => setThumbnail(e.target.value)}
          className="w-full rounded-btn border border-border bg-bg px-3 py-2 font-mono text-xs text-text-primary focus:border-accent-yellow focus:outline-none"
          placeholder="https://..."
        />
      </Field>

      <Field label="본문 (Markdown)" required>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          required
          rows={20}
          className="w-full rounded-btn border border-border bg-bg px-3 py-3 font-mono text-sm text-text-primary leading-relaxed focus:border-accent-yellow focus:outline-none"
          placeholder="# 제목&#10;&#10;본문 마크다운...&#10;&#10;## 섹션&#10;&#10;![](https://...) 이미지도 됨"
        />
      </Field>

      <div className="grid gap-5 sm:grid-cols-3">
        <Field label="작성자" hint="기본: 본인 이름">
          <input
            type="text"
            value={author}
            onChange={(e) => setAuthor(e.target.value)}
            className="w-full rounded-btn border border-border bg-bg px-3 py-2 text-sm text-text-primary focus:border-accent-yellow focus:outline-none"
            placeholder="LO"
          />
        </Field>
        <Field label="게시일 (YYYY-MM-DD)" required>
          <input
            type="date"
            value={publishedAt}
            onChange={(e) => setPublishedAt(e.target.value)}
            required
            className="w-full rounded-btn border border-border bg-bg px-3 py-2 text-sm text-text-primary focus:border-accent-yellow focus:outline-none"
          />
        </Field>
        <Field label="읽기 시간 (분)">
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
            {saving ? "저장 중..." : mode === "create" ? "게시" : "수정 저장"}
          </button>
          <button
            type="button"
            onClick={() => router.push("/admin/news")}
            className="rounded-btn border border-border bg-bg-surface px-4 py-2.5 text-sm font-semibold text-text-secondary hover:text-text-primary"
          >
            취소
          </button>
        </div>
        {mode === "edit" && (
          <button
            type="button"
            onClick={onDelete}
            disabled={saving}
            className="rounded-btn border border-accent-red/40 bg-accent-red/10 px-4 py-2.5 text-sm font-semibold text-accent-red hover:bg-accent-red/20 disabled:opacity-60"
          >
            삭제
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
