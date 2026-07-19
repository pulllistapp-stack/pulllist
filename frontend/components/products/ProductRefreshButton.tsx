"use client";

/**
 * Refresh pill for sealed product pages. Hits POST /products/{id}/refresh
 * which re-pulls prices from TCGCSV, updates the Product row + inserts
 * today's snapshot, and returns the fresh numbers so the button can
 * override the SSR'd price in place instead of waiting on a page reload.
 *
 * Cooldown: 5 min per product. Repeated clicks inside the window show
 * a soft "Just refreshed" state — we still flash the badge but never
 * lie about a backend refresh.
 */

import { useEffect, useRef, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";

import { refreshSealedProduct } from "@/lib/api";

type Props = {
  productId: string;
  /** SSR'd price so the button can start with something showing and
   *  swap in the fresh value in place. Optional — display works
   *  from render-time props alone. */
  initialMarket: number | null;
  initialLow: number | null;
  initialHigh: number | null;
};

function fmt(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  if (v >= 1000) return `$${Math.round(v).toLocaleString()}`;
  return `$${v.toFixed(2)}`;
}

export function ProductRefreshButton({
  productId,
  initialMarket,
  initialLow,
  initialHigh,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [override, setOverride] = useState<{
    market: number | null;
    low: number | null;
    high: number | null;
  } | null>(null);
  const [showFresh, setShowFresh] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const freshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (freshTimer.current) clearTimeout(freshTimer.current);
    };
  }, []);

  const market = override?.market ?? initialMarket;
  const low = override?.low ?? initialLow;
  const high = override?.high ?? initialHigh;

  async function onClick() {
    if (busy) return;
    setBusy(true);
    setErrorMsg(null);
    try {
      const res = await refreshSealedProduct(productId);
      setOverride({
        market: res.market_price_usd,
        low: res.low_price_usd,
        high: res.high_price_usd,
      });
      setShowFresh(true);
      if (freshTimer.current) clearTimeout(freshTimer.current);
      freshTimer.current = setTimeout(() => setShowFresh(false), 2500);
    } catch (e) {
      // 429 (cooldown) still shows the "Up to date" badge because the
      // server-side state hasn't drifted — flashing the same value is
      // more honest than a scary error.
      const msg = e instanceof Error ? e.message : "Refresh failed";
      if (msg.toLowerCase().includes("cooldown")) {
        setShowFresh(true);
        if (freshTimer.current) clearTimeout(freshTimer.current);
        freshTimer.current = setTimeout(() => setShowFresh(false), 2500);
      } else {
        setErrorMsg(msg);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline gap-3">
        <span className="text-4xl font-extrabold text-accent-green">
          {fmt(market)}
        </span>
        {low != null && high != null && (
          <span className="text-xs font-mono text-text-tertiary">
            {fmt(low)} – {fmt(high)}
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          {showFresh && (
            <span className="inline-flex items-center gap-1 rounded-full bg-accent-green/15 text-accent-green border border-accent-green/30 px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider font-bold">
              <span aria-hidden>✓</span>
              Up to date
            </span>
          )}
          <button
            type="button"
            onClick={onClick}
            disabled={busy}
            title="Pull fresh prices from TCGCSV"
            aria-label="Refresh prices"
            className="inline-flex items-center gap-1 rounded-full border border-border bg-bg-surface px-2.5 py-1 text-xs font-semibold text-text-secondary hover:border-accent-yellow/60 hover:text-text-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {busy ? (
              <>
                <Loader2 className="h-3 w-3 animate-spin" />
                Refreshing
              </>
            ) : (
              <>
                <RefreshCw className="h-3 w-3" />
                Refresh
              </>
            )}
          </button>
        </div>
      </div>
      {errorMsg && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-1.5 text-[11px] text-red-400">
          <span className="font-mono font-bold">Refresh error:</span>{" "}
          {errorMsg}
        </div>
      )}
    </div>
  );
}
