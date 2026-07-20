"use client";

/**
 * Shared graded-tier preview panel used by CardAddModal and
 * CollectionItemEditModal. Renders the live market price for the
 * (service, value) the user is selecting so they can see the actual
 * slab value before saving, and nudges toward the card page's Refresh
 * button when the tier hasn't been scraped yet.
 *
 * Fetches /cards/{id}/graded-prices lazily the first time it renders
 * with `isGraded=true`, then re-uses the payload for every service /
 * grade change in the modal.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { Award, ExternalLink, Loader2 } from "lucide-react";

import { API_BASE } from "@/lib/api";
import {
  fmtGradedMoney,
  serviceGradeToKey,
  type GradedPricesResponse,
} from "@/lib/gradedTier";

type Props = {
  cardId: string;
  isGraded: boolean;
  service: string;
  value: string;
  /** Optional — parent may want to react to tier price (e.g. ROI hint).
   *  Called with null when tier is unknown/untracked or data is missing. */
  onTierPrice?: (price: number | null) => void;
};

export function GradedTierPreview({
  cardId,
  isGraded,
  service,
  value,
  onTierPrice,
}: Props) {
  const [data, setData] = useState<GradedPricesResponse | null>(null);
  const [loading, setLoading] = useState(false);

  // Deps intentionally scoped to (isGraded, cardId) — including
  // `data` or `loading` in the dep array is a self-inflicted wound:
  // setLoading(true) inside the effect triggers a re-render, the
  // cleanup fires with cancelled=true, and the in-flight fetch's
  // resolvers all short-circuit → the panel stays stuck on "Loading"
  // forever. React's eslint-plugin-react-hooks does warn about this
  // pattern but only when it can prove the missing dep is read
  // unconditionally; here the guards hide it.
  useEffect(() => {
    if (!isGraded) return;
    let cancelled = false;
    setLoading(true);
    fetch(`${API_BASE}/cards/${cardId}/graded-prices`, { cache: "no-store" })
      .then(async (r) => (r.ok ? ((await r.json()) as GradedPricesResponse) : {}))
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
  }, [isGraded, cardId]);

  const tierKey = isGraded ? serviceGradeToKey(service, value) : null;
  const tier = tierKey && data ? data[tierKey] ?? null : null;
  const price = tier?.latest_price_usd ?? null;

  useEffect(() => {
    if (!onTierPrice) return;
    onTierPrice(isGraded && tierKey ? price : null);
  }, [isGraded, tierKey, price, onTierPrice]);

  if (!isGraded) return null;

  if (loading) {
    return (
      <div className="mt-3 rounded-card border border-border bg-bg-elevated px-3 py-2 text-xs font-mono text-text-tertiary flex items-center gap-2">
        <Loader2 className="h-3 w-3 animate-spin" />
        Loading graded market…
      </div>
    );
  }

  if (tierKey === null) {
    return (
      <div className="mt-3 rounded-card border border-border bg-bg-elevated px-3 py-2 text-xs font-mono text-text-tertiary">
        No live graded market tracked for {service} {value}
        {" · "}
        <span className="text-text-secondary">value falls back to raw</span>
      </div>
    );
  }

  if (price != null) {
    return (
      <div className="mt-3 rounded-card border border-accent-yellow/40 bg-accent-yellow/5 px-3 py-2 text-xs font-mono flex items-center justify-between">
        <span className="inline-flex items-center gap-1.5 text-text-secondary">
          <Award className="h-3.5 w-3.5 text-accent-yellow" />
          {service} {value} market
        </span>
        <span className="font-bold text-accent-yellow">
          {fmtGradedMoney(price)}
        </span>
      </div>
    );
  }

  return (
    <div className="mt-3 rounded-card border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-xs">
      <p className="font-mono text-amber-400 mb-1.5">
        No {service} {value} data yet — value defaults to raw
      </p>
      <Link
        href={`/cards/${cardId}`}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-1 text-[11px] font-mono text-accent-yellow hover:brightness-125 transition-all"
      >
        Open card page & hit Refresh
        <ExternalLink className="h-3 w-3" />
      </Link>
    </div>
  );
}
