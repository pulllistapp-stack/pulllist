"use client";

import { useCallback, useEffect, useState } from "react";
import { Activity, Globe, Loader2, ShieldAlert } from "lucide-react";

import { AdminGuard } from "@/components/admin/AdminGuard";
import { AdminNav } from "@/components/admin/AdminNav";
import {
  getVisitsByUser,
  getVisitsSummary,
  type VisitsByUserItem,
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
  const [byUser, setByUser] = useState<VisitsByUserItem[]>([]);
  const [windowDays, setWindowDays] = useState<number>(1);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, b] = await Promise.all([
        getVisitsSummary(),
        getVisitsByUser(windowDays),
      ]);
      setSummary(s);
      setByUser(b.items);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [windowDays]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <main className="mx-auto max-w-6xl px-4 sm:px-6 py-8">
      <AdminNav />

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
                Per-user visits
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
            {byUser.length === 0 ? (
              <p className="text-sm text-text-tertiary italic">
                No signed-in visits in this window.
              </p>
            ) : (
              <div className="rounded-card border border-border bg-bg-surface overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border bg-bg/40 text-[11px] font-mono uppercase tracking-wider text-text-tertiary">
                      <th className="text-left px-3 py-2">User</th>
                      <th className="text-right px-3 py-2">Views</th>
                      <th className="text-right px-3 py-2 hidden sm:table-cell">
                        Last seen
                      </th>
                      <th className="text-right px-3 py-2">Country</th>
                    </tr>
                  </thead>
                  <tbody>
                    {byUser.map((u) => (
                      <tr
                        key={u.user_id}
                        className="border-b border-border last:border-0"
                      >
                        <td className="px-3 py-2">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-text-primary truncate max-w-[200px]">
                              {u.name ?? u.email ?? u.user_id.slice(0, 8)}
                            </span>
                            {u.is_admin && (
                              <span className="rounded-full bg-accent-yellow/15 text-accent-yellow text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5">
                                Admin
                              </span>
                            )}
                          </div>
                          {u.email && u.name && (
                            <span className="block text-[11px] font-mono text-text-tertiary truncate max-w-[260px]">
                              {u.email}
                            </span>
                          )}
                        </td>
                        <td className="text-right px-3 py-2 font-mono font-bold text-text-primary">
                          {u.views}
                        </td>
                        <td className="text-right px-3 py-2 font-mono text-[11px] text-text-tertiary hidden sm:table-cell">
                          {u.last_seen ? formatRelative(new Date(u.last_seen)) : "—"}
                        </td>
                        <td
                          className={cn(
                            "text-right px-3 py-2 font-mono text-xs",
                            isSuspicious(u.last_country)
                              ? "text-accent-red font-bold"
                              : "text-text-secondary",
                          )}
                          title={
                            isSuspicious(u.last_country)
                              ? "Flagged country — review activity"
                              : undefined
                          }
                        >
                          {isSuspicious(u.last_country) && (
                            <ShieldAlert className="inline h-3 w-3 mr-1" />
                          )}
                          {countryFlag(u.last_country)} {u.last_country ?? "??"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
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
  return (
    <div className="flex items-end gap-1.5 h-24">
      {data.map((d) => {
        const ratio = d.views / maxViews;
        return (
          <div
            key={d.date}
            className="flex-1 flex flex-col items-center gap-1"
            title={`${d.date}: ${d.views} views, ${d.uniques} unique`}
          >
            <div className="flex-1 flex items-end w-full">
              <div
                className="w-full rounded-t-md bg-accent-yellow/60 hover:bg-accent-yellow transition-colors"
                style={{ height: `${ratio * 100}%` }}
              />
            </div>
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

function formatRelative(d: Date): string {
  const diffMs = Date.now() - d.getTime();
  const min = Math.floor(diffMs / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day}d ago`;
  return d.toLocaleDateString();
}
