"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Share2 } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { AssetMixDonut, PALETTE } from "@/components/AssetMixDonut";
import { PortfolioGrowthChart } from "@/components/PortfolioGrowthChart";
import { ShareModal } from "@/components/portfolio/ShareModal";
import { PriceBadge } from "@/components/PriceBadge";
import { listSets, type SetWithCardCount } from "@/lib/api";
import {
  CollectionItemDetail,
  CollectionSummary,
  collectionSummary,
  getToken,
  listMyItems,
} from "@/lib/auth";

export default function PortfolioPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [summary, setSummary] = useState<CollectionSummary | null>(null);
  const [items, setItems] = useState<CollectionItemDetail[]>([]);
  const [sets, setSets] = useState<SetWithCardCount[]>([]);
  const [loading, setLoading] = useState(true);
  const [shareOpen, setShareOpen] = useState(false);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const [s, list, allSets] = await Promise.all([
          collectionSummary(),
          listMyItems(),
          listSets(getToken() ?? undefined),
        ]);
        if (cancelled) return;
        setSummary(s);
        setItems(list);
        setSets(allSets);
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

  // Build set_id -> series map for asset mix
  const seriesBySet = useMemo(() => {
    const map: Record<string, string> = {};
    for (const s of sets) map[s.id] = s.series ?? "Other";
    return map;
  }, [sets]);

  // Asset mix by series (sum of qty × market_price_usd)
  const assetMix = useMemo(() => {
    const acc: Record<string, number> = {};
    for (const it of items) {
      const series = seriesBySet[it.set_id] ?? "Other";
      const value = (it.market_price_usd ?? 0) * it.qty;
      acc[series] = (acc[series] ?? 0) + value;
    }
    const total = Object.values(acc).reduce((s, v) => s + v, 0);
    const entries = Object.entries(acc)
      .filter(([, v]) => v > 0)
      .sort((a, b) => b[1] - a[1]);
    return {
      total,
      slices: entries.map(([label, value], i) => ({
        label,
        value,
        color: PALETTE[i % PALETTE.length],
      })),
    };
  }, [items, seriesBySet]);

  // Master sets (100% complete)
  const masterSets = useMemo(() => {
    let count = 0;
    for (const s of sets) {
      if (s.card_count > 0 && (s.owned_unique ?? 0) >= s.card_count) count++;
    }
    return count;
  }, [sets]);

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

  const value = summary?.estimated_value_usd ?? 0;
  const cardsOwned = summary?.unique_cards ?? 0;
  const totalQty = summary?.total_qty ?? 0;
  const setsTouched = summary?.sets_touched ?? 0;

  return (
    <main className="mx-auto max-w-7xl px-6 py-10">
      <nav className="mb-6 text-sm text-text-secondary">
        <Link href="/" className="hover:text-text-primary">
          Home
        </Link>
        <span className="mx-2 text-text-tertiary">/</span>
        <span className="text-text-primary">Portfolio</span>
      </nav>

      <div className="mb-8 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold mb-1 tracking-tight">
            {user.name ?? user.email.split("@")[0]}&apos;s Portfolio
          </h1>
          <p className="text-text-secondary text-sm">
            Live valuation across {setsTouched} sets · {totalQty} cards
          </p>
        </div>
        <div className="shrink-0 flex flex-wrap gap-2">
          <button
            onClick={() => setShareOpen(true)}
            className="inline-flex items-center gap-2 rounded-full border border-border bg-bg-surface text-text-primary font-semibold px-4 py-2.5 text-sm hover:border-accent-yellow/40 hover:text-accent-yellow transition-colors"
          >
            <Share2 className="h-4 w-4" />
            Share
          </button>
          <Link
            href="/scan"
            className="inline-flex items-center gap-2 rounded-full bg-accent-yellow text-gray-900 font-bold px-5 py-2.5 text-sm hover:brightness-105 shadow-md shadow-accent-yellow/30 transition-all"
          >
            <span aria-hidden>📸</span>
            Scan a card
          </Link>
        </div>
      </div>

      {shareOpen && <ShareModal onClose={() => setShareOpen(false)} />}

      {/* Top row: Stats LEFT (compact), Vault grid teaser RIGHT (big — per LO preference) */}
      <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-6 mb-8">
        {/* Stats column */}
        <div className="flex flex-col gap-4">
          <div className="rounded-card bg-bg-surface border border-border p-5">
            <div className="text-xs font-mono uppercase tracking-wider text-text-tertiary">
              Total collection value
            </div>
            <div className="mt-2 font-mono text-3xl font-bold text-accent-green">
              ${value.toFixed(2)}
            </div>
            <div className="mt-1 text-xs text-text-tertiary">
              Based on current TCGplayer + eBay market prices
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <MiniStat label="Unique cards" value={cardsOwned.toLocaleString()} />
            <MiniStat label="Total copies" value={totalQty.toLocaleString()} />
            <MiniStat label="Sets touched" value={setsTouched.toLocaleString()} />
            <MiniStat label="Master sets" value={masterSets.toLocaleString()} highlight />
          </div>
        </div>

        {/* Big vault preview — top owned cards (highest value first) */}
        <div className="rounded-card bg-bg-surface border border-border p-5">
          <div className="flex items-baseline justify-between mb-4">
            <h2 className="text-sm font-mono uppercase tracking-wider text-text-tertiary">
              Top cards by value
            </h2>
            <span className="text-xs font-mono text-text-tertiary">
              {items.length} total
            </span>
          </div>

          {loading ? (
            <div className="text-text-tertiary text-sm">Loading…</div>
          ) : items.length === 0 ? (
            <div className="py-10 text-center">
              <p className="text-sm text-text-secondary mb-3">
                Your vault is empty. Tap{" "}
                <span className="text-accent-green">+ I have this</span> on any card to start.
              </p>
              <Link
                href="/sets"
                className="inline-block rounded-full bg-accent-yellow px-4 py-2 text-sm font-semibold text-gray-900 hover:brightness-110"
              >
                Browse sets
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-3">
              {[...items]
                .sort(
                  (a, b) =>
                    (b.market_price_usd ?? 0) - (a.market_price_usd ?? 0),
                )
                .slice(0, 12)
                .map((it) => (
                  <Link
                    key={it.id}
                    href={`/cards/${it.card_id}`}
                    className="group block"
                  >
                    <div className="relative aspect-[245/342] overflow-hidden rounded-md bg-bg border border-border group-hover:border-accent-yellow/40">
                      {it.image_small && (
                        <Image
                          src={it.image_small}
                          alt={it.card_name}
                          fill
                          sizes="100px"
                          className="object-contain group-hover:scale-[1.03] transition-transform"
                          unoptimized
                        />
                      )}
                    </div>
                    <div className="mt-1.5 flex items-center justify-between text-xs">
                      <span className="font-mono text-text-tertiary truncate">
                        #{it.card_number ?? "—"}
                      </span>
                      <span className="font-mono font-bold text-accent-yellow">
                        {it.market_price_usd != null
                          ? `$${it.market_price_usd.toFixed(2)}`
                          : "—"}
                      </span>
                    </div>
                  </Link>
                ))}
            </div>
          )}
        </div>
      </div>

      {/* Second row: Growth chart (left, real data), Asset Mix donut (right) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-12">
        <PortfolioGrowthChart />

        <div className="rounded-card bg-bg-surface border border-border p-5">
          <h2 className="mb-4 text-sm font-mono uppercase tracking-wider text-text-tertiary">
            Asset mix
          </h2>
          <AssetMixDonut slices={assetMix.slices} total={assetMix.total} />
        </div>
      </div>

      {/* Full vault grouped by set */}
      <section>
        <h2 className="mb-4 text-lg font-bold">Vault by set</h2>
        {loading ? (
          <div className="text-text-tertiary">Loading your collection…</div>
        ) : items.length === 0 ? null : (
          setOrder.map((setId) => {
            const setItems = bySet[setId];
            const setName = setItems[0].set_name;
            return (
              <div key={setId} className="mb-10">
                <div className="flex items-baseline justify-between mb-3">
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
                          className="absolute top-1 right-1 z-10 inline-flex items-center justify-center min-w-5 h-5 px-1 rounded-full bg-accent-yellow text-gray-900 text-xs font-bold font-mono"
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
              </div>
            );
          })
        )}
      </section>
    </main>
  );
}

function MiniStat({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className="rounded-card bg-bg-surface border border-border p-3">
      <div className="text-[10px] font-mono uppercase tracking-wider text-text-tertiary mb-1">
        {label}
      </div>
      <div
        className={`text-xl font-bold font-mono ${
          highlight ? "text-accent-yellow" : "text-text-primary"
        }`}
      >
        {value}
      </div>
    </div>
  );
}
