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
import { Award, Loader2 } from "lucide-react";

import { API_BASE } from "@/lib/api";

type GradedTier = "psa10" | "psa9" | "cgc10" | "cgc9";

type GradedPoint = {
  latest_price_usd: number | null;
  variant: string | null;
  source: string | null;
  updated_at: string | null; // ISO date
};

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

  return (
    <section className="mt-8">
      <div className="flex items-baseline justify-between mb-3">
        <h3 className="text-lg font-bold tracking-tight text-text-primary">
          Graded Prices
        </h3>
        <span className="text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
          Beta · sold-listing medians
        </span>
      </div>
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
                <>
                  <div className="text-xl font-extrabold text-accent-green">
                    {fmtMoney(row!.latest_price_usd)}
                  </div>
                  <div className="mt-1 text-[10px] text-text-tertiary leading-tight">
                    {row!.variant ?? "—"}
                    {row!.source ? ` / ${row!.source}` : ""}
                    <br />
                    <span className="opacity-70">
                      updated {fmtRelative(row!.updated_at)}
                    </span>
                  </div>
                </>
              ) : (
                <>
                  <div className="text-xl font-bold text-text-tertiary/60">
                    —
                  </div>
                  <div className="mt-1 text-[10px] text-text-tertiary/70 leading-tight">
                    No sold listings indexed yet.
                  </div>
                </>
              )}
            </div>
          );
        })}
      </div>
      <p className="mt-3 text-[10px] text-text-tertiary/60 leading-relaxed">
        Median sold price across the last 90 days of graded eBay listings
        matching the exact card + grade tier. Ungraded / raw prices live in
        the chart above.
      </p>
    </section>
  );
}
