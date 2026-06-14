import Link from "next/link";

import { SetsBrowser } from "@/components/SetsBrowser";
import { listSets, SetWithCardCount } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function SetsPage() {
  let sets: SetWithCardCount[] = [];
  let error: string | null = null;

  try {
    sets = await listSets();
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

      <div className="mb-8 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold mb-1">Expansion Sets</h1>
          <p className="text-text-secondary text-sm">
            {sets.length} sets · {totalCards} cards seeded · Explore every generation of the Pokémon TCG
          </p>
        </div>
      </div>

      {error && (
        <div className="rounded-card bg-accent-red/10 border border-accent-red/30 p-4 text-sm mb-6">
          <div className="font-semibold mb-1">Could not reach API</div>
          <div className="text-text-secondary font-mono">{error}</div>
        </div>
      )}

      {!error && sets.length === 0 && (
        <div className="rounded-card bg-bg-surface border border-border p-6 text-sm text-text-secondary">
          No sets yet. Seed the database:
          <pre className="mt-2 font-mono text-text-primary">
            python -m scripts.seed_sets --sets-only
          </pre>
        </div>
      )}

      {!error && sets.length > 0 && <SetsBrowser initialSets={sets} />}
    </main>
  );
}
