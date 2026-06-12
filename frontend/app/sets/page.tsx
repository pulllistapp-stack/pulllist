import Link from "next/link";

import { SetCard } from "@/components/SetCard";
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

  const bySeries = sets.reduce<Record<string, SetWithCardCount[]>>((acc, s) => {
    const key = s.series ?? "Other";
    (acc[key] ??= []).push(s);
    return acc;
  }, {});

  const orderedSeries = Object.keys(bySeries).sort((a, b) => {
    const aMax = Math.max(
      ...bySeries[a].map((s) => Date.parse(s.release_date ?? "1970-01-01")),
    );
    const bMax = Math.max(
      ...bySeries[b].map((s) => Date.parse(s.release_date ?? "1970-01-01")),
    );
    return bMax - aMax;
  });

  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <nav className="mb-8">
        <Link href="/" className="text-text-secondary hover:text-text-primary">
          ← Home
        </Link>
      </nav>

      <h1 className="text-3xl font-bold mb-2">Browse sets</h1>
      <p className="text-text-secondary mb-10">
        {sets.length} sets · {sets.reduce((n, s) => n + s.card_count, 0)} cards
        seeded
      </p>

      {error && (
        <div className="rounded-card bg-accent-red/10 border border-accent-red/30 p-4 text-sm">
          <div className="font-semibold mb-1">Could not reach API</div>
          <div className="text-text-secondary font-mono">{error}</div>
          <div className="text-text-secondary mt-2">
            Start the backend: <code>uvicorn app.main:app --reload</code>
          </div>
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

      {orderedSeries.map((series) => (
        <section key={series} className="mb-12">
          <h2 className="text-sm font-mono uppercase tracking-wider text-text-tertiary mb-4">
            {series}
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
            {bySeries[series]
              .sort(
                (a, b) =>
                  Date.parse(b.release_date ?? "1970-01-01") -
                  Date.parse(a.release_date ?? "1970-01-01"),
              )
              .map((s) => (
                <SetCard key={s.id} set={s} />
              ))}
          </div>
        </section>
      ))}
    </main>
  );
}
