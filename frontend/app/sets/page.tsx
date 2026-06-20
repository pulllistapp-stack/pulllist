import Image from "next/image";
import Link from "next/link";

import { RegionTabs } from "@/components/RegionTabs";
import { SetsBrowser } from "@/components/SetsBrowser";
import {
  CatalogRegion,
  listSets,
  SetWithCardCount,
} from "@/lib/api";

export const dynamic = "force-dynamic";

function normalizeRegion(raw: string | string[] | undefined): CatalogRegion {
  const v = Array.isArray(raw) ? raw[0] : raw;
  return v === "ja" || v === "ko" ? v : "en";
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

      {!error && sets.length === 0 && region === "ko" && (
        <div className="rounded-card bg-bg-surface border border-border p-10 text-center max-w-xl mx-auto">
          <div className="mx-auto mb-4 h-20 w-20 rounded-full bg-white flex items-center justify-center shadow-sm">
            <Image
              src="/pullist-mascot.png"
              alt="PullList mascot"
              width={60}
              height={60}
              className="object-contain"
              unoptimized
            />
          </div>
          <h2 className="text-lg font-bold text-text-primary">
            🇰🇷 Korean catalog — coming soon
          </h2>
          <p className="mt-2 text-sm text-text-secondary">
            We&apos;re sourcing Korean prints from{" "}
            <code className="font-mono text-xs bg-bg border border-border rounded px-1">
              pokemonkorea.co.kr
            </code>
            . Until that lands, browse Japanese (the master prints most Korean
            cards translate) or USA.
          </p>
          <div className="mt-5 flex justify-center gap-2">
            <Link
              href="/sets?region=ja"
              className="rounded-full bg-accent-yellow text-gray-900 font-bold px-4 py-2 text-sm hover:brightness-105 transition-all"
            >
              🇯🇵 Browse Japanese
            </Link>
            <Link
              href="/sets?region=en"
              className="rounded-full border border-border bg-bg-surface text-text-primary font-semibold px-4 py-2 text-sm hover:border-accent-yellow/60 transition-all"
            >
              🇺🇸 Browse English
            </Link>
          </div>
        </div>
      )}

      {!error && sets.length === 0 && region !== "ko" && (
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
