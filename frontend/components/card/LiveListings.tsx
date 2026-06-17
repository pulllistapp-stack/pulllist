"use client";

import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  ExternalLink,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Truck,
} from "lucide-react";

import { getLiveListings, type LiveListing } from "@/lib/api";
import { wrapEbayUrl, wrapTcgPlayerUrl } from "@/lib/affiliate";
import { cn } from "@/lib/utils";

function fmtUSD(v: number) {
  return `$${v.toFixed(2)}`;
}

const GRADED_RE = /\b(psa|bgs|cgc|sgc)\s*\d/i;

function isGraded(title: string): boolean {
  return GRADED_RE.test(title);
}

function parseFeedback(v: number | string | null | undefined): number | null {
  if (v == null) return null;
  const n = typeof v === "number" ? v : parseFloat(v);
  return Number.isFinite(n) ? n : null;
}

type Filter = "all" | "raw" | "graded" | "free_ship";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "raw", label: "Raw" },
  { key: "graded", label: "Graded" },
  { key: "free_ship", label: "Free ship" },
];

function applyFilter(listings: LiveListing[], filter: Filter): LiveListing[] {
  switch (filter) {
    case "raw":
      return listings.filter((l) => !isGraded(l.title));
    case "graded":
      return listings.filter((l) => isGraded(l.title));
    case "free_ship":
      return listings.filter((l) => l.shipping_usd === 0);
    default:
      return listings;
  }
}

function SellerTrust({ pct }: { pct: number | null }) {
  if (pct == null) return null;
  if (pct >= 99) {
    return (
      <span
        className="inline-flex items-center gap-0.5 text-[10px] font-mono text-accent-green"
        title={`${pct}% positive feedback — trusted seller`}
      >
        <ShieldCheck className="h-3 w-3" />
        {pct}%
      </span>
    );
  }
  if (pct >= 95) {
    return (
      <span
        className="inline-flex items-center gap-0.5 text-[10px] font-mono text-text-tertiary"
        title={`${pct}% positive feedback`}
      >
        {pct}%
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center gap-0.5 text-[10px] font-mono text-accent-red"
      title={`${pct}% positive feedback — caution`}
    >
      {pct}%
    </span>
  );
}

export function LiveListings({ cardId }: { cardId: string }) {
  const [listings, setListings] = useState<LiveListing[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    getLiveListings(cardId, 12)
      .then((r) => {
        if (cancelled) return;
        setListings(r.listings);
        if (r.error) setErr(r.error);
      })
      .catch((e) => {
        if (!cancelled) setErr(String(e?.message ?? e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [cardId, refreshKey]);

  const filtered = useMemo(
    () => (listings ? applyFilter(listings, filter) : []),
    [listings, filter],
  );

  // The cheapest under the current filter — flagged with a Crown chip.
  const cheapestKey = filtered[0]?.url;

  // Per-filter counts for the chip badges.
  const counts = useMemo(() => {
    if (!listings) return { all: 0, raw: 0, graded: 0, free_ship: 0 };
    return {
      all: listings.length,
      raw: listings.filter((l) => !isGraded(l.title)).length,
      graded: listings.filter((l) => isGraded(l.title)).length,
      free_ship: listings.filter((l) => l.shipping_usd === 0).length,
    };
  }, [listings]);

  return (
    <section>
      <div className="mb-4 flex items-baseline justify-between gap-3 flex-wrap">
        <h2 className="text-lg font-bold text-text-primary">
          Live listings
          {listings && (
            <span className="ml-2 text-sm font-normal text-text-tertiary">
              · {filtered.length}
              {filter !== "all" && listings.length !== filtered.length && (
                <span className="text-text-tertiary/60"> of {listings.length}</span>
              )}
            </span>
          )}
        </h2>
        <div className="flex items-center gap-2">
          {loading && (
            <span className="inline-flex items-center gap-1 text-xs text-text-tertiary">
              <Loader2 className="h-3 w-3 animate-spin" />
              Fetching eBay
            </span>
          )}
          <button
            onClick={() => setRefreshKey((k) => k + 1)}
            disabled={loading}
            title="Refetch from eBay"
            className="inline-flex items-center gap-1 rounded-full border border-border bg-bg-surface px-2.5 py-1 text-xs font-semibold text-text-secondary hover:border-teal-400/40 hover:text-text-primary transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <RefreshCw className={cn("h-3 w-3", loading && "animate-spin")} />
            Refresh
          </button>
        </div>
      </div>

      {/* Filter pills */}
      {listings && listings.length > 0 && (
        <div className="mb-4 inline-flex rounded-full border border-border bg-bg-surface p-1">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              disabled={counts[f.key] === 0 && f.key !== "all"}
              className={cn(
                "rounded-full px-3 py-1 text-xs font-semibold transition-colors",
                filter === f.key
                  ? "bg-bg-elevated text-text-primary shadow-sm"
                  : "text-text-secondary hover:text-text-primary",
                counts[f.key] === 0 &&
                  f.key !== "all" &&
                  "opacity-40 cursor-not-allowed",
              )}
            >
              {f.label}
              <span className="ml-1 text-[10px] text-text-tertiary font-mono">
                {counts[f.key]}
              </span>
            </button>
          ))}
        </div>
      )}

      {err && !listings?.length && (
        <div className="rounded-2xl border border-dashed border-border bg-bg-surface/50 p-6 text-center text-sm text-text-secondary">
          Couldn&apos;t fetch live listings right now.
        </div>
      )}

      {loading && !listings && <ListingsSkeleton />}

      {!loading && !err && listings && listings.length === 0 && (
        <div className="rounded-2xl border-2 border-dashed border-border bg-bg-surface/50 p-10 text-center">
          <p className="text-sm font-medium text-text-primary">
            No active eBay listings right now
          </p>
          <p className="mt-1 text-xs text-text-secondary">
            Either super-rare or just sold out — check back later.
          </p>
        </div>
      )}

      {!loading && listings && listings.length > 0 && filtered.length === 0 && (
        <div className="rounded-2xl border border-dashed border-border bg-bg-surface/50 p-8 text-center">
          <p className="text-sm text-text-secondary">
            No listings match this filter — try a different one.
          </p>
        </div>
      )}

      {filtered.length > 0 && (
        <div className="grid grid-cols-1 gap-2.5">
          {filtered.map((l) => (
            <ListingCard
              key={l.url}
              listing={l}
              isCheapest={l.url === cheapestKey}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function ListingCard({
  listing,
  isCheapest,
}: {
  listing: LiveListing;
  isCheapest: boolean;
}) {
  const feedback = parseFeedback(listing.seller_feedback_pct);
  const graded = isGraded(listing.title);
  const freeShip = listing.shipping_usd === 0;

  const outboundUrl =
    listing.source === "eBay"
      ? wrapEbayUrl(listing.url)
      : listing.source === "TCGplayer"
        ? wrapTcgPlayerUrl(listing.url)
        : listing.url;

  return (
    <a
      href={outboundUrl}
      target="_blank"
      rel="noopener noreferrer sponsored"
      className={cn(
        "group relative flex gap-3 rounded-2xl border bg-bg p-3 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md",
        isCheapest
          ? "border-accent-yellow/50 hover:border-accent-yellow shadow-sm shadow-accent-yellow/10"
          : "border-border hover:border-accent-yellow/40",
      )}
    >
      {/* Thumbnail */}
      <div className="relative h-20 w-20 sm:h-24 sm:w-24 shrink-0 overflow-hidden rounded-lg bg-bg-surface">
        {listing.image_url ? (
          <Image
            src={listing.image_url}
            alt=""
            fill
            className="object-contain"
            sizes="96px"
            unoptimized
          />
        ) : (
          <div className="flex h-full items-center justify-center text-[10px] text-text-tertiary">
            no img
          </div>
        )}
      </div>

      {/* Middle: title + chips + seller */}
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5 mb-1">
          {isCheapest && (
            <span className="inline-flex items-center rounded-full bg-accent-yellow/15 text-accent-yellow border border-accent-yellow/40 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider">
              Cheapest
            </span>
          )}
          {graded ? (
            <span className="inline-flex items-center rounded-full bg-violet-500/15 text-violet-600 dark:text-violet-300 border border-violet-500/30 px-2 py-0.5 text-[10px] font-semibold uppercase">
              Graded
            </span>
          ) : (
            <span className="inline-flex items-center rounded-full bg-bg-surface text-text-tertiary border border-border px-2 py-0.5 text-[10px] font-semibold uppercase">
              {listing.condition}
            </span>
          )}
          {freeShip && (
            <span className="inline-flex items-center gap-0.5 rounded-full bg-accent-green/15 text-accent-green border border-accent-green/30 px-2 py-0.5 text-[10px] font-semibold uppercase">
              <Truck className="h-2.5 w-2.5" />
              Free ship
            </span>
          )}
        </div>

        <p className="line-clamp-2 text-xs text-text-primary leading-snug">
          {listing.title}
        </p>

        <div className="mt-1.5 flex items-center gap-2 text-[11px] text-text-tertiary">
          <span className="truncate font-medium text-text-secondary max-w-[160px]">
            {listing.seller}
          </span>
          <SellerTrust pct={feedback} />
        </div>
      </div>

      {/* Right: price stack */}
      <div className="flex flex-col items-end justify-between shrink-0">
        <div className="text-right">
          <p className="font-mono text-lg sm:text-xl font-extrabold text-text-primary leading-none">
            {fmtUSD(listing.total_usd)}
          </p>
          {!freeShip && (
            <p className="mt-0.5 text-[10px] font-mono text-text-tertiary">
              {fmtUSD(listing.price_usd)} + {fmtUSD(listing.shipping_usd)} ship
            </p>
          )}
        </div>
        <span className="mt-2 inline-flex items-center gap-1 rounded-full bg-gray-900 dark:bg-zinc-100 text-white dark:text-gray-900 px-3 py-1 text-[11px] font-bold group-hover:brightness-110 transition">
          Buy
          <ExternalLink className="h-3 w-3" />
        </span>
      </div>
    </a>
  );
}

function ListingsSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-2.5">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="flex gap-3 rounded-2xl border border-border bg-bg p-3 animate-pulse"
        >
          <div className="h-20 w-20 sm:h-24 sm:w-24 shrink-0 rounded-lg bg-bg-surface" />
          <div className="flex-1 space-y-2">
            <div className="h-3 w-1/3 rounded bg-bg-surface" />
            <div className="h-3 w-3/4 rounded bg-bg-surface" />
            <div className="h-2 w-1/2 rounded bg-bg-surface" />
          </div>
          <div className="space-y-2 text-right">
            <div className="h-5 w-16 rounded bg-bg-surface" />
            <div className="h-6 w-12 rounded bg-bg-surface" />
          </div>
        </div>
      ))}
    </div>
  );
}
