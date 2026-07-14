import Link from "next/link";

import { listSeries } from "@/lib/api";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Series · PullList",
  description:
    "Browse Pokémon TCG sets grouped by series — Scarlet & Violet, Sword & Shield, Sun & Moon, and every earlier era.",
};

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso + "T00:00:00Z").toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
  });
}

export default async function SeriesIndexPage() {
  const { items } = await listSeries();

  return (
    <main className="mx-auto max-w-[100rem] px-4 py-8">
      <header className="mb-8">
        <h1 className="text-3xl font-extrabold tracking-tight">Series</h1>
        <p className="mt-2 max-w-3xl text-sm text-text-secondary">
          Every Pokémon TCG era, from Base Set to the current Scarlet &amp;
          Violet cycle. Each series page collects all its sets and sealed
          products on one screen.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((s) => (
          <Link
            key={s.slug}
            href={`/series/${s.slug}`}
            className="group rounded-card border border-border bg-bg-surface p-5 transition-colors hover:border-accent-yellow/40"
          >
            <div className="text-[10px] font-mono uppercase tracking-widest text-text-tertiary">
              Series
            </div>
            <div className="mt-1 text-xl font-bold text-text-primary group-hover:text-accent-yellow">
              {s.series}
            </div>
            <div className="mt-3 flex flex-wrap gap-4 text-xs">
              <SmallStat label="Sets" value={s.set_count} />
              <SmallStat label="Cards" value={s.card_count} />
              <SmallStat label="Sealed" value={s.product_count} />
            </div>
            <div className="mt-2 text-[11px] text-text-tertiary">
              Latest release · {fmtDate(s.latest_release)}
            </div>
          </Link>
        ))}
      </div>
    </main>
  );
}

function SmallStat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="text-lg font-extrabold text-text-primary">
        {value.toLocaleString()}
      </div>
      <div className="text-[9px] font-mono uppercase tracking-wider text-text-tertiary">
        {label}
      </div>
    </div>
  );
}
