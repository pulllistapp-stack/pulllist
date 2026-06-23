"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { CheckSquare, Download, Loader2, MoreVertical, Share2, Square, Trash2, X } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { AssetMixDonut, PALETTE } from "@/components/AssetMixDonut";
import { MascotLoader } from "@/components/MascotLoader";
import { PortfolioGrowthChart } from "@/components/PortfolioGrowthChart";
import { CollectionItemEditModal } from "@/components/portfolio/CollectionItemEditModal";
import { ShareModal } from "@/components/portfolio/ShareModal";
import { PriceBadge } from "@/components/PriceBadge";
import { VariantChip } from "@/components/VariantChip";
import {
  downloadCollectionCsv,
  listSets,
  type SetWithCardCount,
} from "@/lib/api";
import {
  bulkDeleteCollectionItems,
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
  const [exporting, setExporting] = useState(false);

  // Manage mode: a tap on a vault card toggles its checkbox instead of
  // navigating, and a sticky action bar surfaces bulk delete. Same-card-
  // different-variant entries (the Professor Elm bug LO hit) can be cleaned
  // up here without round-tripping through each card's detail page.
  const [manageMode, setManageMode] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);

  // Per-row edit modal — click the ⋯ overlay on a vault card to surface
  // notes / purchase price / acquired date / source that the add-modal
  // captured; lets users edit or delete that one row in place.
  const [editingItem, setEditingItem] = useState<CollectionItemDetail | null>(
    null,
  );

  const exitManageMode = useCallback(() => {
    setManageMode(false);
    setSelected(new Set());
    setConfirmOpen(false);
    setConfirmText("");
  }, []);

  const toggleSelected = useCallback((itemId: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) next.delete(itemId);
      else next.add(itemId);
      return next;
    });
  }, []);

  const selectAllVisible = useCallback(() => {
    setSelected((prev) =>
      prev.size === items.length ? new Set() : new Set(items.map((it) => it.id)),
    );
  }, [items]);

  const handleBulkDelete = useCallback(async () => {
    if (selected.size === 0) return;
    // Multi-item deletes require typing "delete" — a single accidental
    // tap shouldn't be able to wipe 50 cards from someone's collection.
    if (selected.size >= 2 && confirmText.trim().toLowerCase() !== "delete") {
      return;
    }
    const ids = Array.from(selected);
    setDeleting(true);
    try {
      await bulkDeleteCollectionItems(ids);
      // Optimistic: drop the rows + refresh summary in the background.
      setItems((prev) => prev.filter((it) => !selected.has(it.id)));
      void collectionSummary().then(setSummary).catch(() => {});
      exitManageMode();
    } catch (err) {
      console.error(err);
      alert(
        `Couldn't delete: ${err instanceof Error ? err.message : String(err)}`,
      );
    } finally {
      setDeleting(false);
    }
  }, [selected, confirmText, exitManageMode]);

  const handleExport = async () => {
    const tok = getToken();
    if (!tok || exporting) return;
    setExporting(true);
    try {
      await downloadCollectionCsv(tok);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error(err);
      alert(`Export failed.\n\n${msg}`);
    } finally {
      setExporting(false);
    }
  };

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
          listSets({ token: getToken() ?? undefined }),
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
      <main className="mx-auto max-w-7xl px-6 py-16">
        <MascotLoader size="lg" />
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
            type="button"
            onClick={() => (manageMode ? exitManageMode() : setManageMode(true))}
            disabled={items.length === 0}
            className={
              "inline-flex items-center gap-2 rounded-full border font-semibold px-4 py-2.5 text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed " +
              (manageMode
                ? "border-accent-red/60 bg-accent-red/10 text-accent-red hover:bg-accent-red/15"
                : "border-border bg-bg-surface text-text-primary hover:border-accent-yellow/40 hover:text-accent-yellow")
            }
            title={
              items.length === 0
                ? "Add cards before managing"
                : manageMode
                  ? "Exit manage mode"
                  : "Select cards to delete"
            }
          >
            {manageMode ? <X className="h-4 w-4" /> : <CheckSquare className="h-4 w-4" />}
            {manageMode ? "Cancel" : "Manage"}
          </button>
          <button
            type="button"
            onClick={handleExport}
            disabled={exporting || items.length === 0 || manageMode}
            className="inline-flex items-center gap-2 rounded-full border border-border bg-bg-surface text-text-primary font-semibold px-4 py-2.5 text-sm hover:border-accent-yellow/40 hover:text-accent-yellow transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title={items.length === 0 ? "Add cards to enable export" : "Download your collection as CSV"}
          >
            {exporting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Download className="h-4 w-4" />
            )}
            {exporting ? "Exporting…" : "Export CSV"}
          </button>
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

      {editingItem && (
        <CollectionItemEditModal
          item={editingItem}
          onClose={() => setEditingItem(null)}
          onSaved={async () => {
            try {
              const [s, list] = await Promise.all([
                collectionSummary(),
                listMyItems(),
              ]);
              setSummary(s);
              setItems(list);
            } catch {
              // non-fatal — modal already closed
            }
          }}
          onDeleted={async () => {
            try {
              const [s, list] = await Promise.all([
                collectionSummary(),
                listMyItems(),
              ]);
              setSummary(s);
              setItems(list);
            } catch {
              // non-fatal
            }
          }}
        />
      )}

      {/* Top row: stats column left (compact), vault grid right (large). */}
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
              Top 10 cards by value
            </h2>
            <span className="text-xs font-mono text-text-tertiary">
              {Math.min(items.length, 10)} of {items.length}
            </span>
          </div>

          {loading ? (
            <MascotLoader size="md" className="py-6" />
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
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
              {[...items]
                .sort(
                  (a, b) =>
                    (b.market_price_usd ?? 0) - (a.market_price_usd ?? 0),
                )
                .slice(0, 10)
                .map((it, i) => (
                  <Link
                    key={it.id}
                    href={`/cards/${it.card_id}`}
                    className="group block"
                  >
                    <div className="relative aspect-[245/342] overflow-hidden rounded-md bg-bg border border-border group-hover:border-accent-yellow/40">
                      {/* Rank badge — makes the "Top 10" ordering explicit
                          so the row is read as a leaderboard, not a sample. */}
                      <span className="absolute top-1 left-1 z-10 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-gray-900/80 dark:bg-zinc-900/80 px-1.5 text-[10px] font-bold text-white backdrop-blur">
                        #{i + 1}
                      </span>
                      {it.image_small && (
                        <Image
                          src={it.image_small}
                          alt={it.card_name}
                          fill
                          sizes="120px"
                          className="object-contain group-hover:scale-[1.03] transition-transform"
                          unoptimized
                        />
                      )}
                    </div>
                    <div className="mt-1.5 flex items-center justify-between text-xs">
                      <span className="font-mono text-text-tertiary truncate">
                        {it.card_number ? `№${it.card_number}` : "—"}
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
                  {setItems.map((item) => {
                    const isSelected = selected.has(item.id);
                    const cardCls =
                      "group relative flex flex-col rounded-card border p-2 transition-colors text-left " +
                      (manageMode
                        ? isSelected
                          ? "cursor-pointer bg-accent-red/5 border-accent-red/70 ring-2 ring-accent-red/30"
                          : "cursor-pointer bg-bg-surface border-border hover:border-accent-red/40"
                        : "bg-bg-surface border-border hover:border-accent-yellow/40");

                    const inner = (
                      <>
                        {manageMode && (
                          <span
                            className={
                              "absolute top-1 left-1 z-10 inline-flex h-6 w-6 items-center justify-center rounded-md backdrop-blur shadow-sm " +
                              (isSelected
                                ? "bg-accent-red text-white"
                                : "bg-bg/90 text-text-secondary border border-border")
                            }
                            aria-hidden
                          >
                            {isSelected ? (
                              <CheckSquare className="h-4 w-4" />
                            ) : (
                              <Square className="h-4 w-4" />
                            )}
                          </span>
                        )}

                        {!manageMode && item.qty > 1 && (
                          <span
                            className="absolute top-1 right-1 z-10 inline-flex items-center justify-center min-w-5 h-5 px-1 rounded-full bg-accent-yellow text-gray-900 text-xs font-bold font-mono"
                            title={`${item.qty} copies`}
                          >
                            ×{item.qty}
                          </span>
                        )}

                        {!manageMode && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              setEditingItem(item);
                            }}
                            className="absolute top-1 left-1 z-10 inline-flex h-6 w-6 items-center justify-center rounded-md bg-bg/80 backdrop-blur border border-border text-text-secondary opacity-70 md:opacity-0 md:group-hover:opacity-100 focus:opacity-100 hover:text-text-primary hover:bg-bg-elevated transition-opacity"
                            aria-label={`Edit ${item.card_name}`}
                            title="Edit row details"
                          >
                            <MoreVertical className="h-3.5 w-3.5" />
                          </button>
                        )}

                        <div className="relative aspect-[245/342] w-full overflow-hidden rounded-md bg-bg">
                          {item.image_small ? (
                            <Image
                              src={item.image_small}
                              alt={item.card_name}
                              fill
                              sizes="(max-width: 768px) 33vw, 200px"
                              className={
                                "object-contain transition-transform " +
                                (manageMode ? "" : "group-hover:scale-[1.02]")
                              }
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
                            <VariantChip variant={item.variant} />
                          </div>
                        </div>
                      </>
                    );

                    return manageMode ? (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => toggleSelected(item.id)}
                        aria-pressed={isSelected}
                        className={cardCls}
                      >
                        {inner}
                      </button>
                    ) : (
                      <Link
                        key={item.id}
                        href={`/cards/${item.card_id}`}
                        className={cardCls}
                      >
                        {inner}
                      </Link>
                    );
                  })}
                </div>
              </div>
            );
          })
        )}
      </section>

      {manageMode && (
        <div
          className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-bg-surface/95 backdrop-blur-md shadow-[0_-8px_24px_-12px_rgba(0,0,0,0.25)]"
          role="region"
          aria-label="Manage mode actions"
        >
          <div className="mx-auto max-w-7xl px-4 py-3 flex flex-wrap items-center gap-3">
            <span className="text-sm font-mono text-text-secondary">
              <span className="text-text-primary font-bold">
                {selected.size}
              </span>{" "}
              of {items.length} selected
            </span>
            <button
              type="button"
              onClick={selectAllVisible}
              className="rounded-full border border-border bg-bg px-3 py-1.5 text-xs font-semibold text-text-secondary hover:text-text-primary hover:border-accent-yellow/40"
            >
              {selected.size === items.length ? "Clear all" : "Select all"}
            </button>
            <div className="flex-1" />
            <button
              type="button"
              onClick={exitManageMode}
              className="rounded-full border border-border bg-bg px-3 py-1.5 text-xs font-semibold text-text-secondary hover:text-text-primary"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => {
                setConfirmText("");
                setConfirmOpen(true);
              }}
              disabled={selected.size === 0}
              className="inline-flex items-center gap-1.5 rounded-full bg-accent-red text-white font-bold px-4 py-1.5 text-xs hover:brightness-105 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete {selected.size > 0 ? `(${selected.size})` : ""}
            </button>
          </div>
        </div>
      )}

      {confirmOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-full max-w-md rounded-card border border-border bg-bg-surface p-6 shadow-2xl">
            <h3 className="text-lg font-bold text-text-primary mb-1">
              {selected.size === 1
                ? "Remove this card?"
                : `Remove ${selected.size} cards?`}
            </h3>
            <p className="text-sm text-text-secondary mb-4">
              {selected.size === 1
                ? "It'll come right back if you add it again later."
                : "This can't be undone. Type DELETE below to confirm."}
            </p>

            {selected.size >= 2 && (
              <input
                type="text"
                value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
                placeholder="Type DELETE"
                autoFocus
                className="w-full rounded-btn border border-border bg-bg px-3 py-2 text-sm font-mono uppercase tracking-wider text-text-primary focus:border-accent-red focus:outline-none mb-4"
                aria-label="Type DELETE to confirm"
              />
            )}

            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setConfirmOpen(false);
                  setConfirmText("");
                }}
                disabled={deleting}
                className="rounded-btn border border-border bg-bg px-4 py-2 text-sm font-semibold text-text-secondary hover:text-text-primary disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleBulkDelete}
                disabled={
                  deleting ||
                  (selected.size >= 2 &&
                    confirmText.trim().toLowerCase() !== "delete")
                }
                className="inline-flex items-center gap-2 rounded-btn bg-accent-red text-white font-bold px-4 py-2 text-sm hover:brightness-105 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {deleting && <Loader2 className="h-4 w-4 animate-spin" />}
                {deleting ? "Deleting…" : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
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
