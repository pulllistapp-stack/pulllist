"use client";

/**
 * /drops — Release Calendar. Shows every catalog set that carries a
 * release_date, grouped by month, sorted with upcoming releases first
 * then history descending. Country + year chips filter the timeline
 * so a KR-focused collector can scan just their region without noise.
 *
 * Data source: listSets() already returns release_date per set for
 * every language. No new backend endpoint needed — the page just
 * flattens EN + JP + KR + CN sets, filters to those with a real
 * release_date, and buckets by year-month.
 */

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Calendar, ChevronRight } from "lucide-react";

import { listSets, type CatalogRegion, type SetWithCardCount } from "@/lib/api";
import { MascotLoader } from "@/components/MascotLoader";

const REGIONS: {
  key: CatalogRegion | "all";
  label: string;
  flag: string;
}[] = [
  { key: "all", label: "All", flag: "🌐" },
  { key: "en", label: "US", flag: "🇺🇸" },
  { key: "ja", label: "JP", flag: "🇯🇵" },
  { key: "ko", label: "KR", flag: "🇰🇷" },
  { key: "zh-cn", label: "CN", flag: "🇨🇳" },
  { key: "zh-tw", label: "TW", flag: "🇹🇼" },
];

// Region → accent color used for the left rail dot next to each entry.
const REGION_COLOR: Record<string, string> = {
  en: "bg-sky-400",
  ja: "bg-rose-400",
  ko: "bg-amber-400",
  "zh-cn": "bg-emerald-400",
  "zh-tw": "bg-cyan-400",
};

const REGION_LABEL: Record<string, string> = {
  en: "US",
  ja: "JP",
  ko: "KR",
  "zh-cn": "CN",
  "zh-tw": "TW",
};

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

function isoToDate(iso: string): Date {
  // Accept "YYYY-MM-DD" or full ISO. Force UTC midnight so timezone
  // doesn't shift the display date when the browser renders it.
  return new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
}

function daysUntil(iso: string): number {
  const then = isoToDate(iso).getTime();
  const now = new Date().setUTCHours(0, 0, 0, 0);
  return Math.round((then - now) / (1000 * 60 * 60 * 24));
}

function fmtDate(iso: string): string {
  const d = isoToDate(iso);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(d.getUTCDate()).padStart(2, "0")}`;
}

export default function ReleaseCalendarPage() {
  const [rows, setRows] = useState<SetWithCardCount[]>([]);
  const [loading, setLoading] = useState(true);
  const [region, setRegion] = useState<CatalogRegion | "all">("all");
  const [year, setYear] = useState<number | "all">("all");

  // Pull every region on mount and merge — one dataset, chip filter
  // does the rest in memory. Failures per-region are non-fatal so a
  // KR-empty backend doesn't hide the EN + JP timeline.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all(
      (["en", "ja", "ko", "zh-cn", "zh-tw"] as CatalogRegion[]).map((r) =>
        listSets({ region: r }).catch(() => [] as SetWithCardCount[]),
      ),
    )
      .then((chunks) => {
        if (cancelled) return;
        const today = new Date().setUTCHours(0, 0, 0, 0);
        const merged = chunks.flat().filter((s) => {
          if (!s.release_date) return false;
          // Hide upcoming rows that don't yet have anything to show:
          // no logo yet, no cards yet, no known card_count. LO's ask —
          // Storm Emeralda / Aura Seeker / Delta Reign / FPIC S3 /
          // Special Deck Set were seeded so the calendar wouldn't lie
          // about our roadmap coverage, but until TCGCSV publishes a
          // logo or a card list the tile reads as an empty stub.
          // Carve-out: 30th Celebration family stays visible even
          // without a logo/card because LO explicitly wants the
          // worldwide-launch cluster and the US secondary waves
          // (UPC Day/Night, Battle Decks, wave aggregates) to be
          // discoverable now, artwork gaps notwithstanding.
          const releaseTs = new Date(
            s.release_date.length === 10
              ? `${s.release_date}T00:00:00Z`
              : s.release_date,
          ).getTime();
          const isFuture = releaseTs >= today;
          const isEmpty =
            !s.logo_url && (s.card_count ?? 0) === 0;
          const is30th =
            (s.series ?? "").toLowerCase().includes("30th celebration") ||
            s.id.startsWith("me30") ||
            s.id.startsWith("m30cs") ||
            s.id === "m6a";
          if (isFuture && isEmpty && !is30th) return false;
          return true;
        });
        setRows(merged);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Year chip options — derived from the actual data so we never
  // render a year that has zero entries.
  const years = useMemo(() => {
    const s = new Set<number>();
    for (const r of rows) {
      if (r.release_date) s.add(isoToDate(r.release_date).getUTCFullYear());
    }
    return [...s].sort((a, b) => b - a);
  }, [rows]);

  // Filter → sort → group by (year, month).
  const grouped = useMemo(() => {
    const filtered = rows.filter((r) => {
      if (region !== "all" && r.language !== region) return false;
      if (year !== "all") {
        if (!r.release_date) return false;
        if (isoToDate(r.release_date).getUTCFullYear() !== year) return false;
      }
      return true;
    });

    // Upcoming (delta >= 0) first descending, then past descending.
    // Both groups share the same "most recent first" ordering so the
    // eye lands on today's/tomorrow's release without extra scrolling.
    filtered.sort((a, b) => (b.release_date! > a.release_date! ? 1 : -1));

    const now = Date.now();
    const upcoming: SetWithCardCount[] = [];
    const past: SetWithCardCount[] = [];
    for (const r of filtered) {
      if (isoToDate(r.release_date!).getTime() >= now - 24 * 60 * 60 * 1000) {
        upcoming.push(r);
      } else {
        past.push(r);
      }
    }

    // Bucket into YYYY-MM. Upcoming = ascending (closest first),
    // past = descending (most recent first).
    upcoming.reverse();
    const bucket = (list: SetWithCardCount[]) => {
      const map = new Map<string, SetWithCardCount[]>();
      for (const s of list) {
        const d = isoToDate(s.release_date!);
        const key = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
        (map.get(key) ?? map.set(key, []).get(key)!).push(s);
      }
      return [...map.entries()];
    };

    return {
      upcoming: bucket(upcoming),
      past: bucket(past),
      count: filtered.length,
      upcomingCount: upcoming.length,
    };
  }, [rows, region, year]);

  return (
    <main className="mx-auto max-w-4xl px-4 py-8 pb-24">
      <header className="mb-6">
        <div className="flex items-center gap-2 mb-2">
          <Calendar className="h-5 w-5 text-accent-yellow" />
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-text-primary">
            Release Calendar
          </h1>
        </div>
        <p className="text-sm text-text-secondary">
          Every Pokémon TCG set release we track, grouped by month.
          {grouped.count > 0 && (
            <>
              {" "}
              <span className="font-mono text-text-tertiary">
                {grouped.count} sets
              </span>
              {grouped.upcomingCount > 0 && (
                <>
                  {" · "}
                  <span className="font-mono text-accent-green">
                    {grouped.upcomingCount} upcoming
                  </span>
                </>
              )}
            </>
          )}
        </p>
      </header>

      {/* Region chips */}
      <div className="flex flex-wrap gap-2 mb-3">
        {REGIONS.map((r) => (
          <button
            key={r.key}
            type="button"
            onClick={() => setRegion(r.key)}
            className={
              "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-mono uppercase tracking-wider font-semibold transition-colors " +
              (region === r.key
                ? "border-accent-yellow bg-accent-yellow/10 text-text-primary"
                : "border-border bg-bg-surface text-text-secondary hover:text-text-primary")
            }
          >
            <span aria-hidden>{r.flag}</span>
            {r.label}
          </button>
        ))}
      </div>

      {/* Year chips — All + descending years present in data */}
      {years.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-6 overflow-x-auto pb-1">
          <button
            type="button"
            onClick={() => setYear("all")}
            className={
              "inline-flex items-center rounded-full border px-3 py-1 text-[11px] font-mono uppercase tracking-wider font-semibold transition-colors " +
              (year === "all"
                ? "border-accent-yellow bg-accent-yellow/10 text-text-primary"
                : "border-border bg-bg-surface text-text-secondary hover:text-text-primary")
            }
          >
            All
          </button>
          {years.map((y) => (
            <button
              key={y}
              type="button"
              onClick={() => setYear(y)}
              className={
                "inline-flex items-center rounded-full border px-3 py-1 text-[11px] font-mono uppercase tracking-wider font-semibold transition-colors " +
                (year === y
                  ? "border-accent-yellow bg-accent-yellow/10 text-text-primary"
                  : "border-border bg-bg-surface text-text-secondary hover:text-text-primary")
              }
            >
              {y}
            </button>
          ))}
        </div>
      )}

      {/* Timeline */}
      {loading ? (
        <MascotLoader size="md" className="py-16" />
      ) : grouped.count === 0 ? (
        <div className="rounded-2xl border border-dashed border-border/60 bg-bg-surface/40 p-8 text-center text-text-tertiary">
          No releases match the current filter.
        </div>
      ) : (
        <>
          {grouped.upcoming.length > 0 && (
            <TimelineSection label="Upcoming" months={grouped.upcoming} />
          )}
          {grouped.past.length > 0 && (
            <TimelineSection label="Past releases" months={grouped.past} muted />
          )}
        </>
      )}
    </main>
  );
}

function TimelineSection({
  label,
  months,
  muted = false,
}: {
  label: string;
  months: [string, SetWithCardCount[]][];
  muted?: boolean;
}) {
  return (
    <section className={muted ? "mt-10" : "mt-2"}>
      <h2
        className={
          "mb-3 text-[11px] font-mono uppercase tracking-wider font-bold " +
          (muted ? "text-text-tertiary" : "text-accent-green")
        }
      >
        {label}
      </h2>
      {months.map(([key, entries]) => {
        const [y, m] = key.split("-");
        const monthLabel = `${MONTH_NAMES[Number(m) - 1]} ${y}`;
        return (
          <div key={key} className="mb-8">
            <div className="flex items-baseline gap-2 mb-3">
              <h3 className="text-base font-bold text-text-primary">
                {monthLabel}
              </h3>
              <span className="text-xs font-mono text-text-tertiary">
                {entries.length} {entries.length === 1 ? "set" : "sets"}
              </span>
            </div>
            <ol className="space-y-2">
              {entries.map((s) => (
                <TimelineRow key={`${s.language}-${s.id}`} s={s} />
              ))}
            </ol>
          </div>
        );
      })}
    </section>
  );
}

function TimelineRow({ s }: { s: SetWithCardCount }) {
  const delta = daysUntil(s.release_date!);
  const dot = REGION_COLOR[s.language] ?? "bg-text-tertiary";
  const displayName = s.language === "ko" ? s.name_ko ?? s.name : s.name;
  const isUpcoming = delta > 0;
  const isToday = delta === 0;
  return (
    <li>
      <Link
        href={`/sets/${s.id}`}
        className="flex items-center gap-3 rounded-2xl border border-border bg-bg-surface p-3 transition-colors hover:border-accent-yellow/40 hover:bg-bg-surface/80"
      >
        <span
          className={`h-2.5 w-2.5 shrink-0 rounded-full ${dot} ${
            isUpcoming ? "animate-pulse" : "opacity-60"
          }`}
          aria-hidden
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-text-tertiary mb-0.5">
            <span>{fmtDate(s.release_date!)}</span>
            <span>·</span>
            <span>{REGION_LABEL[s.language] ?? s.language.toUpperCase()}</span>
            {(isToday || isUpcoming) && (
              <>
                <span>·</span>
                <span
                  className={
                    isToday
                      ? "text-accent-green font-bold"
                      : "text-accent-yellow"
                  }
                >
                  {isToday ? "TODAY" : `D-${delta}`}
                </span>
              </>
            )}
          </div>
          <div className="font-semibold text-text-primary truncate">
            {displayName}
          </div>
          {s.series && (
            <div className="text-[11px] text-text-tertiary truncate">
              {s.series}
            </div>
          )}
        </div>
        {s.printed_total != null && s.printed_total > 0 && (
          <span className="shrink-0 rounded-full border border-border bg-bg px-2 py-0.5 text-[10px] font-mono text-text-tertiary uppercase tracking-wider">
            {s.printed_total} cards
          </span>
        )}
        {s.logo_url && (
          <div className="relative h-8 w-16 shrink-0">
            <Image
              src={s.logo_url}
              alt={displayName}
              fill
              sizes="64px"
              className="object-contain"
              unoptimized
            />
          </div>
        )}
        <ChevronRight className="h-4 w-4 text-text-tertiary shrink-0" />
      </Link>
    </li>
  );
}
