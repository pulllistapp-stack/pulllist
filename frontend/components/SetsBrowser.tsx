"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import type { CatalogRegion, SetSubtype, SetType, SetWithCardCount } from "@/lib/api";
import { listSets } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { seriesLabel } from "@/lib/series";

import { useAuth } from "./AuthProvider";
import { SetCard } from "./SetCard";

type Props = {
  initialSets: SetWithCardCount[];
  region?: CatalogRegion;
};

// 5-year super-buckets for PROMO_NEW sets. Keyed by the bucket label
// the user sees; each bucket collects any promo set whose year falls
// inside its window. Ordered oldest→newest so buckets stack in time.
const PROMO_NEW_BUCKETS: { label: string; years: [number, number] }[] = [
  { label: "1996–2005", years: [1996, 2005] },
  { label: "2006–2010", years: [2006, 2010] },
  { label: "2011–2015", years: [2011, 2015] },
  { label: "2016–2020", years: [2016, 2020] },
  { label: "2021–2025", years: [2021, 2025] },
  { label: "2026–2030", years: [2026, 2030] },
];

function promoSetYear(set: SetWithCardCount): number | null {
  // JP promos encode the year in the set id (`JPP-U2016`, `JPP-U1996`,
  // ...). Everything else — KR `ko-p-{era}`, future CN/TW promo buckets
  // — falls back to release_date. Release_date is a plain ISO date
  // string in the API payload, so slicing the first 4 chars is enough.
  const m = set.id.match(/^JPP-U(\d{4})/);
  if (m) return Number(m[1]);
  if (set.release_date) {
    const y = Number(set.release_date.slice(0, 4));
    if (!Number.isNaN(y)) return y;
  }
  return null;
}

function bucketFor(set: SetWithCardCount) {
  const y = promoSetYear(set);
  if (y == null) return null;
  return PROMO_NEW_BUCKETS.find(
    (b) => y >= b.years[0] && y <= b.years[1],
  );
}

export function SetsBrowser({ initialSets, region = "en" }: Props) {
  const { user, loading } = useAuth();
  const [sets, setSets] = useState<SetWithCardCount[]>(initialSets);
  const [activeSeries, setActiveSeries] = useState<string | null>(null);

  useEffect(() => {
    setSets(initialSets);
  }, [initialSets]);

  useEffect(() => {
    if (loading || !user) return;
    const token = getToken();
    if (!token) return;
    let cancelled = false;
    listSets({ token, region })
      .then((fresh) => {
        if (!cancelled) setSets(fresh);
      })
      .catch(() => {
        /* silent */
      });
    return () => {
      cancelled = true;
    };
  }, [user, loading, region]);

  // Segregate by set_type. STUB is filtered out (backend already does
  // this for the no-logo no-cards intersection; also drop any that slipped
  // through). PROMO_NEW gets its own bucketed rendering path; DECK slides
  // to the bottom. Sets with set_type=null (all EN/KR right now) fall
  // through to the MAIN branch — the current behaviour.
  const {
    mainSets,
    promoNew,
    promoNewByBucket,
    deckSets,
  } = useMemo(() => {
    const main: SetWithCardCount[] = [];
    const promoLegacy: SetWithCardCount[] = [];
    const promoNewSets: SetWithCardCount[] = [];
    const deck: SetWithCardCount[] = [];
    for (const s of sets) {
      const t = (s.set_type ?? "MAIN") as SetType;
      if (t === "STUB") continue;
      if (t === "DECK") {
        deck.push(s);
      } else if (t === "PROMO_NEW") {
        promoNewSets.push(s);
      } else if (t === "PROMO_LEGACY") {
        promoLegacy.push(s);
      } else {
        main.push(s);
      }
    }
    // PROMO_LEGACY is already grouped under a "Promos" series card in
    // the current UI — keep it flowing through the MAIN grid so nothing
    // moves in the JP-catalog visual for existing users.
    const combinedMain = [...main, ...promoLegacy];

    // Bucket PROMO_NEW by 5-year window. Order: oldest → newest.
    const bucketMap = new Map<string, SetWithCardCount[]>();
    for (const b of PROMO_NEW_BUCKETS) bucketMap.set(b.label, []);
    for (const s of promoNewSets) {
      const b = bucketFor(s);
      if (b) bucketMap.get(b.label)!.push(s);
    }
    // Sort inside each bucket by year ascending. Uses the same
    // JPP-U-first-then-release_date derivation as the bucket picker.
    for (const [, arr] of bucketMap) {
      arr.sort((a, b) => (promoSetYear(a) ?? 0) - (promoSetYear(b) ?? 0));
    }

    // Sort DECK alphabetically by name for stable grid order
    deck.sort((a, b) => a.name.localeCompare(b.name));

    return {
      mainSets: combinedMain,
      promoNew: promoNewSets,
      promoNewByBucket: bucketMap,
      deckSets: deck,
    };
  }, [sets]);

  // Series chips list ALL visible sets regardless of set_type. The
  // categorization (MAIN/PROMO_NEW/DECK) affects which SECTION a set
  // renders in, but the series filter itself is orthogonal — clicking
  // "Sword & Shield" should slice across every section that has SwSh
  // sets, including decks at the bottom.
  const visibleSets = useMemo(
    () => [...mainSets, ...promoNew, ...deckSets],
    [mainSets, promoNew, deckSets],
  );

  const seriesList = useMemo(() => {
    const groups: Record<string, number> = {};
    for (const s of visibleSets) {
      const key = s.series ?? "Other";
      const date = Date.parse(s.release_date ?? "1970-01-01");
      groups[key] = Math.max(groups[key] ?? 0, date);
    }
    return Object.entries(groups)
      .sort((a, b) => b[1] - a[1])
      .map(([name]) => name);
  }, [visibleSets]);

  // When a series is active, every section (main / promo_new / deck)
  // narrows to just that series.
  const filteredMain = activeSeries
    ? mainSets.filter((s) => (s.series ?? "Other") === activeSeries)
    : mainSets;
  const filteredPromoNew = activeSeries
    ? promoNew.filter((s) => (s.series ?? "Other") === activeSeries)
    : promoNew;
  const filteredDeck = activeSeries
    ? deckSets.filter((s) => (s.series ?? "Other") === activeSeries)
    : deckSets;

  const groupedMain = useMemo(() => {
    const by: Record<string, SetWithCardCount[]> = {};
    for (const s of filteredMain) {
      const key = s.series ?? "Other";
      (by[key] ??= []).push(s);
    }
    for (const k of Object.keys(by)) {
      by[k].sort(
        (a, b) =>
          Date.parse(b.release_date ?? "1970-01-01") -
          Date.parse(a.release_date ?? "1970-01-01"),
      );
    }
    return by;
  }, [filteredMain]);

  const orderedSeries = useMemo(() => {
    return Object.keys(groupedMain).sort((a, b) => {
      const aMax = Math.max(
        ...groupedMain[a].map((s) =>
          Date.parse(s.release_date ?? "1970-01-01"),
        ),
      );
      const bMax = Math.max(
        ...groupedMain[b].map((s) =>
          Date.parse(s.release_date ?? "1970-01-01"),
        ),
      );
      return bMax - aMax;
    });
  }, [groupedMain]);

  const hasAnyOwned = useMemo(
    () => sets.some((s) => (s.owned_unique ?? 0) > 0),
    [sets],
  );

  // Always render every section — even under a series filter — since a
  // series can span multiple set_type buckets. Each section renders its
  // own filtered slice and hides itself if the slice is empty.

  return (
    <>
      {/* Series filter chips */}
      <div className="mb-8 flex flex-wrap gap-2">
        <button
          onClick={() => setActiveSeries(null)}
          className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors ${
            activeSeries === null
              ? "bg-accent-yellow text-gray-900 border-accent-yellow"
              : "bg-bg-surface border-border text-text-secondary hover:text-text-primary hover:border-accent-yellow/40"
          }`}
        >
          All series ({visibleSets.length})
        </button>
        {seriesList.map((series) => {
          const count = visibleSets.filter(
            (s) => (s.series ?? "Other") === series,
          ).length;
          return (
            <button
              key={series}
              onClick={() => setActiveSeries(series)}
              className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors ${
                activeSeries === series
                  ? "bg-accent-yellow text-gray-900 border-accent-yellow"
                  : "bg-bg-surface border-border text-text-secondary hover:text-text-primary hover:border-accent-yellow/40"
              }`}
            >
              {seriesLabel(series)}{" "}
              <span className="opacity-60">({count})</span>
            </button>
          );
        })}
      </div>

      {/* MAIN grid (grouped by series) */}
      {orderedSeries.map((series) => (
        <section key={series} className="mb-12">
          {activeSeries === null && (
            <h2 className="text-sm font-mono uppercase tracking-wider text-text-tertiary mb-4">
              {seriesLabel(series)}
            </h2>
          )}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {groupedMain[series].map((s) => (
              <SetCard key={s.id} set={s} />
            ))}
          </div>
        </section>
      ))}

      {/* PROMO_NEW — 5-year bucket sections. JP promos slot in by their
          JPP-U{year} id; KR (`ko-p-*`) and any future promo-catalog sets
          slot in by release_date year. Renders one sub-section per
          bucket window that has any sets after the series filter. */}
      {filteredPromoNew.length > 0 && (
        <section className="mb-12">
          <h2 className="text-sm font-mono uppercase tracking-wider text-text-tertiary mb-4">
            {region === "ja" ? "新プロモカード (5年ごと)" : "New Promos (5-year buckets)"}
          </h2>
          <div className="space-y-8">
            {PROMO_NEW_BUCKETS.map((b) => {
              const inBucket = filteredPromoNew.filter((s) => {
                const y = promoSetYear(s);
                return y != null && y >= b.years[0] && y <= b.years[1];
              });
              if (inBucket.length === 0) return null;
              return (
                <div key={b.label}>
                  <h3 className="text-xs font-mono uppercase tracking-wider text-text-secondary mb-3">
                    {b.label}{" "}
                    <span className="opacity-60">
                      ({inBucket.length} sets)
                    </span>
                  </h3>
                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                    {inBucket.map((s) => (
                      <SetCard key={s.id} set={s} />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* DECK — bottom section. Starter sets, preconstructed decks,
          trainer boxes and build boxes all live here so the main grid
          isn't diluted. */}
      {filteredDeck.length > 0 && (
        <section className="mb-12 mt-16 pt-8 border-t border-border">
          <h2 className="text-sm font-mono uppercase tracking-wider text-text-tertiary mb-1">
            {region === "ja" ? "デッキ商品" : "Deck Products"}
          </h2>
          <p className="text-xs text-text-tertiary mb-4">
            Starter sets, preconstructed decks, trainer boxes, build boxes
            — sorted alphabetically. {filteredDeck.length} products.
          </p>
          <div className="space-y-8">
            {(["STARTER", "DECK", "BOX", "SPECIAL"] as SetSubtype[]).map(
              (sub) => {
                const inSub = filteredDeck.filter(
                  (s) => (s.set_subtype ?? "DECK") === sub,
                );
                if (inSub.length === 0) return null;
                const label =
                  region === "ja"
                    ? { STARTER: "スターター", DECK: "デッキ", BOX: "ボックス", SPECIAL: "スペシャル" }[sub]
                    : { STARTER: "Starter", DECK: "Deck", BOX: "Box", SPECIAL: "Special" }[sub];
                return (
                  <div key={sub}>
                    <h3 className="text-xs font-mono uppercase tracking-wider text-text-secondary mb-3">
                      {label}{" "}
                      <span className="opacity-60">({inSub.length})</span>
                    </h3>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                      {inSub.map((s) => (
                        <SetCard key={s.id} set={s} />
                      ))}
                    </div>
                  </div>
                );
              },
            )}
          </div>
        </section>
      )}

      {/* Pokédex CTA — auth-aware */}
      {!hasAnyOwned && (
        <section className="mt-16 rounded-card border-2 border-dashed border-accent-yellow/30 bg-accent-yellow/5 p-8 text-center">
          <div className="mx-auto mb-3 inline-flex h-12 w-12 items-center justify-center rounded-full bg-accent-yellow/15">
            <span className="text-2xl">📖</span>
          </div>
          <h2 className="text-lg font-bold mb-1">Complete your Pokédex!</h2>
          <p className="mx-auto max-w-md text-sm text-text-secondary">
            {user
              ? "Mark cards you own from any set page and watch your completion bars fill in."
              : "Connect your collection to see automatic completion tracking for every set. Our scout even suggests the cheapest way to finish your binder."}
          </p>
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            {user ? (
              <Link
                href="/cards"
                className="rounded-full bg-accent-yellow px-5 py-2 text-sm font-semibold text-gray-900 hover:brightness-110"
              >
                Browse cards to add
              </Link>
            ) : (
              <Link
                href="/signup"
                className="rounded-full bg-accent-yellow px-5 py-2 text-sm font-semibold text-gray-900 hover:brightness-110"
              >
                Start tracking — free
              </Link>
            )}
            <Link
              href="/cards"
              className="rounded-full border border-border bg-bg-surface px-5 py-2 text-sm font-semibold text-text-secondary hover:text-text-primary hover:border-accent-yellow/40"
            >
              Browse master sets
            </Link>
          </div>
        </section>
      )}
    </>
  );
}
