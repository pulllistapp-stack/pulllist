"use client";

import { useCallback, useEffect, useState } from "react";
import { Activity, Globe, Loader2, ShieldAlert } from "lucide-react";

import { AdminGuard } from "@/components/admin/AdminGuard";
import {
  getVisitsAnonSessions,
  getVisitsBots,
  getVisitsRecent,
  getVisitsSummary,
  getVisitsTopPaths,
  getVisitsTopReferrers,
  getVisitsVisitors,
  type AnonSessionItem,
  type BotItem,
  type TopPathItem,
  type TopReferrerItem,
  type VisitRecentItem,
  type VisitorItem,
  type VisitScope,
  type VisitsSummary,
} from "@/lib/auth";
import { cn } from "@/lib/utils";

export default function AdminVisitsPage() {
  return (
    <AdminGuard>
      <AdminVisitsContent />
    </AdminGuard>
  );
}

function AdminVisitsContent() {
  const [summary, setSummary] = useState<VisitsSummary | null>(null);
  const [visitors, setVisitors] = useState<VisitorItem[]>([]);
  const [topPaths, setTopPaths] = useState<TopPathItem[]>([]);
  const [topReferrers, setTopReferrers] = useState<TopReferrerItem[]>([]);
  const [recent, setRecent] = useState<VisitRecentItem[]>([]);
  const [anonSessions, setAnonSessions] = useState<AnonSessionItem[]>([]);
  const [bots, setBots] = useState<BotItem[]>([]);
  const [windowDays, setWindowDays] = useState<number>(1);
  const [scope, setScope] = useState<VisitScope>("all");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, v, tp, tr, rec, anon, bt] = await Promise.all([
        getVisitsSummary(),
        getVisitsVisitors(windowDays, 60),
        getVisitsTopPaths(windowDays, 15),
        getVisitsTopReferrers(windowDays, 15),
        getVisitsRecent({ limit: 60, scope }),
        getVisitsAnonSessions(windowDays, 30),
        getVisitsBots(windowDays),
      ]);
      setSummary(s);
      setVisitors(v.items);
      setTopPaths(tp.items);
      setTopReferrers(tr.items);
      setRecent(rec.items);
      setAnonSessions(anon.items);
      setBots(bt.items);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [windowDays, scope]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <main className="mx-auto max-w-6xl px-4 sm:px-6 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-extrabold tracking-tight text-text-primary">
          Visits
        </h1>
        <p className="mt-1 text-sm text-text-secondary">
          Site traffic — both signed-in users and anonymous visitors. Geo
          comes from edge headers, no IPs stored.
        </p>
      </div>

      {loading || !summary ? (
        <div className="flex items-center justify-center py-12 text-text-tertiary">
          <Loader2 className="h-5 w-5 animate-spin" />
        </div>
      ) : (
        <>
          {/* Top stat cards */}
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 mb-8">
            <StatCard
              label="Views today"
              value={summary.views.today.toLocaleString()}
              hint={`yesterday ${summary.views.yesterday.toLocaleString()}`}
            />
            <StatCard
              label="Unique today"
              value={summary.uniques.today.toLocaleString()}
              hint={`yesterday ${summary.uniques.yesterday.toLocaleString()}`}
            />
            <StatCard
              label="7-day views"
              value={summary.views.week.toLocaleString()}
              hint={`${summary.uniques.week.toLocaleString()} unique`}
              wide
            />
          </div>

          {/* 7d sparkline (text-based for now) */}
          {summary.daily_7d.length > 0 && (
            <section className="mb-8">
              <h2 className="text-sm font-mono uppercase tracking-wider text-text-tertiary mb-3">
                Last 7 days
              </h2>
              <div className="rounded-card border border-border bg-bg-surface p-4">
                <DailyBars data={summary.daily_7d} />
              </div>
            </section>
          )}

          {/* Country breakdown */}
          <section className="mb-8">
            <div className="flex items-baseline justify-between mb-3">
              <h2 className="text-sm font-mono uppercase tracking-wider text-text-tertiary inline-flex items-center gap-1.5">
                <Globe className="h-3.5 w-3.5" />
                Today by country
              </h2>
              <span className="text-xs font-mono text-text-tertiary">
                top {summary.countries_today.length}
              </span>
            </div>
            {summary.countries_today.length === 0 ? (
              <p className="text-sm text-text-tertiary italic">
                No visits today yet.
              </p>
            ) : (
              <ul className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {summary.countries_today.map((c) => (
                  <li
                    key={c.country}
                    className={cn(
                      "rounded-card border bg-bg-surface px-3 py-2 flex items-center justify-between",
                      isSuspicious(c.country)
                        ? "border-accent-red/40"
                        : "border-border",
                    )}
                  >
                    <span className="text-sm font-bold">
                      {countryFlag(c.country)} {c.country}
                    </span>
                    <span className="text-xs font-mono text-text-secondary">
                      {c.count}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* Per-user breakdown */}
          <section>
            <div className="flex items-baseline justify-between mb-3 gap-3 flex-wrap">
              <h2 className="text-sm font-mono uppercase tracking-wider text-text-tertiary inline-flex items-center gap-1.5">
                <Activity className="h-3.5 w-3.5" />
                Visitors
              </h2>
              <div className="inline-flex gap-1 rounded-full border border-border bg-bg-surface p-1">
                {[1, 7, 30].map((d) => (
                  <button
                    key={d}
                    onClick={() => setWindowDays(d)}
                    className={cn(
                      "rounded-full px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider transition-colors",
                      windowDays === d
                        ? "bg-accent-yellow text-gray-900"
                        : "text-text-secondary hover:text-text-primary",
                    )}
                  >
                    {d}d
                  </button>
                ))}
              </div>
            </div>
            {visitors.length === 0 ? (
              <p className="text-sm text-text-tertiary italic">
                No visits in this window.
              </p>
            ) : (
              <>
              {/* Mobile: per-visitor card list — signed-in + anon merged,
                  all fields visible without a swipe-to-scroll gesture. */}
              <ul className="sm:hidden space-y-2">
                {visitors.map((v) => {
                  const isAnon = v.type === "anon";
                  return (
                  <li
                    key={v.id}
                    className={cn(
                      "rounded-card border border-border p-3",
                      isAnon ? "bg-bg-surface/60 opacity-80" : "bg-bg-surface",
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span
                            className={cn(
                              "truncate",
                              isAnon
                                ? "font-mono text-text-tertiary"
                                : "font-bold text-text-primary",
                            )}
                          >
                            {isAnon
                              ? `anon-${(v.session_id ?? "").slice(0, 8)}`
                              : (v.name ?? v.email ?? (v.user_id ?? "").slice(0, 8))}
                          </span>
                          {v.is_admin && (
                            <span className="shrink-0 rounded-full bg-accent-yellow/15 text-accent-yellow text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5">
                              Admin
                            </span>
                          )}
                          {isAnon && (
                            <span className="shrink-0 rounded-full bg-neutral-500/10 text-text-tertiary text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5">
                              Anon
                            </span>
                          )}
                        </div>
                        {!isAnon && v.email && v.name && (
                          <p className="mt-0.5 text-[11px] font-mono text-text-tertiary truncate">
                            {v.email}
                          </p>
                        )}
                      </div>
                      <div className="text-right shrink-0">
                        <p
                          className={cn(
                            "font-mono font-bold text-lg leading-none",
                            isAnon ? "text-text-secondary" : "text-text-primary",
                          )}
                        >
                          {v.views}
                        </p>
                        <p className="text-[10px] font-mono text-text-tertiary uppercase tracking-wider">
                          views
                        </p>
                      </div>
                    </div>
                    <div className="mt-2 flex items-center justify-between gap-2 text-[11px] font-mono text-text-tertiary">
                      <span
                        className={cn(
                          isSuspicious(v.last_country)
                            ? "text-accent-red font-bold"
                            : "text-text-secondary",
                        )}
                      >
                        {isSuspicious(v.last_country) && (
                          <ShieldAlert className="inline h-3 w-3 mr-1" />
                        )}
                        {countryFlag(v.last_country)}{" "}
                        {v.last_country ?? "??"}
                      </span>
                      <span>
                        last{" "}
                        {v.last_seen
                          ? formatRelative(new Date(v.last_seen))
                          : "—"}
                      </span>
                    </div>
                  </li>
                  );
                })}
              </ul>

              {/* Desktop: original table with horizontal scroll fallback.
                  Anonymous rows sit in the same table body but rendered
                  in a muted tone so signed-in accounts still stand out. */}
              <div className="hidden sm:block rounded-card border border-border bg-bg-surface overflow-hidden">
                <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border bg-bg/40 text-[11px] font-mono uppercase tracking-wider text-text-tertiary">
                      <th className="text-left px-3 py-2">Visitor</th>
                      <th className="text-right px-3 py-2">Views</th>
                      <th className="text-right px-3 py-2 hidden sm:table-cell">
                        Last seen
                      </th>
                      <th className="text-right px-3 py-2">Country</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visitors.map((v) => {
                      const isAnon = v.type === "anon";
                      return (
                      <tr
                        key={v.id}
                        className={cn(
                          "border-b border-border last:border-0",
                          isAnon && "bg-bg/20",
                        )}
                      >
                        <td className="px-3 py-2">
                          <div className="flex items-center gap-2">
                            <span
                              className={cn(
                                "truncate max-w-[200px]",
                                isAnon
                                  ? "font-mono text-text-tertiary"
                                  : "font-bold text-text-primary",
                              )}
                            >
                              {isAnon
                                ? `anon-${(v.session_id ?? "").slice(0, 8)}`
                                : (v.name ?? v.email ?? (v.user_id ?? "").slice(0, 8))}
                            </span>
                            {v.is_admin && (
                              <span className="rounded-full bg-accent-yellow/15 text-accent-yellow text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5">
                                Admin
                              </span>
                            )}
                            {isAnon && (
                              <span className="rounded-full bg-neutral-500/10 text-text-tertiary text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5">
                                Anon
                              </span>
                            )}
                          </div>
                          {!isAnon && v.email && v.name && (
                            <span className="block text-[11px] font-mono text-text-tertiary truncate max-w-[260px]">
                              {v.email}
                            </span>
                          )}
                        </td>
                        <td
                          className={cn(
                            "text-right px-3 py-2 font-mono font-bold",
                            isAnon ? "text-text-secondary" : "text-text-primary",
                          )}
                        >
                          {v.views}
                        </td>
                        <td className="text-right px-3 py-2 font-mono text-[11px] text-text-tertiary hidden sm:table-cell">
                          {v.last_seen ? formatRelative(new Date(v.last_seen)) : "—"}
                        </td>
                        <td
                          className={cn(
                            "text-right px-3 py-2 font-mono text-xs",
                            isSuspicious(v.last_country)
                              ? "text-accent-red font-bold"
                              : "text-text-secondary",
                          )}
                          title={
                            isSuspicious(v.last_country)
                              ? "Flagged country — review activity"
                              : undefined
                          }
                        >
                          {isSuspicious(v.last_country) && (
                            <ShieldAlert className="inline h-3 w-3 mr-1" />
                          )}
                          {countryFlag(v.last_country)} {v.last_country ?? "??"}
                        </td>
                      </tr>
                      );
                    })}
                  </tbody>
                </table>
                </div>
              </div>
              </>
            )}
          </section>

          {/* Top pages + Top referrers side by side */}
          <section className="grid gap-4 md:grid-cols-2 mt-8">
            <TrafficCard title="Top pages" hint={`Last ${windowDays}d`}>
              {topPaths.length === 0 ? (
                <EmptyRow />
              ) : (
                <ul className="text-xs divide-y divide-border">
                  {topPaths.map((p) => (
                    <li key={p.path} className="py-2 min-w-0 overflow-hidden">
                      {/* Long URLs (/news/ascended-heroes-focused-…)
                          were sliding past the viewport because the
                          previous flex row let the metrics keep their
                          intrinsic width and the path never had a
                          real ceiling to shrink into. Full-width path
                          on its own line + metrics under = truncate
                          works, no swipe needed on mobile. */}
                      <p className="block w-full font-mono text-text-primary truncate">
                        {p.path}
                      </p>
                      <p className="mt-0.5 font-mono text-[10px] text-text-tertiary tabular-nums">
                        {p.views.toLocaleString()} views ·{" "}
                        {p.uniques.toLocaleString()} unique
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </TrafficCard>

            <TrafficCard title="Top referrers" hint={`Last ${windowDays}d`}>
              {topReferrers.length === 0 ? (
                <EmptyRow />
              ) : (
                <ul className="text-xs divide-y divide-border">
                  {topReferrers.map((r) => (
                    <li
                      key={r.domain}
                      className="py-2 min-w-0 overflow-hidden"
                    >
                      <p
                        className={cn(
                          "block w-full font-mono truncate",
                          r.domain === "direct"
                            ? "text-text-tertiary italic"
                            : "text-text-primary",
                        )}
                      >
                        {r.domain}
                      </p>
                      <p className="mt-0.5 font-mono text-[10px] text-text-tertiary tabular-nums">
                        {r.views.toLocaleString()} views ·{" "}
                        {r.uniques.toLocaleString()} unique
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </TrafficCard>

          </section>

          {/* Bot traffic breakdown — server-side UA classification.
              Only rows with a recognized bot name reach this table; the
              category tag drives the color chip. */}
          <section className="mt-8">
            <TrafficCard
              title="Bot activity"
              hint={`Last ${windowDays}d · server-side UA match`}
            >
              {bots.length === 0 ? (
                <EmptyRow />
              ) : (
                <ul className="text-xs divide-y divide-border">
                  {bots.map((b) => (
                    <li
                      key={b.bot_name}
                      className="py-2 flex items-center gap-3 min-w-0"
                    >
                      <BotCategoryChip category={b.category} />
                      <span className="font-mono text-text-primary truncate flex-1 min-w-0">
                        {b.bot_name}
                      </span>
                      <span className="font-mono text-[10px] text-text-tertiary tabular-nums shrink-0">
                        {b.views.toLocaleString()} views
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </TrafficCard>
          </section>

          {/* Anonymous sessions — who's been on the site not signed in */}
          <section className="mt-8">
            <div className="mb-3 flex items-baseline justify-between">
              <h2 className="text-lg font-bold text-text-primary">
                Anonymous sessions
              </h2>
              <span className="text-[10px] font-mono text-text-tertiary uppercase tracking-wider">
                Last {windowDays}d · latest 30
              </span>
            </div>
            {anonSessions.length === 0 ? (
              <div className="rounded-card border border-border bg-bg-surface p-6 text-center text-sm text-text-tertiary">
                No anonymous sessions in this window.
              </div>
            ) : (
              <>
              {/* Mobile: card per session — all 7 fields visible via
                  compact vertical stacking + inline chips. */}
              <ul className="sm:hidden space-y-2">
                {anonSessions.map((s) => (
                  <li
                    key={s.session_id}
                    className="rounded-card border border-border bg-bg-surface p-3"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <p className="font-mono text-[11px] text-text-tertiary">
                          {s.session_id.slice(0, 12)}…
                        </p>
                        <p className="mt-0.5 font-mono text-xs text-text-primary break-all">
                          {s.entry_path ?? "—"}
                        </p>
                      </div>
                      <div className="text-right shrink-0">
                        <p className="font-mono font-bold text-text-primary text-base leading-none">
                          {s.views}
                        </p>
                        <p className="text-[9px] font-mono text-text-tertiary uppercase">
                          views
                        </p>
                      </div>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-x-2 gap-y-0.5 text-[11px] text-text-secondary">
                      <span className="font-mono">
                        {countryFlag(s.country ?? null)}{" "}
                        {s.country ?? "??"}
                        {s.city ? ` · ${s.city}` : ""}
                      </span>
                      <span>· {s.device ?? "—"}</span>
                      <span className="font-mono text-text-tertiary">
                        ·{" "}
                        {s.last_seen ? relativeTime(s.last_seen) : "—"}
                      </span>
                    </div>
                    <p className="mt-1 font-mono text-[10px] text-text-tertiary break-all">
                      ref: {s.entry_referrer ?? "direct"}
                    </p>
                  </li>
                ))}
              </ul>

              {/* Desktop: full table. */}
              <div className="hidden sm:block rounded-card border border-border bg-bg-surface overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead className="bg-bg-elevated text-text-tertiary uppercase tracking-wider">
                      <tr>
                        <th className="text-left px-3 py-2 font-mono">Session</th>
                        <th className="text-left px-3 py-2 font-mono">
                          Entry path
                        </th>
                        <th className="text-left px-3 py-2 font-mono">
                          Referrer
                        </th>
                        <th className="text-left px-3 py-2 font-mono">Where</th>
                        <th className="text-left px-3 py-2 font-mono">Device</th>
                        <th className="text-right px-3 py-2 font-mono">Views</th>
                        <th className="text-right px-3 py-2 font-mono">
                          Last seen
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {anonSessions.map((s) => (
                        <tr key={s.session_id} className="hover:bg-bg/40">
                          <td className="px-3 py-2 font-mono text-text-tertiary">
                            {s.session_id.slice(0, 8)}…
                          </td>
                          <td className="px-3 py-2 font-mono text-text-primary max-w-[240px] truncate">
                            {s.entry_path ?? "—"}
                          </td>
                          <td className="px-3 py-2 font-mono text-text-secondary max-w-[160px] truncate">
                            {s.entry_referrer ?? "direct"}
                          </td>
                          <td className="px-3 py-2 text-text-secondary">
                            {countryFlag(s.country ?? null)} {s.country ?? "??"}
                            {s.city ? ` · ${s.city}` : ""}
                          </td>
                          <td className="px-3 py-2 text-text-secondary">
                            {s.device ?? "—"}
                          </td>
                          <td className="px-3 py-2 text-right font-mono tabular-nums">
                            {s.views}
                          </td>
                          <td className="px-3 py-2 text-right font-mono text-text-tertiary">
                            {s.last_seen ? relativeTime(s.last_seen) : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
              </>
            )}
          </section>

          {/* Recent stream — mixed feed with scope toggle */}
          <section className="mt-8">
            <div className="mb-3 flex items-baseline justify-between gap-2 flex-wrap">
              <h2 className="text-lg font-bold text-text-primary">
                Recent activity
              </h2>
              <div className="inline-flex gap-1 rounded-full border border-border bg-bg-surface p-1">
                {(["all", "user", "anon"] as VisitScope[]).map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setScope(s)}
                    className={cn(
                      "rounded-full px-3 py-1 text-[11px] font-bold uppercase tracking-wider transition-colors",
                      scope === s
                        ? "bg-accent-yellow text-gray-900"
                        : "text-text-secondary hover:text-text-primary",
                    )}
                  >
                    {s === "all" ? "All" : s === "user" ? "Signed-in" : "Anonymous"}
                  </button>
                ))}
              </div>
            </div>
            {/* Mobile: card per activity — all 6 fields visible. */}
            <ul className="sm:hidden space-y-2">
              {recent.length === 0 ? (
                <li className="rounded-card border border-border bg-bg-surface p-6 text-center text-sm text-text-tertiary">
                  No visits match this filter.
                </li>
              ) : (
                recent.map((v) => (
                  <li
                    key={v.id}
                    className="rounded-card border border-border bg-bg-surface p-3"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <p className="text-[11px]">
                          {v.is_anonymous ? (
                            <span className="text-text-tertiary italic">
                              anon
                            </span>
                          ) : (
                            <span className="text-text-primary font-bold">
                              {v.user?.name ?? v.user?.email ?? "user"}
                            </span>
                          )}
                        </p>
                        <p className="mt-0.5 font-mono text-xs text-text-primary break-all">
                          {v.path}
                        </p>
                      </div>
                      <span className="shrink-0 font-mono text-[10px] text-text-tertiary">
                        {relativeTime(v.created_at)}
                      </span>
                    </div>
                    <div className="mt-1.5 flex flex-wrap gap-x-2 gap-y-0.5 text-[10px] font-mono text-text-secondary">
                      <span>
                        {countryFlag(v.country ?? null)}{" "}
                        {v.country ?? "??"}
                      </span>
                      <span>· {v.device ?? "—"}</span>
                      <span className="text-text-tertiary break-all">
                        · ref: {v.referrer ? shortHost(v.referrer) : "direct"}
                      </span>
                    </div>
                  </li>
                ))
              )}
            </ul>

            {/* Desktop: full table. */}
            <div className="hidden sm:block rounded-card border border-border bg-bg-surface overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="bg-bg-elevated text-text-tertiary uppercase tracking-wider">
                    <tr>
                      <th className="text-left px-3 py-2 font-mono">Time</th>
                      <th className="text-left px-3 py-2 font-mono">Who</th>
                      <th className="text-left px-3 py-2 font-mono">Path</th>
                      <th className="text-left px-3 py-2 font-mono">Referrer</th>
                      <th className="text-left px-3 py-2 font-mono">Where</th>
                      <th className="text-left px-3 py-2 font-mono">Device</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {recent.length === 0 ? (
                      <tr>
                        <td
                          className="px-3 py-6 text-center text-text-tertiary"
                          colSpan={6}
                        >
                          No visits match this filter.
                        </td>
                      </tr>
                    ) : (
                      recent.map((v) => (
                        <tr key={v.id} className="hover:bg-bg/40">
                          <td className="px-3 py-2 font-mono text-text-tertiary whitespace-nowrap">
                            {relativeTime(v.created_at)}
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap">
                            {v.is_anonymous ? (
                              <span className="text-text-tertiary italic">
                                anon
                              </span>
                            ) : (
                              <span className="text-text-primary">
                                {v.user?.name ?? v.user?.email ?? "user"}
                              </span>
                            )}
                          </td>
                          <td className="px-3 py-2 font-mono text-text-primary max-w-[280px] truncate">
                            {v.path}
                          </td>
                          <td className="px-3 py-2 font-mono text-text-secondary max-w-[200px] truncate">
                            {v.referrer ? shortHost(v.referrer) : "direct"}
                          </td>
                          <td className="px-3 py-2 text-text-secondary whitespace-nowrap">
                            {countryFlag(v.country ?? null)} {v.country ?? "??"}
                          </td>
                          <td className="px-3 py-2 text-text-secondary">
                            {v.device ?? "—"}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        </>
      )}
    </main>
  );
}

function TrafficCard({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-card border border-border bg-bg-surface p-4 overflow-hidden min-w-0">
      <div className="mb-2 flex items-baseline justify-between">
        <h2 className="text-sm font-bold text-text-primary">{title}</h2>
        {hint && (
          <span className="text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
            {hint}
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

function EmptyRow() {
  return (
    <div className="py-6 text-center text-sm text-text-tertiary">No data.</div>
  );
}

function shortHost(referrer: string): string {
  try {
    const u = referrer.startsWith("http") ? new URL(referrer) : null;
    return u ? u.hostname : referrer;
  } catch {
    return referrer;
  }
}

function relativeTime(iso: string): string {
  const t = new Date(iso).getTime();
  // Clamp to 0 so a slight server/client clock skew (visit rows can
  // land a few seconds in the client's "future") doesn't render as
  // '-1437s'. LO explicitly wanted the seconds visible even for
  // very-recent rows, so no "just now" swallow — always show a
  // concrete number in the smallest unit that fits.
  const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

function StatCard({
  label,
  value,
  hint,
  wide,
}: {
  label: string;
  value: string;
  hint?: string;
  wide?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-card border border-border bg-bg-surface px-4 py-3",
        wide && "col-span-2 lg:col-span-1",
      )}
    >
      <p className="text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
        {label}
      </p>
      <p className="mt-1 text-2xl font-extrabold text-text-primary tabular-nums">
        {value}
      </p>
      {hint && (
        <p className="mt-0.5 text-[11px] font-mono text-text-tertiary">{hint}</p>
      )}
    </div>
  );
}

function DailyBars({
  data,
}: {
  data: { date: string; views: number; uniques: number }[];
}) {
  const maxViews = Math.max(...data.map((d) => d.views), 1);
  // 96px container height − ~14px reserved for the date label = ~82px of
  // vertical room for the tallest bar. Compute pixel heights directly
  // because a percentage inside a `flex-1` parent doesn't resolve — the
  // parent's height stays `auto` and every bar rendered at 0px, leaving
  // the whole 7-day strip visually empty.
  const MAX_BAR_PX = 82;
  const MIN_BAR_PX = 2;
  return (
    <div className="flex items-end gap-1.5 h-24">
      {data.map((d) => {
        const ratio = d.views / maxViews;
        const barPx = Math.max(Math.round(ratio * MAX_BAR_PX), MIN_BAR_PX);
        return (
          <div
            key={d.date}
            className="flex-1 flex flex-col items-center gap-1 h-full justify-end"
            title={`${d.date}: ${d.views} views, ${d.uniques} unique`}
          >
            <div
              className="w-full rounded-t-md bg-accent-yellow/60 hover:bg-accent-yellow transition-colors"
              style={{ height: `${barPx}px` }}
            />
            <span className="text-[9px] font-mono text-text-tertiary">
              {d.date.slice(5)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/** Countries we currently want surfaced as red-flag for additional
 *  review. Not a block — just a visual ShieldAlert + red text. */
const SUSPICIOUS = new Set(["CN", "RU", "KP", "IR"]);
function isSuspicious(country: string | null | undefined): boolean {
  return !!country && SUSPICIOUS.has(country.toUpperCase());
}

function countryFlag(code: string | null | undefined): string {
  if (!code || code.length !== 2) return "🏳";
  const A = 0x1f1e6;
  const cc = code.toUpperCase();
  return (
    String.fromCodePoint(A + cc.charCodeAt(0) - 65) +
    String.fromCodePoint(A + cc.charCodeAt(1) - 65)
  );
}

// Bot category → chip label + color. Categories come from the backend
// so this only styles what's already been classified server-side.
const BOT_CATEGORY_STYLE: Record<
  BotItem["category"],
  { label: string; className: string }
> = {
  search: {
    label: "search",
    className: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  },
  llm: {
    label: "llm",
    className: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  },
  seo: {
    label: "seo",
    className: "bg-orange-500/15 text-orange-700 dark:text-orange-400",
  },
  social: {
    label: "social",
    className: "bg-sky-500/10 text-sky-600 dark:text-sky-400",
  },
  monitor: {
    label: "monitor",
    className: "bg-violet-500/10 text-violet-600 dark:text-violet-400",
  },
  other: {
    label: "other",
    className: "bg-neutral-500/10 text-text-tertiary",
  },
};

function BotCategoryChip({ category }: { category: BotItem["category"] }) {
  const style = BOT_CATEGORY_STYLE[category];
  return (
    <span
      className={cn(
        "inline-flex shrink-0 rounded px-1.5 py-0.5 text-[9px] font-mono uppercase tracking-wide",
        style.className,
      )}
    >
      {style.label}
    </span>
  );
}

function formatRelative(d: Date): string {
  // Clamp to 0 — server-serialized timestamps sometimes land a few
  // seconds in the client's "future" thanks to clock skew, and we'd
  // rather render "0s ago" than "-14297s ago".
  const diffMs = Math.max(0, Date.now() - d.getTime());
  const s = Math.floor(diffMs / 1000);
  if (s < 60) return `${s}s ago`;
  const min = Math.floor(s / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day}d ago`;
  return d.toLocaleDateString();
}
