"use client";

import { useRouter } from "next/navigation";
import { ReactNode } from "react";

import { Pagination } from "@/components/Pagination";
import {
  DEFAULT_PAGE_SIZE,
  PageSizeSelector,
} from "@/components/PageSizeSelector";

type Props = {
  q: string;
  currentPage: number;
  totalPages: number;
  total: number;
  pageSize: number;
  renderResults: ReactNode;
};

export function SearchPagination({
  q,
  currentPage,
  totalPages,
  total,
  pageSize,
  renderResults,
}: Props) {
  const router = useRouter();

  const goToPage = (n: number) => {
    const next = new URLSearchParams({ q });
    if (n > 1) next.set("page", String(n));
    if (pageSize !== DEFAULT_PAGE_SIZE) next.set("page_size", String(pageSize));
    router.push(`/search?${next.toString()}`);
  };

  const changePageSize = (size: number) => {
    const next = new URLSearchParams({ q });
    if (size !== DEFAULT_PAGE_SIZE) next.set("page_size", String(size));
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
