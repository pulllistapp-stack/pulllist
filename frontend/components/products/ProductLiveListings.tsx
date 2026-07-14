"use client";

/**
 * Live eBay listings for a sealed product. Mirrors
 * `components/card/LiveListings` but scoped to the /products/[id]
 * page — sellers, prices, images, and EPN affiliate deep-links so
 * clicks route eBay revenue back to us.
 */

import { useEffect, useState } from "react";
import Image from "next/image";
import { ArrowUpRight, Loader2, RefreshCw } from "lucide-react";

import {
  getProductLiveListings,
  ProductLiveListing,
} from "@/lib/api";

// Reuse the site's EPN campaign id; falls back to a static campid if
// the env isn't wired. Matches the card LiveListings behaviour.
const EPN_CAMPID = process.env.NEXT_PUBLIC_EBAY_CAMPAIGN_ID ?? "5339157076";
const EPN_TOOLID = "10001";
const EPN_MKRID = "711-53200-19255-0";

function withAffiliate(url: string | null): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    u.searchParams.set("mkevt", "1");
    u.searchParams.set("mkcid", "1");
    u.searchParams.set("mkrid", EPN_MKRID);
    u.searchParams.set("campid", EPN_CAMPID);
    u.searchParams.set("toolid", EPN_TOOLID);
    return u.toString();
  } catch {
    return url;
  }
}

function fmtPrice(v: number): string {
  if (v >= 1000) return `$${Math.round(v).toLocaleString()}`;
  return `$${v.toFixed(2)}`;
}

export function ProductLiveListings({ productId }: { productId: string }) {
  const [listings, setListings] = useState<ProductLiveListing[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    getProductLiveListings(productId, 12)
      .then((res) => {
        if (res.error) setError(res.error);
        setListings(res.listings ?? []);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : String(e));
        setListings([]);
      })
      .finally(() => setLoading(false));
  };

  useEffect(load, [productId]);  // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section className="mt-8 rounded-card border border-border bg-bg-surface p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <div>
          <h2 className="text-lg font-bold tracking-tight">Live on eBay</h2>
          <div className="text-[11px] text-text-tertiary">
            Top active listings · updated on load
          </div>
        </div>
        <button
          type="button"
          onClick={load}
          disabled={loading}
          className="inline-flex items-center gap-1 rounded-full border border-border bg-bg px-3 py-1 text-xs text-text-secondary hover:text-text-primary disabled:opacity-50"
        >
          {loading ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <RefreshCw className="h-3 w-3" />
          )}
          Refresh
        </button>
      </div>

      {error && (
        <div className="mb-3 rounded-lg border border-accent-red/30 bg-accent-red/10 p-3 text-xs text-accent-red">
          eBay error: {error}
        </div>
      )}

      {loading && !listings ? (
        <div className="flex h-48 items-center justify-center text-text-tertiary">
          <Loader2 className="h-5 w-5 animate-spin" />
        </div>
      ) : listings && listings.length > 0 ? (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {listings.map((l, i) => (
            <a
              key={`${l.url ?? "no-url"}-${i}`}
              href={withAffiliate(l.url) ?? "#"}
              target="_blank"
              rel="noopener noreferrer sponsored"
              className="group flex items-start gap-3 rounded-lg border border-border bg-bg/40 p-2.5 transition-colors hover:border-accent-yellow/40"
            >
              {l.image_url ? (
                <div className="relative h-14 w-14 flex-shrink-0 overflow-hidden rounded bg-bg">
                  <Image
                    src={l.image_url}
                    alt=""
                    fill
                    className="object-cover"
                    sizes="56px"
                    unoptimized
                  />
                </div>
              ) : (
                <div className="h-14 w-14 flex-shrink-0 rounded bg-bg" />
              )}
              <div className="min-w-0 flex-1">
                <div className="line-clamp-2 text-xs font-semibold text-text-primary group-hover:text-accent-yellow">
                  {l.title}
                </div>
                <div className="mt-1 flex items-baseline gap-2 text-xs">
                  <span className="font-mono font-bold text-accent-green">
                    {fmtPrice(l.price_usd)}
                  </span>
                  {l.shipping_usd > 0 ? (
                    <span className="text-text-tertiary">
                      +{fmtPrice(l.shipping_usd)} ship
                    </span>
                  ) : (
                    <span className="text-text-tertiary">free ship</span>
                  )}
                </div>
                <div className="mt-1 flex items-center gap-2 text-[10px] text-text-tertiary">
                  {l.seller && <span className="truncate">{l.seller}</span>}
                  {l.condition && (
                    <>
                      <span>·</span>
                      <span>{l.condition}</span>
                    </>
                  )}
                  {l.location && (
                    <>
                      <span>·</span>
                      <span>{l.location}</span>
                    </>
                  )}
                </div>
              </div>
              <ArrowUpRight className="h-3.5 w-3.5 flex-shrink-0 text-text-tertiary group-hover:text-accent-yellow" />
            </a>
          ))}
        </div>
      ) : (
        <div className="flex h-32 flex-col items-center justify-center rounded-lg border border-dashed border-border/60 bg-bg/40 text-center text-sm text-text-tertiary">
          <div className="font-semibold text-text-secondary">
            No live listings right now
          </div>
          <div className="mt-1 text-xs">
            eBay didn&apos;t return any priced listings for this exact SKU.
          </div>
        </div>
      )}

      <p className="mt-3 text-[10px] leading-relaxed text-text-tertiary">
        eBay Partner Network affiliate links — clicking one may earn PullList
        a small commission at no extra cost to you.
      </p>
    </section>
  );
}
