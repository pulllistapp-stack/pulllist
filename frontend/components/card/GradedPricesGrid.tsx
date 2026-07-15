"use client";

/**
 * Graded Prices grid — sits below the CardPriceChart. Four cards, one
 * per canonical grade tier (PSA 10 / PSA 9 / CGC 10 / CGC 9). Fed by
 * `services.grade_classifier` output on the backend once eBay
 * classified snapshots start landing.
 *
 * ROADMAP #9 (Multi-Grade prices) — this is the frontend half of the
 * "prep" phase; backend data pipeline is separate (`grade` column on
 * `card_price_snapshots` already exists, eBay ingest will bucket
 * listings via the regex classifier). Until real graded rows land,
 * every tile falls into the "no data yet" state gracefully.
 */

import { useEffect, useState } from "react";
import { Award, Loader2, RefreshCw, CheckCircle2 } from "lucide-react";

import { API_BASE } from "@/lib/api";
import { authFetch } from "@/lib/auth";
import { useAuth } from "@/components/AuthProvider";

type GradedTier =
  | "psa10"
  | "psa9"
  | "cgc10"
  | "cgc9"
  | "bgs10"
  | "bgs9.5"
  | "bgs9"
  | "tag10"
  | "tag9.5"
  | "tag9";

type GradedPoint = {
  latest_price_usd: number | null;
  variant: string | null;
  source: string | null;
  updated_at: string | null; // ISO date
  sales_count?: number | null;
};

// Map raw source key → human label + tile accent class. Sold data is
// the ground truth; asking (scraped active listings) is a fallback
// for thin tiers, so we surface which one the tile is showing.
function sourceMeta(source: string | null | undefined): {
  label: string;
  tone: "sold" | "asking" | "unknown";
} {
  if (source === "ebay_sold") return { label: "Sold", tone: "sold" };
  if (source === "ebay_asking") return { label: "Asking", tone: "asking" };
  if (source === "ebay") return { label: "Asking", tone: "asking" }; // legacy Browse-API asking
  return { label: source ?? "—", tone: "unknown" };
}

type GradedResponse = Partial<Record<GradedTier, GradedPoint>>;

const TIER_META: {
  key: GradedTier;
  label: string;
  color: string; // per-tier accent
}[] = [
  { key: "psa10", label: "PSA 10", color: "text-emerald-400" },
  { key: "psa9", label: "PSA 9", color: "text-emerald-300" },
  { key: "cgc10", label: "CGC 10", color: "text-teal-400" },
  { key: "cgc9", label: "CGC 9", color: "text-teal-300" },
  { key: "bgs10", label: "BGS 10", color: "text-indigo-400" },
  { key: "bgs9.5", label: "BGS 9.5", color: "text-indigo-300" },
  { key: "bgs9", label: "BGS 9", color: "text-indigo-200" },
  // TAG family — rose accent so it reads as its own grader (PSA green,
  // CGC teal, BGS indigo, TAG rose).
  { key: "tag10", label: "TAG 10", color: "text-rose-400" },
  { key: "tag9.5", label: "TAG 9.5", color: "text-rose-300" },
  { key: "tag9", label: "TAG 9", color: "text-rose-200" },
];

function fmtMoney(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  if (v >= 1000) return `$${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
  return `$${v.toFixed(2)}`;
}

function fmtRelative(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function GradedPricesGrid({ cardId }: { cardId: string }) {
  const [data, setData] = useState<GradedResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState<
    "idle" | "queuing" | "queued" | "error" | "cooldown"
  >("idle");
  const [refreshMsg, setRefreshMsg] = useState<string>("");
  const { user } = useAuth();

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    // Endpoint is planned but not shipped yet; a 404 here should render
    // the "no data yet" grid instead of an error.
    fetch(`${API_BASE}/cards/${cardId}/graded-prices`, { cache: "no-store" })
      .then(async (r) => {
        if (!r.ok) return null;
        return (await r.json()) as GradedResponse;
      })
      .then((json) => {
        if (!cancelled) setData(json ?? {});
      })
      .catch(() => {
        if (!cancelled) setData({});
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [cardId]);

  async function onRefresh() {
    setRefreshing("queuing");
    setRefreshMsg("");
    try {
      const r = await authFetch<{ status: string; message: string }>(
        `/cards/${cardId}/refresh-graded-prices`,
        { method: "POST" },
      );
      setRefreshing("queued");
      setRefreshMsg(r?.message ?? "Refresh queued — check back in 2-3 min");
    } catch (e: unknown) {
      const err = e as { status?: number; message?: string };
      if (err.status === 429) {
        setRefreshing("cooldown");
        setRefreshMsg("Already refreshed recently — try again later");
      } else if (err.status === 401) {
        setRefreshing("error");
        setRefreshMsg("Sign in to refresh graded prices");
      } else {
        setRefreshing("error");
        setRefreshMsg(err.message ?? "Refresh failed");
      }
    }
  }

  return (
    <section className="mt-8">
      <div className="flex items-baseline justify-between mb-3 gap-3 flex-wrap">
        <h3 className="text-lg font-bold tracking-tight text-text-primary">
          Graded Prices
        </h3>
        <div className="flex items-center gap-2">
          {user &&
            (() => {
              // When most tiles are empty, promote the refresh button
              // to a solid accent so users notice the escape hatch.
              // Once data lands, drop back to the subtle outline chip.
              const filledCount = data
                ? TIER_META.filter(
                    (t) =>
                      data[t.key] && data[t.key]!.latest_price_usd != null,
                  ).length
                : 0;
              const promoted = filledCount <= 2 && !loading;
              const idleClass = promoted
                ? "border-accent-green/60 bg-accent-green/10 hover:bg-accent-green/20 text-accent-green"
                : "border-border bg-bg-surface hover:bg-bg-elevated text-text-secondary";
              return (
                <button
                  type="button"
                  onClick={onRefresh}
                  disabled={
                    refreshing === "queuing" || refreshing === "queued"
                  }
                  className={
                    "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 " +
                    "text-[10px] font-mono uppercase tracking-wider " +
                    "border disabled:opacity-60 disabled:cursor-not-allowed " +
                    "transition-colors " +
                    idleClass
                  }
                  title={
                    "Scrape fresh sold + active-listing data for this card " +
                    "from eBay. Runs in the background (~2-3 min) — reload " +
                    "the page after to see updated tiles."
                  }
                >
                  {refreshing === "queuing" ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : refreshing === "queued" ? (
                    <CheckCircle2 className="h-3 w-3 text-accent-green" />
                  ) : (
                    <RefreshCw className="h-3 w-3" />
                  )}
                  {refreshing === "queuing"
                    ? "Queuing..."
                    : refreshing === "queued"
                    ? "Queued · Reload in ~3 min"
                    : promoted
                    ? "Refresh — get live data"
                    : "Refresh"}
                </button>
              );
            })()}
          <span className="text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
            Beta · sold-listing medians
          </span>
        </div>
      </div>
      {refreshMsg && (
        <div
          className={
            "mb-3 text-[11px] px-2.5 py-1.5 rounded-lg border " +
            (refreshing === "queued"
              ? "border-accent-green/40 bg-accent-green/10 text-accent-green"
              : refreshing === "cooldown"
              ? "border-amber-500/40 bg-amber-500/10 text-amber-400"
              : "border-red-500/40 bg-red-500/10 text-red-400")
          }
        >
          {refreshMsg}
        </div>
      )}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {TIER_META.map((tier) => {
          const row = data?.[tier.key];
          const hasData = !!row && row.latest_price_usd != null;
          return (
            <div
              key={tier.key}
              className={
                "rounded-2xl border p-3 " +
                (hasData
                  ? "border-border bg-bg-surface"
                  : "border-dashed border-border/60 bg-bg-surface/40")
              }
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-1.5">
                  <Award className={"h-3.5 w-3.5 " + tier.color} />
                  <span className="text-[11px] font-mono uppercase tracking-wider text-text-secondary font-bold">
                    {tier.label}
                  </span>
                </div>
                {loading && (
                  <Loader2 className="h-3 w-3 animate-spin text-text-tertiary" />
                )}
              </div>
              {hasData ? (
                (() => {
                  const meta = sourceMeta(row!.source);
                  const priceClass =
                    meta.tone === "sold"
                      ? "text-accent-green"
                      : "text-amber-400"; // Asking = amber so users see the softer signal
                  const badgeClass =
                    meta.tone === "sold"
                      ? "bg-accent-green/15 text-accent-green"
                      : "bg-amber-500/15 text-amber-400";
                  return (
                    <>
                      <div className={"text-xl font-extrabold " + priceClass}>
                        {fmtMoney(row!.latest_price_usd)}
                      </div>
                      <div className="mt-1 flex items-center gap-1.5 text-[10px] leading-tight">
                        <span
                          className={
                            "px-1.5 py-[1px] rounded font-mono font-bold uppercase tracking-wider " +
                            badgeClass
                          }
                        >
                          {meta.label}
                        </span>
                        {row!.sales_count != null && (
                          <span className="text-text-tertiary">
                            {row!.sales_count}{" "}
                            {meta.tone === "sold"
                              ? row!.sales_count === 1
                                ? "sale"
                                : "sales"
                              : row!.sales_count === 1
                              ? "listing"
                              : "listings"}
                          </span>
                        )}
                      </div>
                      <div className="mt-1 text-[10px] text-text-tertiary/70 leading-tight">
                        updated {fmtRelative(row!.updated_at)}
                      </div>
                    </>
                  );
                })()
              ) : (
                <>
                  <div className="text-xl font-bold text-text-tertiary/60">
                    ·
                  </div>
                  <div className="mt-1 text-[10px] text-text-tertiary/70 leading-tight">
                    {user
                      ? "Not tracked yet — hit Refresh above to check now."
                      : "Not tracked yet — sign in and hit Refresh to check."}
                  </div>
                </>
              )}
            </div>
          );
        })}
      </div>
      <p className="mt-3 text-[10px] text-text-tertiary/60 leading-relaxed">
        Median across the last 90 days of graded eBay listings matching the
        exact card + tier.{" "}
        <span className="text-accent-green">Sold</span> tiles come from
        actually-cleared sales; <span className="text-amber-400">Asking</span>{" "}
        tiles fall back to active-listing medians when sold data is thin
        (common for vintage CGC / TAG). Missing a tier?{" "}
        {user
          ? "Hit Refresh above to scrape it right now — takes 2-3 minutes."
          : "Sign in to trigger a live refresh for any card."}{" "}
        Ungraded / raw prices live in the chart above.
      </p>
    </section>
  );
}
