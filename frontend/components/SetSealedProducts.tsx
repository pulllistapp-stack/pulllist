"use client";

import { useEffect, useState } from "react";

import { listProductsForSet, type Product } from "@/lib/api";
import { ProductCard } from "./ProductCard";

// sessionStorage TTL for sealed-product responses. Products are
// catalog data that changes ~daily at most, so a 5-min in-tab cache
// dramatically cuts /products/set/{id}/list hits when a user hops
// between /sets pages during a browsing session — the biggest driver
// of surplus Neon compute this month. Cleared automatically when
// the tab closes; no cross-tab persistence needed.
const CACHE_KEY_PREFIX = "pl:sealed:";
const CACHE_TTL_MS = 5 * 60 * 1000;

type CacheEntry = { at: number; rows: Product[] };

function readCache(setId: string): Product[] | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(CACHE_KEY_PREFIX + setId);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CacheEntry;
    if (Date.now() - parsed.at > CACHE_TTL_MS) return null;
    return parsed.rows;
  } catch {
    return null;
  }
}

function writeCache(setId: string, rows: Product[]) {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(
      CACHE_KEY_PREFIX + setId,
      JSON.stringify({ at: Date.now(), rows } satisfies CacheEntry),
    );
  } catch {
    // storage full / disabled — silently skip cache write; the fetch
    // path still works.
  }
}

/**
 * Sealed-products grid on the set detail page. Two use modes:
 *
 *   - default (`expanded=false`): compact carousel row surfaced above
 *     the card grid — how the component originally shipped. Renders
 *     nothing when there are no sealed rows so older sets don't get a
 *     hollow section.
 *
 *   - expanded (`expanded=true`): full-width panel body used inside
 *     the Cards / Sealed tab layout — larger grid, empty state kept.
 *
 * Fetches client-side by default so SSR stays cheap. When the parent
 * already has the products list (e.g. it needed the count for a tab
 * badge), it can pass `products` and skip the fetch entirely.
 */
export function SetSealedProducts({
  setId,
  products: injectedProducts,
  expanded = false,
}: {
  setId: string;
  products?: Product[] | null;
  expanded?: boolean;
}) {
  const parentProvided = injectedProducts !== undefined;
  const [products, setProducts] = useState<Product[] | null>(() => {
    if (parentProvided) return injectedProducts ?? null;
    return readCache(setId);
  });

  useEffect(() => {
    if (parentProvided) {
      setProducts(injectedProducts ?? null);
      return;
    }
    let cancelled = false;
    const cached = readCache(setId);
    if (cached) {
      setProducts(cached);
      return;
    }
    listProductsForSet(setId)
      .then((rows) => {
        if (!cancelled) {
          setProducts(rows);
          writeCache(setId, rows);
        }
      })
      .catch(() => {
        if (!cancelled) setProducts([]);
      });
    return () => {
      cancelled = true;
    };
  }, [setId, parentProvided, injectedProducts]);

  // Compact mode collapses to nothing when there's no data — that's
  // deliberate. Expanded mode keeps a proper empty state because the
  // sealed tab exists precisely to answer "does this set have sealed
  // product data" and silently disappearing would be confusing.
  if (!products || products.length === 0) {
    if (!expanded) return null;
    return (
      <div className="rounded-card border border-dashed border-border/60 bg-bg-surface/40 p-8 text-center">
        <div className="mb-1 text-sm font-semibold text-text-secondary">
          No sealed products indexed for this set yet
        </div>
        <div className="text-xs text-text-tertiary">
          Older sets sometimes don&apos;t show up in TCGCSV&apos;s sealed
          catalog. Newer releases (Mega Evolution era, Ascended Heroes,
          30th Celebration…) carry the full sealed lineup.
        </div>
      </div>
    );
  }

  if (expanded) {
    return (
      <div>
        <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
          <div className="text-sm text-text-secondary">
            <span className="font-medium text-text-primary">
              {products.length.toLocaleString()}
            </span>{" "}
            sealed SKU{products.length === 1 ? "" : "s"}
          </div>
          <div className="text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
            Booster Box · ETB · Bundle · Premium · Tin · Blister
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
          {products.map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <section className="mb-6">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="text-lg font-bold tracking-tight">
          Sealed products
        </h2>
        <span className="text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
          {products.length} SKU
          {products.length === 1 ? "" : "s"}
        </span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
        {products.map((p) => (
          <ProductCard key={p.id} product={p} />
        ))}
      </div>
    </section>
  );
}
