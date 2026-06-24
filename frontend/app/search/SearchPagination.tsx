"use client";

import { useRouter } from "next/navigation";
import { ArrowUpDown } from "lucide-react";
import { ReactNode } from "react";

import { Pagination } from "@/components/Pagination";
import {
  DEFAULT_PAGE_SIZE,
  PageSizeSelector,
} from "@/components/PageSizeSelector";
import type { CardSearchSort } from "@/lib/api";

type Props = {
  q: string;
  currentPage: number;
  totalPages: number;
  total: number;
  pageSize: number;
  sort: CardSearchSort;
  renderResults: ReactNode;
};

const SORT_OPTIONS: { value: CardSearchSort; label: string }[] = [
  { value: "relevance", label: "Most relevant" },
  { value: "price_desc", label: "Price: high → low" },
  { value: "price_asc", label: "Price: low → high" },
  { value: "newest", label: "Newest set" },
  { value: "oldest", label: "Oldest set" },
];

export function SearchPagination({
  q,
  currentPage,
  totalPages,
  total,
  pageSize,
  sort,
  renderResults,
}: Props) {
  const router = useRouter();

  /** Build a URLSearchParams that preserves q + sort + pageSize. Caller
   *  layers on the field they're changing (page / sort / page_size) so
   *  the others survive navigation. */
  const baseParams = (): URLSearchParams => {
    const next = new URLSearchParams({ q });
    if (pageSize !== DEFAULT_PAGE_SIZE) next.set("page_size", String(pageSize));
    if (sort !== "relevance") next.set("sort", sort);
    return next;
  };

  const goToPage = (n: number) => {
    const next = baseParams();
    if (n > 1) next.set("page", String(n));
    router.push(`/search?${next.toString()}`);
  };

  const changePageSize = (size: number) => {
    const next = new URLSearchParams({ q });
    if (size !== DEFAULT_PAGE_SIZE) next.set("page_size", String(size));
    if (sort !== "relevance") next.set("sort", sort);
    router.push(`/search?${next.toString()}`);
  };

  const changeSort = (nextSort: CardSearchSort) => {
    const next = new URLSearchParams({ q });
    if (pageSize !== DEFAULT_PAGE_SIZE) next.set("page_size", String(pageSize));
    if (nextSort !== "relevance") next.set("sort", nextSort);
    router.push(`/search?${next.toString()}`);
  };

  return (
    <>
      <div className="flex flex-wrap items-baseline justify-between gap-3 mb-8">
        <p className="text-sm text-text-secondary font-mono">
          {total.toLocaleString()} {total === 1 ? "match" : "matches"}
        </p>
        <div className="flex items-center gap-3 text-xs">
          {totalPages > 1 && (
            <span className="font-mono text-text-tertiary">
              page {currentPage} / {totalPages}
            </span>
          )}

          <label className="inline-flex items-center gap-1.5 rounded-full border border-border bg-bg-surface px-3 py-1.5 text-xs font-mono text-text-secondary hover:text-text-primary transition-colors">
            <ArrowUpDown className="h-3 w-3" />
            <span className="sr-only">Sort by</span>
            <select
              value={sort}
              onChange={(e) => changeSort(e.target.value as CardSearchSort)}
              className="bg-transparent focus:outline-none cursor-pointer"
              aria-label="Sort search results"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>

          <PageSizeSelector value={pageSize} onChange={changePageSize} />
        </div>
      </div>

      {renderResults}

      <Pagination
        currentPage={currentPage}
        totalPages={totalPages}
        total={total}
        pageSize={pageSize}
        onPageChange={goToPage}
      />
    </>
  );
}
