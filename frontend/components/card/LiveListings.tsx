"use client";

import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import { Loader2, RefreshCw, ShieldCheck, Truck } from "lucide-react";

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

  // The cheapest *trustworthy* listing under the current filter. We
  // skip suspicious ones so the Cheapest badge doesn't land on a scam
  // decoy (e.g. 0-feedback seller at 9% of market price).
  const cheapestKey = filtered.find((l) => !l.suspicious)?.url;

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
        <div className="-mx-1 flex gap-3 overflow-x-auto px-1 pb-3 snap-x scroll-pl-1">
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
  const suspicious = listing.suspicious === true;

  const outboundUrl =
    listing.source === "eBay"
      ? wrapEbayUrl(listing.url)
      : listing.source === "TCGplayer"
        ? wrapTcgPlayerUrl(listing.url)
        : listing.url;

  // Stack badges in the upper-left so they never overlap. Cheapest sits
  // at the top when present, then Graded; Suspicious *replaces* both —
  // a flagged listing isn't the cheapest of anything we trust.
  const topBadges: Array<"cheapest" | "graded" | "suspicious"> = [];
  if (suspicious) topBadges.push("suspicious");
  else if (isCheapest) topBadges.push("cheapest");
  if (graded) topBadges.push("graded");

  // Compact carousel card — eBay-style horizontal strip. The whole tile is the
  // outbound link; no separate Buy button needed.
  return (
    <a
      href={outboundUrl}
      target="_blank"
      rel="noopener noreferrer sponsored"
      title={
        suspicious
          ? `⚠ Suspicious: new seller asking far below market. ${listing.title}`
          : listing.title
      }
      className={cn(
        "group relative flex w-[150px] shrink-0 snap-start flex-col gap-1.5 rounded-2xl border bg-bg p-2 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md",
        suspicious
          ? "border-accent-red/40 opacity-75 hover:opacity-100 hover:border-accent-red/70"
          : isCheapest
            ? "border-accent-yellow/60 hover:border-accent-yellow shadow-sm shadow-accent-yellow/10"
            : "border-border hover:border-accent-yellow/40",
      )}
    >
      {/* Thumbnail */}
      <div className="relative aspect-square w-full overflow-hidden rounded-lg bg-bg-surface">
        {listing.image_url ? (
          <Image
            src={listing.image_url}
            alt=""
            fill
            className={cn(
              "object-contain transition-transform duration-200 group-hover:scale-[1.04]",
              suspicious && "grayscale-[40%] group-hover:grayscale-0",
            )}
            sizes="150px"
            unoptimized
          />
        ) : (
          <div className="flex h-full items-center justify-center text-[10px] text-text-tertiary">
            no img
          </div>
        )}

        {/* Badges sit *inside* the thumbnail so the horizontal-scroll parent
            (overflow-x: auto, which also clips overflow-y) can't shave the
            top off a -top badge. Stack downward — index 0 at top-1. */}
        {topBadges.map((kind, i) => {
          const top = i === 0 ? "top-1" : i === 1 ? "top-7" : "top-[3.25rem]";
          if (kind === "suspicious") {
            return (
              <span
                key={kind}
                className={cn(
                  "absolute left-1 inline-flex items-center gap-0.5 rounded-full bg-accent-red text-white px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider shadow-sm",
                  top,
                )}
              >
                ⚠ Risky
              </span>
            );
          }
          if (kind === "cheapest") {
            return (
              <span
                key={kind}
                className={cn(
                  "absolute left-1 inline-flex items-center rounded-full bg-accent-yellow text-bg px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider shadow-sm",
                  top,
                )}
              >
                Cheapest
              </span>
            );
          }
          return (
            <span
              key={kind}
              className={cn(
                "absolute left-1 inline-flex items-center rounded-full bg-violet-500/95 text-white px-1.5 py-0.5 text-[9px] font-semibold uppercase",
                top,
              )}
            >
              Graded
            </span>
          );
        })}

        {freeShip && (
          <span className="absolute bottom-1 right-1 inline-flex items-center gap-0.5 rounded-full bg-accent-green/95 text-white px-1.5 py-0.5 text-[9px] font-semibold uppercase">
            <Truck className="h-2.5 w-2.5" />
            Free
          </span>
        )}
      </div>

      {/* Price */}
      <div>
        <p className="font-mono text-base font-extrabold text-text-primary leading-none">
          {fmtUSD(listing.total_usd)}
        </p>
        {!freeShip && (
          <p className="mt-0.5 text-[9px] font-mono text-text-tertiary leading-none">
            +{fmtUSD(listing.shipping_usd)} ship
          </p>
        )}
      </div>

      {/* Title */}
      <p className="line-clamp-2 text-[11px] text-text-secondary leading-snug">
        {listing.title}
      </p>

      {/* Bottom: condition (when ungraded) + seller trust */}
      <div className="mt-auto flex items-center justify-between gap-1 text-[10px] text-text-tertiary">
        {!graded && (
          <span className="font-mono uppercase truncate">{listing.condition}</span>
        )}
        <SellerTrust pct={feedback} />
      </div>
    </a>
  );
}

function ListingsSkeleton() {
  return (
    <div className="-mx-1 flex gap-3 overflow-x-auto px-1 pb-3">
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <div
          key={i}
          className="flex w-[150px] shrink-0 flex-col gap-1.5 rounded-2xl border border-border bg-bg p-2 animate-pulse"
        >
          <div className="aspect-square w-full rounded-lg bg-bg-surface" />
          <div className="h-4 w-16 rounded bg-bg-surface" />
          <div className="h-3 w-3/4 rounded bg-bg-surface" />
          <div className="h-3 w-1/2 rounded bg-bg-surface" />
        </div>
      ))}
    </div>
  );
}
