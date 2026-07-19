import Link from "next/link";

import { RegionTabs } from "@/components/RegionTabs";
import { SetsBrowser } from "@/components/SetsBrowser";
import {
  CatalogRegion,
  listSets,
  SetWithCardCount,
} from "@/lib/api";

export const dynamic = "force-dynamic";

const _VALID_REGIONS: CatalogRegion[] = ["en", "ja", "ko", "zh-cn", "zh-tw"];

function normalizeRegion(raw: string | string[] | undefined): CatalogRegion {
  const v = Array.isArray(raw) ? raw[0] : raw;
  return (_VALID_REGIONS as string[]).includes(v ?? "") ? (v as CatalogRegion) : "en";
}

export default async function SetsPage({
  searchParams,
}: {
  searchParams: Promise<{ region?: string }>;
}) {
  const params = await searchParams;
  const region = normalizeRegion(params.region);

  let sets: SetWithCardCount[] = [];
  let error: string | null = null;

  try {
    sets = await listSets({ region });
  } catch (e) {
    error = e instanceof Error ? e.message : "Unknown error";
  }

  const totalCards = sets.reduce((n, s) => n + s.card_count, 0);

  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <nav className="mb-6">
        <Link href="/" className="text-sm text-text-secondary hover:text-text-primary">
          ← Home
        </Link>
      </nav>

      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold mb-1">Expansion Sets</h1>
          <p className="text-text-secondary text-sm">
            {sets.length} sets · {totalCards.toLocaleString()} cards · Explore every generation of the Pokémon TCG
          </p>
        </div>
      </div>

      <div className="mb-8">
        <RegionTabs active={region} hrefBase="/sets" />
      </div>

      {error && (
        <div className="rounded-card bg-accent-red/10 border border-accent-red/30 p-4 text-sm mb-6">
          <div className="font-semibold mb-1">Could not reach API</div>
          <div className="text-text-secondary font-mono">{error}</div>
        </div>
      )}

      {!error && sets.length === 0 && (
        <div className="rounded-card bg-bg-surface border border-border p-6 text-sm text-text-secondary">
          No sets indexed for this region yet.
        </div>
      )}

      {!error && sets.length > 0 && (
        <SetsBrowser initialSets={sets} region={region} />
      )}
    </main>
  );
}
