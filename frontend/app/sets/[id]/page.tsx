"use client";

import Image from "next/image";
import Link from "next/link";
import { notFound, useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { CardThumb } from "@/components/CardThumb";
import { FilterSidebar } from "@/components/FilterSidebar";
import { Pagination } from "@/components/Pagination";
import {
  DEFAULT_PAGE_SIZE,
  PageSizeSelector,
} from "@/components/PageSizeSelector";
import { SetCompletion } from "@/components/SetCompletion";
import { SetSealedProducts } from "@/components/SetSealedProducts";
import { SetReportModal } from "@/components/SetReportModal";
import {
  browseCards,
  BrowseParams,
  CardList,
  getSet,
  listProductsForSet,
  Product,
  SetWithCardCount,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import { seriesLabel } from "@/lib/series";

export default function SetDetailPage() {
  return (
    <Suspense fallback={<PageLoading />}>
      <SetDetailContent />
    </Suspense>
  );
}

function PageLoading() {
  return (
    <main className="mx-auto max-w-[100rem] px-4 py-8">
      <div className="text-text-tertiary py-12 text-center">Loading…</div>
    </main>
  );
}

function SetDetailContent() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { user } = useAuth();

  const setId = params.id;

  const [set, setSet] = useState<SetWithCardCount | null>(null);
  const [data, setData] = useState<CardList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showReport, setShowReport] = useState(false);
  const [sealedProducts, setSealedProducts] = useState<Product[] | null>(null);

  // Cards ↔ Sealed tab state, persisted in URL so back navigation +
  // link sharing land on the same view. ?tab=sealed opens the sealed
  // panel; anything else falls back to cards (default).
  const activeTab: "cards" | "sealed" =
    searchParams.get("tab") === "sealed" ? "sealed" : "cards";

  const switchTab = (t: "cards" | "sealed") => {
    const next = new URLSearchParams(searchParams.toString());
    if (t === "cards") next.delete("tab");
    else next.set("tab", t);
    // Reset paging state when switching tabs — the two panels have
    // independent list layouts and holding page=N from cards makes no
    // sense on sealed.
    next.delete("page");
    router.replace(`/sets/${setId}?${next.toString()}`, { scroll: false });
  };

  const pageSize =
    Number(searchParams.get("page_size") ?? String(DEFAULT_PAGE_SIZE)) ||
    DEFAULT_PAGE_SIZE;

  // Fetch sealed products once per setId — needed for tab count badge
  // even when the sealed panel isn't active. Shape-mirrors what
  // SetSealedProducts used to do internally; centralized here so both
  // the tab badge and the sealed panel read the same source.
  useEffect(() => {
    if (!setId) return;
    let cancelled = false;
    listProductsForSet(setId)
      .then((rows) => {
        if (!cancelled) setSealedProducts(rows);
      })
      .catch(() => {
        if (!cancelled) setSealedProducts([]);
      });
    return () => {
      cancelled = true;
    };
  }, [setId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const s = await getSet(setId);
        if (!cancelled) setSet(s);
      } catch (e) {
        if (e instanceof Error && e.message.includes("404")) {
          notFound();
        }
        if (!cancelled)
          setError(e instanceof Error ? e.message : "Unknown error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [setId]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    const browseParams: BrowseParams = {
      set_id: setId,
      sort: "number_asc",
      page_size: pageSize,
      page: Number(searchParams.get("page") ?? "1") || 1,
    };
    for (const key of [
      "q",
      "rarity",
      "supertype",
      "type",
      "subtype",
      "artist",
      "owned",
      "condition",
      "sort",
    ] as const) {
      const v = searchParams.get(key);
      if (v) (browseParams as Record<string, unknown>)[key] = v;
    }
    for (const key of ["hp_min", "hp_max", "price_min", "price_max"] as const) {
      const v = searchParams.get(key);
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
  }, [setId, searchParams, user, pageSize]);

  const currentPage = Number(searchParams.get("page") ?? "1") || 1;
  const totalPages = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 0;

  const goToPage = (n: number) => {
    const next = new URLSearchParams(searchParams.toString());
    if (n === 1) next.delete("page");
    else next.set("page", String(n));
    router.replace(`/sets/${setId}?${next.toString()}`, { scroll: false });
  };

  const changePageSize = (size: number) => {
    const next = new URLSearchParams(searchParams.toString());
    if (size === DEFAULT_PAGE_SIZE) next.delete("page_size");
    else next.set("page_size", String(size));
    next.delete("page");
    router.replace(`/sets/${setId}?${next.toString()}`, { scroll: false });
  };

  const releaseDate = set?.release_date
    ? new Date(set.release_date).toLocaleDateString("en-US", {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : null;

  const hasActiveFilters = Array.from(searchParams.entries()).some(
    ([k]) => k !== "page",
  );

  return (
    <main className="mx-auto max-w-[100rem] px-4 py-8">
      <nav className="mb-6 text-sm text-text-secondary">
        <Link href="/" className="hover:text-text-primary">
          Home
        </Link>
        <span className="mx-2 text-text-tertiary">/</span>
        <Link href="/sets" className="hover:text-text-primary">
          Sets
        </Link>
        <span className="mx-2 text-text-tertiary">/</span>
        <span className="text-text-primary">{set?.name ?? setId}</span>
      </nav>

      {error && (
        <div className="rounded-card bg-accent-red/10 border border-accent-red/30 p-4 text-sm mb-6">
          <div className="font-semibold mb-1">Failed</div>
          <div className="text-text-secondary font-mono">{error}</div>
        </div>
      )}

      {set && (
        <header className="mb-8 flex flex-col md:flex-row gap-6 items-center md:items-end">
          <div className="flex-shrink-0">
            {set.logo_url ? (
              <Image
                src={set.logo_url}
                alt={set.name}
                width={280}
                height={112}
                className="max-h-28 w-auto object-contain"
                unoptimized
                priority
              />
            ) : (
              <div className="h-28 w-56 flex items-center justify-center text-text-tertiary">
                no logo
              </div>
            )}
          </div>

          <div className="flex-1 text-center md:text-left">
            <div className="flex items-start justify-center md:justify-between gap-3 mb-1 flex-wrap">
              <h1 className="text-3xl font-bold tracking-tight">{set.name}</h1>
              <button
                type="button"
                onClick={() => setShowReport(true)}
                title="Report missing cards, wrong images, or bad metadata"
                className="shrink-0 inline-flex items-center gap-1 rounded-full border border-border bg-bg-surface px-3 py-1.5 text-xs font-semibold text-text-tertiary hover:text-accent-red hover:border-accent-red/40 transition-colors"
              >
                <span aria-hidden>⚠</span>
                Report
              </button>
            </div>
            <div className="text-text-secondary text-sm flex flex-wrap gap-x-4 gap-y-1 justify-center md:justify-start">
              {set.series && (
                <span>
                  <span className="text-text-tertiary">Series ·</span>{" "}
                  {seriesLabel(set.series)}
                </span>
              )}
              {releaseDate && (
                <span>
                  <span className="text-text-tertiary">Released ·</span>{" "}
                  {releaseDate}
                </span>
              )}
              {set.ptcgo_code && (
                <span className="font-mono text-text-tertiary">
                  {set.ptcgo_code}
                </span>
              )}
            </div>
            <div className="mt-3 font-mono text-sm">
              <span className="text-accent-yellow">{set.card_count}</span>
              <span className="text-text-tertiary">
                {" / "}
                {set.total ?? set.printed_total ?? "?"} cards
                {set.printed_total &&
                  set.total &&
                  set.total > set.printed_total && (
                    <span>
                      {" "}
                      ({set.printed_total} printed + {set.total - set.printed_total}{" "}
                      secret)
                    </span>
                  )}
              </span>
            </div>
          </div>
        </header>
      )}

      {set && (
        <div className="mb-6">
          <SetCompletion setId={set.id} totalCards={set.card_count} />
        </div>
      )}

      {/* Cards / Sealed tab bar. Cards is the default; sealed only
          appears if the set has at least one sealed product indexed
          (older sets pre-TCGCSV era return empty). */}
      {set && (
        <div className="mb-6 flex items-center gap-1 border-b border-border">
          <TabButton
            active={activeTab === "cards"}
            onClick={() => switchTab("cards")}
            count={set.card_count}
          >
            Cards
          </TabButton>
          {sealedProducts && sealedProducts.length > 0 && (
            <TabButton
              active={activeTab === "sealed"}
              onClick={() => switchTab("sealed")}
              count={sealedProducts.length}
            >
              Sealed
            </TabButton>
          )}
        </div>
      )}

      {activeTab === "cards" && (
        <div className="flex flex-col md:flex-row gap-6">
          <div className="md:w-60 flex-shrink-0">
            {/* Same sidebar scroll fix as /cards — see the comment there
                for why 100dvh + pb-16 replaces 100vh-5.5rem. */}
            <div className="md:sticky md:top-20 md:max-h-[calc(100dvh-5rem)] md:overflow-y-auto md:overscroll-contain md:pr-2 md:pb-16 filter-scroll">
              <FilterSidebar
                basePath={`/sets/${setId}`}
                lockedSetId={setId}
                language={set?.language}
              />
            </div>
          </div>

          <div className="flex-1 min-w-0">
            {data && (
              <div className="flex flex-wrap items-baseline justify-between gap-3 mb-4">
                <div className="text-sm text-text-secondary">
                  <span className="text-text-primary font-medium">
                    {data.total.toLocaleString()}
                  </span>{" "}
                  {hasActiveFilters ? "matching" : "cards"}
                </div>
                <div className="flex items-center gap-3 text-xs">
                  {totalPages > 1 && (
                    <span className="font-mono text-text-tertiary">
                      page {currentPage} / {totalPages}
                    </span>
                  )}
                  <PageSizeSelector value={pageSize} onChange={changePageSize} />
                </div>
              </div>
            )}

            {loading && (
              <div className="text-text-tertiary py-12 text-center">Loading…</div>
            )}

            {!loading && data && data.items.length === 0 && (
              <div className="rounded-card border border-border bg-bg-surface p-8 text-center">
                <h2 className="font-semibold mb-2">
                  {hasActiveFilters
                    ? "No cards match these filters"
                    : "No cards seeded yet"}
                </h2>
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
      )}

      {activeTab === "sealed" && set && (
        <SetSealedProducts setId={set.id} products={sealedProducts} expanded />
      )}

      {showReport && set && (
        <SetReportModal
          setId={set.id}
          setName={set.name}
          onClose={() => setShowReport(false)}
        />
      )}
    </main>
  );
}

function TabButton({
  active,
  onClick,
  count,
  children,
}: {
  active: boolean;
  onClick: () => void;
  count?: number;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        "-mb-px flex items-center gap-2 rounded-t-md border-b-2 px-4 py-2.5 text-sm font-semibold transition-colors " +
        (active
          ? "border-accent-yellow text-text-primary"
          : "border-transparent text-text-tertiary hover:text-text-secondary")
      }
    >
      <span>{children}</span>
      {count != null && (
        <span
          className={
            "rounded-full px-2 py-0.5 text-[10px] font-mono " +
            (active
              ? "bg-accent-yellow/15 text-accent-yellow"
              : "bg-bg-surface text-text-tertiary")
          }
        >
          {count}
        </span>
      )}
    </button>
  );
}
