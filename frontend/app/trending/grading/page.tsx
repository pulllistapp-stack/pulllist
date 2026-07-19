"use client";

/**
 * Grading Premium — ranks catalog cards by (graded-tier median / raw
 * market) multiplier. Answers the "is this card worth grading?"
 * question at a glance: a card sitting at ×50 on PSA 10 clears 50×
 * its raw price when the slab is submitted and graded 10.
 *
 * Filters:
 *   - tier: PSA 10 (default) / CGC 10 / BGS 10 / BGS 10 BL / TAG 10
 *   - language: all / EN / JP  (KR / CN when the JP session lands them)
 *   - min samples floor (defaults to 2 — single-listing medians are
 *     too noisy for a grading-decision surface)
 *
 * Data source: /api/v1/trending/grading-premium (SQL DISTINCT ON
 * with a source-priority ladder: ebay_sold beats ebay_asking beats
 * legacy ebay).
 */

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Award, Diamond, Loader2 } from "lucide-react";

import { API_BASE } from "@/lib/api";

type PremiumItem = {
  card_id: string;
  name: string;
  number: string | null;
  rarity: string | null;
  image_small: string | null;
  language: string;
  set_id: string | null;
  set_name: string | null;
  raw_price_usd: number;
  tier_price_usd: number;
  sales_count: number | null;
  source: string;
  updated_at: string | null;
  multiplier: number;
};

type PremiumResponse = {
  tier: string;
  language: string;
  count: number;
  items: PremiumItem[];
};

type TierOption = {
  key: string;
  label: string;
  color: string; // text color for the multiplier chip
};

const TIERS: TierOption[] = [
  { key: "psa10", label: "PSA 10", color: "text-emerald-400" },
  { key: "cgc10", label: "CGC 10", color: "text-teal-400" },
  { key: "bgs10", label: "BGS 10", color: "text-indigo-400" },
  { key: "bgs10bl", label: "BGS 10 BL", color: "text-slate-300" },
  { key: "tag10", label: "TAG 10", color: "text-rose-400" },
];

const LANGS: { key: string; label: string; flag: string }[] = [
  { key: "all", label: "All", flag: "🌐" },
  { key: "en", label: "EN", flag: "🇺🇸" },
  { key: "ja", label: "JP", flag: "🇯🇵" },
];

function fmt(v: number): string {
  if (v >= 1000) {
    return `$${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
  }
  return `$${v.toFixed(2)}`;
}

function fmtMultiplier(m: number): string {
  if (m >= 100) return `×${m.toFixed(0)}`;
  if (m >= 10) return `×${m.toFixed(1)}`;
  return `×${m.toFixed(2)}`;
}

export default function GradingPremiumPage() {
  const [tier, setTier] = useState("psa10");
  const [language, setLanguage] = useState("all");
  const [soldOnly, setSoldOnly] = useState(true);
  const [data, setData] = useState<PremiumResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const url =
      `${API_BASE}/trending/grading-premium` +
      `?tier=${tier}&language=${language}&limit=150&min_samples=2&min_multiplier=2` +
      `&sold_only=${soldOnly ? "true" : "false"}`;
    fetch(url, { cache: "no-store" })
      .then(async (r) => (r.ok ? ((await r.json()) as PremiumResponse) : null))
      .then((json) => {
        if (!cancelled) setData(json);
      })
      .catch(() => {
        if (!cancelled) setData(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tier, language, soldOnly]);

  const activeTier = useMemo(
    () => TIERS.find((t) => t.key === tier) ?? TIERS[0],
    [tier],
  );

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 pb-24">
      <header className="mb-6">
        <div className="flex items-center gap-2 mb-2">
          <Diamond className="h-5 w-5 text-accent-yellow" />
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-text-primary">
            Grading Premium
          </h1>
        </div>
        <p className="text-sm text-text-secondary max-w-2xl leading-relaxed">
          Cards ranked by how many times their raw market price a{" "}
          {activeTier.label} slab clears at. A ×50 card sells for 50× its
          ungraded market once graded — worth the fee + submission wait if
          you already own a clean copy.
        </p>
      </header>

      {/* Tier chips */}
      <div className="flex flex-wrap gap-2 mb-3">
        {TIERS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTier(t.key)}
            className={
              "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-mono uppercase tracking-wider font-semibold transition-colors " +
              (tier === t.key
                ? "border-accent-yellow bg-accent-yellow/10 text-text-primary"
                : "border-border bg-bg-surface text-text-secondary hover:text-text-primary")
            }
          >
            <Award className={"h-3 w-3 " + t.color} />
            {t.label}
          </button>
        ))}
      </div>

      {/* Language chips + sold-only toggle */}
      <div className="flex flex-wrap items-center gap-2 mb-6">
        {LANGS.map((l) => (
          <button
            key={l.key}
            type="button"
            onClick={() => setLanguage(l.key)}
            className={
              "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-mono uppercase tracking-wider font-semibold transition-colors " +
              (language === l.key
                ? "border-accent-yellow bg-accent-yellow/10 text-text-primary"
                : "border-border bg-bg-surface text-text-secondary hover:text-text-primary")
            }
          >
            <span>{l.flag}</span>
            {l.label}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <label className="flex items-center gap-1.5 cursor-pointer text-[11px] font-mono uppercase tracking-wider text-text-secondary hover:text-text-primary">
            <input
              type="checkbox"
              checked={soldOnly}
              onChange={(e) => setSoldOnly(e.target.checked)}
              className="h-3.5 w-3.5 accent-accent-yellow"
            />
            Sold-only
          </label>
        </div>
      </div>

      {/* List */}
      {loading ? (
        <div className="flex items-center justify-center py-16 text-text-tertiary">
          <Loader2 className="h-5 w-5 animate-spin" />
        </div>
      ) : data == null || data.items.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border/60 bg-bg-surface/40 p-8 text-center text-text-tertiary">
          No cards clear the multiplier floor yet for this tier + language.
          Try another tier or wait for the next scrape sweep.
        </div>
      ) : (
        <ol className="space-y-2">
          {data.items.map((item, idx) => (
            <li key={item.card_id}>
              <Link
                href={`/cards/${item.card_id}`}
                className="flex items-center gap-3 rounded-2xl border border-border bg-bg-surface p-3 transition-colors hover:border-accent-yellow/40 hover:bg-bg-surface/80"
              >
                <div className="w-8 shrink-0 text-center font-mono text-xs text-text-tertiary">
                  {idx + 1}
                </div>
                <div className="relative h-16 w-12 shrink-0 overflow-hidden rounded bg-bg">
                  {item.image_small ? (
                    <Image
                      src={item.image_small}
                      alt={item.name}
                      fill
                      sizes="48px"
                      className="object-contain"
                      unoptimized
                    />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center text-[10px] text-text-tertiary">
                      —
                    </div>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-text-tertiary mb-0.5">
                    <span>{item.language.toUpperCase()}</span>
                    <span>·</span>
                    <span className="truncate">
                      {item.number ?? "—"}
                      {item.set_name ? ` · ${item.set_name}` : ""}
                    </span>
                  </div>
                  <div className="font-semibold text-text-primary text-sm truncate">
                    {item.name}
                  </div>
                  <div className="mt-1 text-[11px] text-text-secondary">
                    <span className="text-text-tertiary">raw </span>
                    <span className="font-mono">{fmt(item.raw_price_usd)}</span>
                    <span className="mx-1.5 text-text-tertiary">→</span>
                    <span
                      className={"font-mono font-semibold " + activeTier.color}
                    >
                      {activeTier.label} {fmt(item.tier_price_usd)}
                    </span>
                    {item.sales_count != null && (
                      <span className="ml-2 text-text-tertiary">
                        · {item.sales_count} sale
                        {item.sales_count === 1 ? "" : "s"}
                      </span>
                    )}
                  </div>
                </div>
                <div
                  className={
                    "ml-2 shrink-0 rounded-lg px-2.5 py-1 text-lg font-extrabold font-mono tracking-tight " +
                    activeTier.color +
                    " bg-current/10"
                  }
                >
                  {fmtMultiplier(item.multiplier)}
                </div>
              </Link>
            </li>
          ))}
        </ol>
      )}

      <p className="mt-6 text-[10px] text-text-tertiary/70 leading-relaxed">
        Multiplier = latest {activeTier.label} median ÷ current raw market.
        Both prices come from the same source ladder as the card-detail
        Graded Prices grid (ebay_sold beats ebay_asking beats legacy
        eBay). Rows with fewer than 2 sold samples are excluded so the
        ranking isn't dominated by a single fluke listing. Grading fees +
        shipping + PopReport risk aren't priced in — treat this as an
        upper-bound estimate, not investment advice.
      </p>
    </main>
  );
}
