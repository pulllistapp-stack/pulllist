"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState } from "react";

import { MascotLoader } from "@/components/MascotLoader";
import { ProductCard } from "@/components/ProductCard";
import {
  listProducts,
  type ProductBrowseParams,
  type ProductList,
  type ProductType,
} from "@/lib/api";

const TYPE_CHIPS: { value: ProductType | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "booster_box", label: "Booster Box" },
  { value: "etb", label: "ETB" },
  { value: "booster_bundle", label: "Bundle" },
  { value: "premium_collection", label: "Premium" },
  { value: "tin", label: "Tin" },
  { value: "blister", label: "Blister" },
  { value: "build_battle", label: "Build & Battle" },
];

// Country/language filter sits ABOVE the product-type row — pick a
// catalog first, then narrow by SKU shape. Order mirrors the site's
// established EN > JP > KR sort (see /sets), so muscle memory carries.
type LanguageFilter = "all" | "en" | "ja" | "ko";
const LANGUAGE_CHIPS: { value: LanguageFilter; label: string; flag: string }[] = [
  { value: "all", label: "All countries", flag: "🌐" },
  { value: "en", label: "English", flag: "🇺🇸" },
  { value: "ja", label: "Japanese", flag: "🇯🇵" },
  { value: "ko", label: "Korean", flag: "🇰🇷" },
];

export default function ProductsPage() {
  return (
    <Suspense fallback={<PageLoading />}>
      <ProductsContent />
    </Suspense>
  );
}

function PageLoading() {
  return (
    <main className="mx-auto max-w-[100rem] px-4 py-8">
      <MascotLoader size="lg" className="py-12" />
    </main>
  );
}

function ProductsContent() {
  const router = useRouter();
  const params = useSearchParams();
  const [data, setData] = useState<ProductList | null>(null);
  const [loading, setLoading] = useState(true);

  const activeType = (params.get("product_type") as ProductType | null) ?? "all";
  const activeLanguage =
    (params.get("language") as LanguageFilter | null) ?? "all";
  const sort = (params.get("sort") as ProductBrowseParams["sort"]) ?? "newest";

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const query: ProductBrowseParams = {
      sort,
      page_size: 60,
    };
    if (activeType !== "all") query.product_type = activeType as ProductType;
    if (activeLanguage !== "all") {
      query.language = activeLanguage as "en" | "ja" | "ko";
    }
    const setFilter = params.get("set_id");
    if (setFilter) query.set_id = setFilter;

    listProducts(query)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch(() => {
        if (!cancelled) setData({ items: [], total: 0, page: 1, page_size: 60 });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeType, activeLanguage, sort, params]);

  const setChip = (t: ProductType | "all") => {
    const next = new URLSearchParams(params.toString());
    if (t === "all") next.delete("product_type");
    else next.set("product_type", t);
    router.replace(`/products?${next}`, { scroll: false });
  };

  const setLanguageChip = (lang: LanguageFilter) => {
    const next = new URLSearchParams(params.toString());
    if (lang === "all") next.delete("language");
    else next.set("language", lang);
    router.replace(`/products?${next}`, { scroll: false });
  };

  const setSort = (s: string) => {
    const next = new URLSearchParams(params.toString());
    next.set("sort", s);
    router.replace(`/products?${next}`, { scroll: false });
  };

  return (
    <main className="mx-auto max-w-[100rem] px-4 py-8">
      <nav className="mb-4 text-sm text-text-secondary">
        <Link href="/" className="hover:text-text-primary">
          Home
        </Link>
        <span className="mx-2 text-text-tertiary">/</span>
        <span className="text-text-primary">Sealed products</span>
      </nav>

      <div className="mb-6">
        <h1 className="text-2xl font-extrabold tracking-tight">
          Sealed products
        </h1>
        <p className="mt-1 text-sm text-text-secondary">
          Booster boxes, ETBs, bundles, tins, and blisters. Prices from
          TCGplayer; expected value calculated from set rarity distribution.
        </p>
      </div>

      {/* Language / country chips — picked first so the type row below
          filters within a chosen catalog. Placed above so the eye lands
          on region before SKU shape (mirrors /sets filter ordering). */}
      <div
        role="tablist"
        aria-label="Catalog language"
        className="mb-2 flex flex-wrap gap-1.5"
      >
        {LANGUAGE_CHIPS.map((c) => {
          const active = c.value === activeLanguage;
          return (
            <button
              key={c.value}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setLanguageChip(c.value)}
              className={
                "inline-flex items-center gap-1.5 rounded-chip border px-2.5 py-1 text-xs font-medium transition-colors " +
                (active
                  ? "bg-accent-yellow text-bg border-accent-yellow"
                  : "bg-bg-surface text-text-secondary border-border hover:text-text-primary hover:border-text-tertiary")
              }
            >
              <span aria-hidden="true">{c.flag}</span>
              <span>{c.label}</span>
            </button>
          );
        })}
      </div>

      {/* Type chips */}
      <div
        role="tablist"
        aria-label="Product type"
        className="mb-4 flex flex-wrap gap-1.5"
      >
        {TYPE_CHIPS.map((c) => {
          const active = c.value === activeType;
          return (
            <button
              key={c.value}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setChip(c.value)}
              className={
                "inline-flex items-center rounded-chip border px-2.5 py-1 text-xs font-medium transition-colors " +
                (active
                  ? "bg-accent-yellow text-bg border-accent-yellow"
                  : "bg-bg-surface text-text-secondary border-border hover:text-text-primary hover:border-text-tertiary")
              }
            >
              {c.label}
            </button>
          );
        })}
      </div>

      <div className="mb-5 flex flex-wrap items-baseline justify-between gap-3">
        <div className="text-sm text-text-secondary">
          {data ? (
            <>
              <span className="text-text-primary font-medium">
                {data.total.toLocaleString()}
              </span>{" "}
              products
            </>
          ) : (
            "—"
          )}
        </div>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          className="text-xs bg-bg-surface border border-border rounded-btn px-2 py-1 focus:outline-none focus:border-accent-yellow/50"
        >
          <option value="newest">Newest</option>
          <option value="price_desc">Price · high to low</option>
          <option value="price_asc">Price · low to high</option>
          <option value="name">Name</option>
        </select>
      </div>

      {loading && <MascotLoader size="lg" className="py-12" />}

      {!loading && data && data.items.length === 0 && (
        <div className="rounded-card border border-border bg-bg-surface p-8 text-center">
          <h2 className="font-semibold mb-1">No products match these filters</h2>
          <p className="text-sm text-text-secondary">Try clearing filters.</p>
        </div>
      )}

      {!loading && data && data.items.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
          {data.items.map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
      )}
    </main>
  );
}
