"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { CardThumb } from "@/components/CardThumb";
import { FilterSidebar } from "@/components/FilterSidebar";
import { MascotLoader } from "@/components/MascotLoader";
import { Pagination } from "@/components/Pagination";
import {
  DEFAULT_PAGE_SIZE,
  PageSizeSelector,
} from "@/components/PageSizeSelector";
import { browseCards, BrowseParams, CardList } from "@/lib/api";
import { getToken } from "@/lib/auth";

export default function BrowseCardsPage() {
  return (
    <Suspense fallback={<PageLoading />}>
      <BrowseCardsContent />
    </Suspense>
  );
}

function PageLoading() {
  return (
    <main className="mx-auto max-w-7xl px-4 py-8">
      <MascotLoader size="lg" className="py-12" />
    </main>
  );
}

function BrowseCardsContent() {
  const router = useRouter();
  const params = useSearchParams();
  const { user } = useAuth();
  const [data, setData] = useState<CardList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState(params.get("q") ?? "");

  const pageSize =
    Number(params.get("page_size") ?? String(DEFAULT_PAGE_SIZE)) ||
    DEFAULT_PAGE_SIZE;

  useEffect(() => {
    setSearchInput(params.get("q") ?? "");
  }, [params]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    const browseParams: BrowseParams = {
      page_size: pageSize,
      page: Number(params.get("page") ?? "1") || 1,
    };
    for (const key of [
      "q",
      "set_id",
      "rarity",
      "supertype",
      "type",
      "subtype",
      "artist",
      "owned",
      "condition",
      "language",
      "sort",
    ] as const) {
      const v = params.get(key);
      if (v) (browseParams as Record<string, unknown>)[key] = v;
    }
    for (const key of ["hp_min", "hp_max", "price_min", "price_max"] as const) {
      const v = params.get(key);
      if (v) (browseParams as Record<string, unknown>)[key] = Number(v);
    }

    (async () => {
      try {
        const token = user ? getToken() ?? undefined : undefined;
        const result = await browseCards(browseParams, token);
        if (!cancelled) setData(result);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Unknown");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [params, user, pageSize]);

  const submitSearch = (e: FormEvent) => {
    e.preventDefault();
    const next = new URLSearchParams(params.toString());
    if (searchInput.trim()) next.set("q", searchInput.trim());
    else next.delete("q");
    next.delete("page");
    router.replace(`/cards?${next.toString()}`, { scroll: false });
  };

  const currentPage = Number(params.get("page") ?? "1") || 1;
  const totalPages = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 0;

  const goToPage = (n: number) => {
    const next = new URLSearchParams(params.toString());
    if (n === 1) next.delete("page");
    else next.set("page", String(n));
    router.replace(`/cards?${next.toString()}`, { scroll: false });
  };

  const changePageSize = (size: number) => {
    const next = new URLSearchParams(params.toString());
    if (size === DEFAULT_PAGE_SIZE) next.delete("page_size");
    else next.set("page_size", String(size));
    next.delete("page");
    router.replace(`/cards?${next.toString()}`, { scroll: false });
  };

  // Region chips — right under the search bar, above the sidebar's fine-
  // grain filters. `language` is a raw Card.language code (en / ja / ko),
  // matches the backend index directly. `null` selection = all regions.
  const activeLanguage = params.get("language");
  const chooseLanguage = (lang: string | null) => {
    const next = new URLSearchParams(params.toString());
    if (lang) next.set("language", lang);
    else next.delete("language");
    next.delete("page");
    router.replace(`/cards?${next.toString()}`, { scroll: false });
  };
  const REGION_CHIPS: { label: string; value: string | null; flag: string }[] = [
    { label: "All", value: null, flag: "🌏" },
    { label: "EN", value: "en", flag: "🇺🇸" },
    { label: "JP", value: "ja", flag: "🇯🇵" },
  ];

  return (
    <main className="mx-auto max-w-7xl px-4 py-8">
      <nav className="mb-4 text-sm text-text-secondary">
        <Link href="/" className="hover:text-text-primary">
          Home
        </Link>
        <span className="mx-2 text-text-tertiary">/</span>
        <span className="text-text-primary">Browse cards</span>
      </nav>

      <div className="flex flex-col md:flex-row gap-6">
        <div className="md:w-64 flex-shrink-0">
          {/* Sidebar scroll:
                - 100dvh (not 100vh) so the mobile URL bar / cookie
                  banner collapse doesn't leave the last filter out
                  of reach — dvh tracks the actually-available area.
                - 5rem reservation matches top-20 exactly; no extra
                  top slack means the whole viewport minus the header
                  is available.
                - pb-16 (4rem) at the bottom is what LO was missing:
                  expanding the ILLUSTRATOR / PRICE accordions can
                  now grow their option lists past what used to be
                  a flush cut-off edge. */}
          <div className="md:sticky md:top-20 md:max-h-[calc(100dvh-5rem)] md:overflow-y-auto md:overscroll-contain md:pr-2 md:pb-16 filter-scroll">
            <FilterSidebar basePath="/cards" />
          </div>
        </div>

        <div className="flex-1 min-w-0">
          <form onSubmit={submitSearch} className="mb-3 flex gap-2">
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search card name…"
              className="flex-1 rounded-btn bg-bg-surface border border-border px-3 py-2 text-sm focus:outline-none focus:border-accent-yellow/50"
            />
            <button
              type="submit"
              className="rounded-btn bg-accent-yellow text-bg font-medium px-4 py-2 hover:brightness-110"
            >
              Search
            </button>
          </form>

          <div
            role="tablist"
            aria-label="Region"
            className="mb-5 flex flex-wrap gap-1.5"
          >
            {REGION_CHIPS.map((c) => {
              const active = c.value === activeLanguage;
              return (
                <button
                  key={c.label}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  onClick={() => chooseLanguage(c.value)}
                  className={
                    "inline-flex items-center gap-1 rounded-chip border px-2.5 py-1 text-xs font-medium transition-colors " +
                    (active
                      ? "bg-accent-yellow text-bg border-accent-yellow"
                      : "bg-bg-surface text-text-secondary border-border hover:text-text-primary hover:border-text-tertiary")
                  }
                >
                  <span aria-hidden>{c.flag}</span>
                  <span>{c.label}</span>
                </button>
              );
            })}
          </div>

          <div className="flex flex-wrap items-baseline justify-between gap-3 mb-4">
            <h1 className="text-xl font-bold">
              {data ? data.total.toLocaleString() : "—"}{" "}
              <span className="text-text-secondary text-sm font-normal">
                {data && data.total === 1 ? "card" : "cards"}
              </span>
            </h1>
            <div className="flex items-center gap-3 text-xs">
              {totalPages > 1 && (
                <span className="font-mono text-text-tertiary">
                  page {currentPage} / {totalPages}
                </span>
              )}
              <PageSizeSelector value={pageSize} onChange={changePageSize} />
            </div>
          </div>

          {error && (
            <div className="rounded-card bg-accent-red/10 border border-accent-red/30 p-4 text-sm mb-4">
              <div className="font-semibold mb-1">Failed to load</div>
              <div className="text-text-secondary font-mono">{error}</div>
            </div>
          )}

          {loading && <MascotLoader size="lg" className="py-12" />}

          {!loading && data && data.items.length === 0 && (
            <div className="rounded-card border border-border bg-bg-surface p-8 text-center">
              <h2 className="font-semibold mb-2">No cards match these filters</h2>
              <p className="text-sm text-text-secondary">
                Try clearing some filters or broadening the search.
              </p>
            </div>
          )}

          {!loading && data && data.items.length > 0 && (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3 mb-8">
                {data.items.map((c, idx) => (
                  <CardThumb key={c.id} card={c} priority={idx < 8} />
                ))}
              </div>

              <Pagination
                currentPage={currentPage}
                totalPages={totalPages}
                total={data.total}
                pageSize={pageSize}
                onPageChange={goToPage}
              />
            </>
          )}
        </div>
      </div>
    </main>
  );
}
