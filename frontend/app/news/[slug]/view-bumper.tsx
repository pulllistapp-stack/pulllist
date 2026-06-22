"use client";

import { useEffect } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

/**
 * Fire-and-forget POST that increments the news_views counter the
 * first time a slug renders on the client. We dedupe per slug for the
 * lifetime of the tab via sessionStorage so a reader bouncing between
 * pages and back doesn't keep padding the count.
 */
export function ViewBumper({ slug }: { slug: string }) {
  useEffect(() => {
    if (!slug) return;
    const key = `news_view_bumped:${slug}`;
    try {
      if (sessionStorage.getItem(key)) return;
      sessionStorage.setItem(key, "1");
    } catch {
      // Private mode / blocked storage — just skip the dedupe and let
      // the post-request hit; the worst case is a small over-count.
    }
    fetch(`${API_BASE}/news/views/${encodeURIComponent(slug)}`, {
      method: "POST",
      keepalive: true,
    }).catch(() => {
      // View tracking is best-effort. Never surface failures.
    });
  }, [slug]);

  return null;
}
