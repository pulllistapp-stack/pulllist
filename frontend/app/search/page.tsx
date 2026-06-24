import Link from "next/link";

import { CardThumb } from "@/components/CardThumb";
import { SearchPagination } from "./SearchPagination";
import {
  Card as CardType,
  CardList,
  searchCards,
  type CardSearchSort,
} from "@/lib/api";

export const dynamic = "force-dynamic";

const DEFAULT_PAGE_SIZE = 50;
const ALLOWED_PAGE_SIZES = new Set([30, 50, 100]);
const ALLOWED_SORTS = new Set<CardSearchSort>([
  "relevance",
  "price_desc",
  "price_asc",
  "newest",
  "oldest",
]);

type Props = {
  searchParams: Promise<{
    q?: string;
    page?: string;
    page_size?: string;
    sort?: string;
  }>;
};

export default async function SearchPage({ searchParams }: Props) {
  const {
    q: rawQ,
    page: pageStr,
    page_size: pageSizeStr,
    sort: sortStr,
  } = await searchParams;
  const q = (rawQ ?? "").trim();
  const page = Math.max(1, Number.parseInt(pageStr ?? "1", 10) || 1);
  const requested = Number.parseInt(pageSizeStr ?? "", 10);
  const pageSize = ALLOWED_PAGE_SIZES.has(requested) ? requested : DEFAULT_PAGE_SIZE;
  const sort: CardSearchSort = ALLOWED_SORTS.has(sortStr as CardSearchSort)
    ? (sortStr as CardSearchSort)
    : "relevance";

  let result: CardList | null = null;
  let error: string | null = null;

  if (q.length > 0) {
    try {
      result = await searchCards(q, page, pageSize, sort);
    } catch (e) {
      error = e instanceof Error ? e.message : "Unknown error";
    }
  }

  const totalPages = result ? Math.max(1, Math.ceil(result.total / pageSize)) : 0;

  return (
    <main className="mx-auto max-w-7xl px-6 py-10">
      <nav className="mb-6 text-sm text-text-secondary">
        <Link href="/" className="hover:text-text-primary">
          Home
        </Link>
        <span className="mx-2 text-text-tertiary">/</span>
        <span className="text-text-primary">Search</span>
      </nav>

      {q.length === 0 ? (
        <div className="rounded-card bg-bg-surface border border-border p-6 text-sm text-text-secondary">
          Type something in the search bar above.
        </div>
      ) : (
        <>
          <h1 className="text-2xl font-bold mb-2">
            Results for{" "}
            <span className="text-accent-yellow">&ldquo;{q}&rdquo;</span>
          </h1>

          {error && (
            <div className="rounded-card bg-accent-red/10 border border-accent-red/30 p-4 text-sm">
              <div className="font-semibold mb-1">Search failed</div>
              <div className="text-text-secondary font-mono">{error}</div>
            </div>
          )}

          {result && (
            <SearchPagination
              q={q}
              currentPage={page}
              totalPages={totalPages}
              total={result.total}
              pageSize={pageSize}
              sort={sort}
              renderResults={
                result.items.length > 0 ? (
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3 mb-10">
                    {result.items.map((c: CardType, idx: number) => (
                      <CardThumb key={c.id} card={c} priority={idx < 12} />
                    ))}
                  </div>
                ) : (
                  <div className="rounded-card bg-bg-surface border border-border p-6 text-sm text-text-secondary">
                    No cards match &ldquo;{q}&rdquo;. Try a different spelling
                    or a Pokémon name like &ldquo;Charizard&rdquo;.
                  </div>
                )
              }
            />
          )}
        </>
      )}
    </main>
  );
}
