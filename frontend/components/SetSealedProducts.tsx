"use client";

import { useEffect, useState } from "react";

import { listProductsForSet, type Product } from "@/lib/api";
import { ProductCard } from "./ProductCard";

/**
 * Sealed-products carousel row on the set detail page. Fetches
 * client-side (parent is a client page too) so the SSR of the set page
 * stays cheap. Renders nothing when the set has no sealed rows —
 * cleaner than a "no sealed products" empty state that would clutter
 * older sets that never had TCGCSV product data.
 */
export function SetSealedProducts({ setId }: { setId: string }) {
  const [products, setProducts] = useState<Product[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    listProductsForSet(setId)
      .then((rows) => {
        if (!cancelled) setProducts(rows);
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
