"use client";

import { useEffect, useState } from "react";
import { ExternalLink, Loader2 } from "lucide-react";

import { getLiveListings, type LiveListing } from "@/lib/api";
import { cn } from "@/lib/utils";

function fmtUSD(v: number) {
  return `$${v.toFixed(2)}`;
}

function SourceBadge({ source }: { source: string }) {
  const cls =
    source === "TCGplayer"
      ? "bg-amber-100 text-amber-800 ring-amber-300 dark:bg-amber-400/15 dark:text-amber-300 dark:ring-amber-400/30"
      : "bg-teal-100 text-teal-800 ring-teal-300 dark:bg-teal-400/15 dark:text-teal-300 dark:ring-teal-400/30";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-bold uppercase ring-1",
        cls,
      )}
    >
      {source}
    </span>
  );
}

export function LiveListings({ cardId }: { cardId: string }) {
  const [listings, setListings] = useState<LiveListing[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getLiveListings(cardId, 10)
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
  }, [cardId]);

  const cheapestTotal = listings?.[0]?.total_usd;

  return (
    <section>
      <div className="mb-3 flex items-baseline justify-between gap-2">
        <h2 className="text-lg font-bold text-gray-900 dark:text-zinc-50">
          Live listings
          {listings && (
            <span className="ml-2 text-sm font-normal text-gray-400">
              · {listings.length}
            </span>
          )}
        </h2>
        {loading && (
          <span className="inline-flex items-center gap-1 text-xs text-gray-500">
            <Loader2 className="h-3 w-3 animate-spin" />
            Fetching from eBay
          </span>
        )}
      </div>

      {err && !listings?.length && (
        <div className="rounded-xl border border-dashed border-gray-200 bg-gray-50 p-6 text-center text-sm text-gray-500 dark:border-[#2D3543] dark:bg-[#1A1F29]">
          Couldn&apos;t fetch live listings right now.
        </div>
      )}

      {!loading && !err && (!listings || listings.length === 0) && (
        <div className="rounded-xl border-2 border-dashed border-gray-200 bg-gray-50/50 p-10 text-center dark:border-[#2D3543] dark:bg-[#1A1F29]/50">
          <p className="text-sm font-medium text-gray-700 dark:text-zinc-300">
            No active eBay listings right now
          </p>
          <p className="mt-1 text-xs text-gray-500 dark:text-zinc-500">
            Either super-rare or just sold out — check back later.
          </p>
        </div>
      )}

      {listings && listings.length > 0 && (
        <>
          {/* Mobile cards */}
          <div className="flex flex-col gap-2 lg:hidden">
            {listings.map((l, i) => (
              <a
                key={l.url}
                href={l.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block rounded-xl border border-gray-200 bg-white p-3 transition-colors hover:border-teal-300 dark:border-[#2D3543] dark:bg-[#1A1F29] dark:hover:border-teal-500/50"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <SourceBadge source={l.source} />
                    {i === 0 && cheapestTotal === l.total_usd && (
                      <span className="rounded-md bg-amber-400/20 px-1.5 py-0.5 text-[10px] font-bold uppercase text-amber-700 ring-1 ring-amber-400/40 dark:text-amber-300">
                        Cheapest
                      </span>
                    )}
                  </div>
                  <span className="inline-flex items-center gap-1 text-xs font-semibold text-teal-600 dark:text-teal-400">
                    Buy <ExternalLink className="h-3 w-3" />
                  </span>
                </div>
                <p className="mt-2 line-clamp-2 text-xs text-gray-600 dark:text-zinc-400">
                  {l.title}
                </p>
                <div className="mt-2 flex items-end justify-between">
                  <div className="text-xs text-gray-400">
                    <p className="font-medium text-gray-700 dark:text-zinc-300">{l.seller}</p>
                    <p>
                      {l.condition} ·{" "}
                      {l.shipping_usd === 0 ? "Free ship" : `+${fmtUSD(l.shipping_usd)} ship`}
                    </p>
                  </div>
                  <p className="font-mono text-lg font-bold text-gray-900 dark:text-zinc-50">
                    {fmtUSD(l.total_usd)}
                  </p>
                </div>
              </a>
            ))}
          </div>

          {/* Desktop table */}
          <div className="hidden overflow-hidden rounded-xl border border-gray-200 bg-white lg:block dark:border-[#2D3543] dark:bg-[#1A1F29]">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50/70 text-left text-xs text-gray-400 dark:border-[#2D3543] dark:bg-[#0F1419]/50 dark:text-zinc-500">
                  <th className="px-4 py-2.5 font-semibold">Source</th>
                  <th className="px-4 py-2.5 font-semibold">Seller</th>
                  <th className="px-4 py-2.5 font-semibold">Condition</th>
                  <th className="px-4 py-2.5 text-right font-semibold">Item</th>
                  <th className="px-4 py-2.5 text-right font-semibold">Ship</th>
                  <th className="px-4 py-2.5 text-right font-semibold">Total</th>
                  <th className="px-4 py-2.5 text-right font-semibold" />
                </tr>
              </thead>
              <tbody>
                {listings.map((l, i) => (
                  <tr
                    key={l.url}
                    className="border-b border-gray-100 last:border-0 hover:bg-gray-50/60 dark:border-[#2D3543]/60 dark:hover:bg-[#222834]/50"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <SourceBadge source={l.source} />
                        {i === 0 && cheapestTotal === l.total_usd && (
                          <span className="rounded bg-amber-400/20 px-1.5 py-0.5 text-[10px] font-bold uppercase text-amber-700 ring-1 ring-amber-400/40 dark:text-amber-300">
                            Cheapest
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-700 dark:text-zinc-300">
                        {l.seller}
                      </div>
                      {l.seller_feedback_pct != null && (
                        <div className="text-[10px] text-gray-400">
                          {l.seller_feedback_pct}% feedback
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-500 dark:text-zinc-400">{l.condition}</td>
                    <td className="px-4 py-3 text-right font-mono text-gray-500 dark:text-zinc-400">
                      {fmtUSD(l.price_usd)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-gray-400">
                      {l.shipping_usd === 0 ? "Free" : fmtUSD(l.shipping_usd)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="font-mono font-bold text-gray-900 dark:text-zinc-50">
                        {fmtUSD(l.total_usd)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <a
                        href={l.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 rounded-full bg-gray-900 px-3 py-1.5 text-xs font-bold text-white hover:bg-gray-800 dark:bg-zinc-100 dark:text-gray-900 dark:hover:bg-white"
                      >
                        Buy <ExternalLink className="h-3 w-3" />
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
