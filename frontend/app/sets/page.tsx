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

      {!error && sets.length > 0 && <SetsBrowser sets={sets} />}

      {/* Complete your Pokedex CTA */}
      <section className="mt-16 rounded-card border-2 border-dashed border-accent-yellow/30 bg-accent-yellow/5 p-8 text-center">
        <div className="mx-auto mb-3 inline-flex h-12 w-12 items-center justify-center rounded-full bg-accent-yellow/15">
          <span className="text-2xl">📖</span>
        </div>
        <h2 className="text-lg font-bold mb-1">Complete your Pokédex!</h2>
        <p className="mx-auto max-w-md text-sm text-text-secondary">
          Connect your collection to see automatic completion tracking for every set. Our scout
          even suggests the cheapest way to finish your binder.
        </p>
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          <Link
            href="/signup"
            className="rounded-full bg-accent-yellow px-5 py-2 text-sm font-semibold text-gray-900 hover:brightness-110"
          >
            Start tracking — free
          </Link>
          <Link
            href="/cards"
            className="rounded-full border border-border bg-bg-surface px-5 py-2 text-sm font-semibold text-text-secondary hover:text-text-primary hover:border-accent-yellow/40"
          >
            Browse master sets
          </Link>
        </div>
      </section>
    </main>
  );
}
