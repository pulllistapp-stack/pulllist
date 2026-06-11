"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { PriceBadge } from "@/components/PriceBadge";
import {
  CollectionItemDetail,
  CollectionSummary,
  collectionSummary,
  listMyItems,
} from "@/lib/auth";

export default function MyCollectionPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [summary, setSummary] = useState<CollectionSummary | null>(null);
  const [items, setItems] = useState<CollectionItemDetail[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const [s, list] = await Promise.all([
          collectionSummary(),
          listMyItems(),
        ]);
        if (cancelled) return;
        setSummary(s);
        setItems(list);
      } catch {
        // non-fatal
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authLoading, user, router]);

  if (authLoading || !user) {
    return (
      <main className="mx-auto max-w-7xl px-6 py-16 text-text-secondary">
        Loading…
      </main>
    );
  }

  const bySet = items.reduce<Record<string, CollectionItemDetail[]>>(
    (acc, item) => {
      (acc[item.set_id] ??= []).push(item);
      return acc;
    },
    {},
  );
  const setOrder = Object.keys(bySet).sort((a, b) =>
    (bySet[a][0].set_name ?? "").localeCompare(bySet[b][0].set_name ?? ""),
  );

  return (
    <main className="mx-auto max-w-7xl px-6 py-12">
      <nav className="mb-6 text-sm text-text-secondary">
        <Link href="/" className="hover:text-text-primary">
          Home
        </Link>
        <span className="mx-2 text-text-tertiary">/</span>
        <span className="text-text-primary">My Collection</span>
      </nav>

      <h1 className="text-3xl font-bold mb-2 tracking-tight">
        {user.name ?? user.email.split("@")[0]}&apos;s Collection
      </h1>

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12">
          <StatCard
            label="Unique cards"
            value={summary.unique_cards.toLocaleString()}
          />
          <StatCard
            label="Total qty"
            value={summary.total_qty.toLocaleString()}
          />
          <StatCard
            label="Sets touched"
            value={summary.sets_touched.toLocaleString()}
          />
          <StatCard
            label="Est. value"
            value={`$${summary.estimated_value_usd.toFixed(2)}`}
            highlight
          />
        </div>
      )}

      {loading ? (
        <div className="text-text-tertiary">Loading your collection…</div>
      ) : items.length === 0 ? (
        <div className="rounded-card border border-border bg-bg-surface p-8 text-center">
          <h2 className="text-lg font-semibold mb-2">Your collection is empty</h2>
          <p className="text-sm text-text-secondary mb-4">
            Browse the catalog and tap{" "}
            <span className="text-accent-green">+ I have this</span> on cards you
            own.
          </p>
          <Link
            href="/sets"
            className="inline-block rounded-btn bg-accent-yellow text-bg font-medium px-4 py-2 hover:brightness-110"
          >
            Browse sets
          </Link>
        </div>
      ) : (
        setOrder.map((setId) => {
          const setItems = bySet[setId];
          const setName = setItems[0].set_name;
          return (
            <section key={setId} className="mb-12">
              <div className="flex items-baseline justify-between mb-4">
                <Link
                  href={`/sets/${setId}`}
                  className="text-sm font-mono uppercase tracking-wider text-text-tertiary hover:text-text-primary"
                >
                  {setName}{" "}
                  <span className="text-text-tertiary">
                    · {setItems.length} owned
                  </span>
                </Link>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
                {setItems.map((item) => (
                  <Link
                    key={item.id}
                    href={`/cards/${item.card_id}`}
                    className="group relative flex flex-col rounded-card bg-bg-surface border border-border p-2 hover:border-accent-yellow/40 transition-colors"
                  >
                    {item.qty > 1 && (
                      <span
                        className="absolute top-1 right-1 z-10 inline-flex items-center justify-center min-w-5 h-5 px-1 rounded-full bg-accent-yellow text-bg text-xs font-bold font-mono"
                        title={`${item.qty} copies`}
                      >
                        ×{item.qty}
                      </span>
                    )}

                    <div className="relative aspect-[245/342] w-full overflow-hidden rounded-md bg-bg">
                      {item.image_small ? (
                        <Image
                          src={item.image_small}
                          alt={item.card_name}
                          fill
                          sizes="(max-width: 768px) 33vw, 200px"
                          className="object-contain group-hover:scale-[1.02] transition-transform"
                          unoptimized
                        />
                      ) : null}
                    </div>

                    <div className="mt-2 px-1 flex flex-col gap-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-mono text-text-tertiary">
                          #{item.card_number ?? "—"}
                        </span>
                        <PriceBadge price={item.market_price_usd} />
                      </div>
                      <div
                        className="text-sm font-medium truncate"
                        title={item.card_name}
                      >
                        {item.card_name}
                      </div>
                      <div className="flex items-center gap-2 text-xs text-text-tertiary font-mono">
                        <span>{item.condition}</span>
                        {item.is_graded && item.grade && (
                          <>
                            <span>·</span>
                            <span className="text-accent-yellow">
                              {item.grade}
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          );
        })
      )}
    </main>
  );
}

function StatCard({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className="rounded-card bg-bg-surface border border-border p-4">
      <div className="text-xs font-mono uppercase tracking-wider text-text-tertiary mb-2">
        {label}
      </div>
      <div
        className={`text-2xl font-bold font-mono ${
          highlight ? "text-accent-green" : "text-text-primary"
        }`}
      >
        {value}
      </div>
    </div>
  );
}
