"use client";

import { useMemo, useState } from "react";
import { Globe } from "lucide-react";

import { AdminGuard } from "@/components/admin/AdminGuard";
import { UPDATES, type UpdateEntry } from "@/lib/updates";
import { cn } from "@/lib/utils";

type Lang = "kr" | "en";

export default function AdminUpdatesPage() {
  return (
    <AdminGuard>
      <AdminUpdatesContent />
    </AdminGuard>
  );
}

function AdminUpdatesContent() {
  const [lang, setLang] = useState<Lang>("kr");

  // Group by date — newest day first, entries within a day keep
  // source-file order (which the maintainer arranges by recency too).
  const groups = useMemo(() => {
    const byDate = new Map<string, UpdateEntry[]>();
    for (const e of UPDATES) {
      const arr = byDate.get(e.date) ?? [];
      arr.push(e);
      byDate.set(e.date, arr);
    }
    return Array.from(byDate.entries()).sort((a, b) =>
      b[0].localeCompare(a[0]),
    );
  }, []);

  const todayIso = new Date().toISOString().slice(0, 10);
  const yesterdayIso = new Date(Date.now() - 86_400_000)
    .toISOString()
    .slice(0, 10);

  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      <div className="flex items-start justify-between gap-4 mb-2">
        <div>
          <h1 className="text-2xl font-bold">
            {lang === "kr" ? "업데이트 내역" : "Update log"}
          </h1>
          <p className="mt-1 text-sm text-text-secondary">
            {lang === "kr"
              ? "PullList에 새로 추가되거나 개선된 내용이에요"
              : "What's new and improved on PullList"}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setLang(lang === "kr" ? "en" : "kr")}
          className="inline-flex items-center gap-1.5 rounded-full border border-border bg-bg-surface px-3 py-1.5 text-xs font-mono uppercase tracking-wider hover:border-accent-yellow/50 transition-colors"
        >
          <Globe className="h-3 w-3" />
          {lang === "kr" ? "EN" : "KR"}
        </button>
      </div>

      <div className="mt-8 space-y-8">
        {groups.map(([date, entries]) => (
          <section key={date}>
            <h2 className="mb-3 text-sm font-semibold text-text-secondary">
              {formatDateHeader(date, lang, todayIso, yesterdayIso)}
            </h2>
            <ul className="space-y-2">
              {entries.map((e, idx) => (
                <li
                  key={`${e.date}-${idx}`}
                  className={cn(
                    "flex items-start gap-3 rounded-card bg-bg-surface",
                    "border border-border px-4 py-3",
                  )}
                >
                  {e.time && (
                    <span className="shrink-0 font-mono text-xs text-text-tertiary tabular-nums mt-0.5">
                      {e.time}
                    </span>
                  )}
                  <span className="text-sm leading-relaxed">
                    {e.emoji && <span className="mr-1.5">{e.emoji}</span>}
                    {lang === "kr" ? e.kr : e.en}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>

      <p className="mt-12 text-center text-xs text-text-tertiary">
        {lang === "kr"
          ? `총 ${UPDATES.length}개 업데이트`
          : `${UPDATES.length} updates total`}
      </p>
    </main>
  );
}

function formatDateHeader(
  iso: string,
  lang: Lang,
  todayIso: string,
  yesterdayIso: string,
): string {
  if (iso === todayIso) return lang === "kr" ? "오늘" : "Today";
  if (iso === yesterdayIso) return lang === "kr" ? "어제" : "Yesterday";

  const [y, m, d] = iso.split("-").map((s) => parseInt(s, 10));
  if (lang === "kr") {
    return `${y}년 ${m}월 ${d}일`;
  }
  const months = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
  ];
  return `${months[m - 1]} ${d}, ${y}`;
}
