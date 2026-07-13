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
 * Sealed-products carousel row on the set detail page. Fetches
 * client-side (parent is a client page too) so the SSR of the set page
 * stays cheap. Renders nothing when the set has no sealed rows —
 * cleaner than a "no sealed products" empty state that would clutter
 * older sets that never had TCGCSV product data.
 */
export function SetSealedProducts({ setId }: { setId: string }) {
  const [products, setProducts] = useState<Product[] | null>(() =>
    readCache(setId),
  );

  useEffect(() => {
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
  }, [setId]);

  if (!products || products.length === 0) return null;

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
