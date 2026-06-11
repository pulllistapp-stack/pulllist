"use client";

type Props = {
  currentPage: number;
  totalPages: number;
  total: number;
  pageSize: number;
  onPageChange: (page: number) => void;
};

/**
 * Smart pagination — Prev/Next + clickable page numbers with ellipsis.
 *
 * Examples for current=6:
 *   total=5:        [Prev] 1 2 3 4 5 [Next]
 *   total=13, c=1:  [Prev] 1 2 3 … 13 [Next]
 *   total=13, c=6:  [Prev] 1 … 5 6 7 … 13 [Next]
 *   total=13, c=13: [Prev] 1 … 11 12 13 [Next]
 */
export function Pagination({
  currentPage,
  totalPages,
  total,
  pageSize,
  onPageChange,
}: Props) {
  if (totalPages <= 1) return null;

  const pages = computePageNumbers(currentPage, totalPages);
  const start = (currentPage - 1) * pageSize + 1;
  const end = Math.min(currentPage * pageSize, total);

  return (
    <nav className="flex flex-col gap-3 border-t border-border pt-5 md:flex-row md:items-center md:justify-between">
      <div className="font-mono text-xs text-text-tertiary order-2 md:order-1">
        {start.toLocaleString()}–{end.toLocaleString()} of{" "}
        {total.toLocaleString()}
      </div>

      <div className="flex items-center justify-center gap-1 order-1 md:order-2">
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage <= 1}
          className="rounded-btn border border-border px-2.5 py-1.5 text-sm text-text-secondary hover:border-accent-yellow/40 hover:text-text-primary disabled:opacity-30 disabled:cursor-not-allowed"
        >
          ← Prev
        </button>

        <div className="hidden sm:flex items-center gap-1">
          {pages.map((p, idx) =>
            p === "..." ? (
              <span
                key={`gap-${idx}`}
                className="px-2 text-text-tertiary font-mono select-none"
              >
                …
              </span>
            ) : (
              <button
                key={p}
                onClick={() => onPageChange(p)}
                className={`min-w-[2rem] rounded-btn px-2 py-1 text-sm font-mono transition-colors ${
                  p === currentPage
                    ? "bg-accent-yellow/15 text-accent-yellow border border-accent-yellow/30"
                    : "border border-border text-text-secondary hover:border-accent-yellow/40 hover:text-text-primary"
                }`}
                aria-current={p === currentPage ? "page" : undefined}
              >
                {p}
              </button>
            ),
          )}
        </div>

        <span className="sm:hidden font-mono text-sm text-text-secondary px-2">
          {currentPage} / {totalPages}
        </span>

        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= totalPages}
          className="rounded-btn border border-border px-2.5 py-1.5 text-sm text-text-secondary hover:border-accent-yellow/40 hover:text-text-primary disabled:opacity-30 disabled:cursor-not-allowed"
        >
          Next →
        </button>
      </div>
    </nav>
  );
}

function computePageNumbers(
  current: number,
  total: number,
): (number | "...")[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  const out: (number | "...")[] = [1];

  if (current > 3) out.push("...");

  const start = Math.max(2, current - 1);
  const end = Math.min(total - 1, current + 1);
  for (let i = start; i <= end; i++) out.push(i);

  if (current < total - 2) out.push("...");

  out.push(total);
  return out;
}
