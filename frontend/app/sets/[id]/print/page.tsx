"use client";

/**
 * Print Checklist — printable binder-placeholder sheets for a set.
 *
 * Physical binder collectors slot ordered pages of Pokémon cards into
 * 9-pocket / 16-pocket / 25-pocket sleeves. When cards are missing,
 * seeing an empty pocket makes it hard to remember which card belongs
 * there. This page renders a grayscale grid of every card in the set
 * (or optionally only unowned cards for signed-in users) with card
 * name + number below each thumbnail — cut them out and drop them
 * into the empty pocket so the "still-need" list is visible at a
 * glance.
 *
 * Visually the page leans into PullList's own idiom (yellow accent,
 * pill controls, mascot decoration, live preview strip, missing-cards
 * progress bar). @media print scoping hides the site chrome + our
 * settings panel so the printer only sees the sheets.
 */

import Image from "next/image";
import Link from "next/link";
import { notFound, useParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { ArrowLeft, Printer, Scissors } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { useCollection } from "@/components/CollectionProvider";
import { MascotLoader } from "@/components/MascotLoader";
import {
  browseCards,
  Card,
  getSet,
  SetWithCardCount,
} from "@/lib/api";
import { getToken } from "@/lib/auth";

type Layout = 9 | 16 | 25;

const LAYOUT_COLS: Record<Layout, number> = { 9: 3, 16: 4, 25: 5 };

const LAYOUT_META: Record<
  Layout,
  { label: string; hint: string; cost: string }
> = {
  9: {
    label: "3 × 3",
    hint: "Standard binder",
    cost: "Card sits large — easy to spot in a full pocket.",
  },
  16: {
    label: "4 × 4",
    hint: "Compact binder",
    cost: "Balanced — good for 200+ card sets.",
  },
  25: {
    label: "5 × 5",
    hint: "Toploader / long box",
    cost: "Densest layout — fewer pages, smaller placeholders.",
  },
};

export default function PrintChecklistPage() {
  return (
    <Suspense fallback={<PageLoading />}>
      <PrintChecklistContent />
    </Suspense>
  );
}

function PageLoading() {
  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <div className="flex justify-center py-16">
        <MascotLoader />
      </div>
    </main>
  );
}

function PrintChecklistContent() {
  const params = useParams<{ id: string }>();
  const setId = params.id;
  const { user } = useAuth();
  const { has } = useCollection();

  const [set, setSet] = useState<SetWithCardCount | null>(null);
  const [cards, setCards] = useState<Card[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [layout, setLayout] = useState<Layout>(9);
  const [onlyMissing, setOnlyMissing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const s = await getSet(setId);
        if (!cancelled) setSet(s);
      } catch (e) {
        if (e instanceof Error && e.message.includes("404")) notFound();
        if (!cancelled)
          setError(e instanceof Error ? e.message : "Unknown error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [setId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const token = user ? getToken() ?? undefined : undefined;
        // Paginate through the whole set — backend caps page_size at
        // 250, but a set can carry >250 cards once secrets + variants
        // are counted.
        const PAGE = 250;
        let page = 1;
        const collected: Card[] = [];
        while (!cancelled) {
          const result = await browseCards(
            { set_id: setId, sort: "number_asc", page_size: PAGE, page },
            token,
          );
          collected.push(...result.items);
          if (
            result.items.length < PAGE ||
            collected.length >= result.total
          ) {
            break;
          }
          page += 1;
        }
        if (!cancelled) setCards(collected);
      } catch (e) {
        if (!cancelled)
          setError(e instanceof Error ? e.message : "Unknown error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [setId, user]);

  const ownedCount = useMemo(() => {
    if (!cards || !user) return 0;
    return cards.filter((c) => has(c.id)).length;
  }, [cards, user, has]);

  const filteredCards = useMemo(() => {
    if (!cards) return [];
    if (!onlyMissing || !user) return cards;
    return cards.filter((c) => !has(c.id));
  }, [cards, onlyMissing, user, has]);

  const pages = useMemo(() => {
    const out: Card[][] = [];
    for (let i = 0; i < filteredCards.length; i += layout) {
      out.push(filteredCards.slice(i, i + layout));
    }
    return out;
  }, [filteredCards, layout]);

  const totalSheets = pages.length;
  const previewCards = filteredCards.slice(0, 6);

  if (error) {
    return (
      <main className="mx-auto max-w-4xl px-4 py-8">
        <div className="rounded-card border border-accent-red/30 bg-accent-red/10 p-4 text-sm">
          <div className="font-semibold">Failed to load the set</div>
          <div className="mt-1 font-mono text-text-secondary">{error}</div>
        </div>
      </main>
    );
  }

  if (!set || !cards) {
    return <PageLoading />;
  }

  const missingCount = cards.length - ownedCount;
  const ownedPct =
    cards.length > 0 ? Math.round((ownedCount / cards.length) * 100) : 0;

  return (
    <>
      {/* Site-facing UI — hidden when printing. */}
      <div className="print:hidden">
        <main className="mx-auto max-w-6xl px-4 py-6">
          <nav className="mb-4 text-sm text-text-secondary">
            <Link
              href={`/sets/${setId}`}
              className="inline-flex items-center gap-1 hover:text-text-primary"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to {set.name}
            </Link>
          </nav>

          {/* Hero — set logo + name + task copy. Feels distinctly
              PullList (yellow accent, mascot chip, card sub-badge). */}
          <header className="mb-6 rounded-card border border-border bg-bg-surface/70 p-5">
            <div className="flex flex-col gap-4 md:flex-row md:items-center">
              {set.logo_url && (
                <div className="relative h-16 w-36 flex-shrink-0">
                  <Image
                    src={set.logo_url}
                    alt={set.name}
                    fill
                    className="object-contain object-left"
                    sizes="144px"
                    unoptimized
                    priority
                  />
                </div>
              )}
              <div className="flex-1">
                <div className="mb-1 inline-flex items-center gap-1.5 rounded-full bg-accent-yellow/15 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-widest text-accent-yellow">
                  <Scissors className="h-3 w-3" />
                  Print &amp; cut · Binder placeholders
                </div>
                <h1 className="text-2xl font-extrabold tracking-tight md:text-3xl">
                  {set.name}
                </h1>
                <p className="mt-1 max-w-2xl text-sm text-text-secondary">
                  Slide grayscale placeholders into empty binder pockets so
                  your still-need list stays visible at a glance.
                </p>
              </div>
            </div>

            {user && (
              <div className="mt-5 grid gap-4 md:grid-cols-[1fr_auto]">
                <div>
                  <div className="mb-1 flex items-baseline justify-between text-xs">
                    <span className="font-mono uppercase tracking-wider text-text-tertiary">
                      Your collection · {set.name}
                    </span>
                    <span className="font-mono">
                      <span className="text-accent-green">{ownedCount}</span>
                      <span className="text-text-tertiary">
                        /{cards.length} · {ownedPct}%
                      </span>
                    </span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-bg">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-accent-green/70 to-accent-green transition-all duration-500"
                      style={{ width: `${ownedPct}%` }}
                    />
                  </div>
                </div>
                <div className="flex items-center gap-3 rounded-lg border border-border bg-bg px-3 py-2 text-xs">
                  <span className="font-mono uppercase tracking-wider text-text-tertiary">
                    Missing
                  </span>
                  <span className="font-mono text-lg font-extrabold text-accent-red">
                    {missingCount}
                  </span>
                </div>
              </div>
            )}
          </header>

          <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
            {/* Left: controls */}
            <div>
              {user ? (
                <label className="mb-5 inline-flex cursor-pointer items-center gap-3 rounded-lg border border-border bg-bg-surface/50 px-4 py-3 text-sm transition-colors hover:border-accent-yellow/40">
                  <input
                    type="checkbox"
                    checked={onlyMissing}
                    onChange={(e) => setOnlyMissing(e.target.checked)}
                    className="h-4 w-4 accent-accent-yellow"
                  />
                  <div className="flex flex-col">
                    <span className="font-semibold">Print only what you&apos;re missing</span>
                    <span className="text-[11px] text-text-tertiary">
                      {filteredCards.length} of {cards.length} cards will print
                    </span>
                  </div>
                </label>
              ) : (
                <div className="mb-5 rounded-lg border border-dashed border-border/60 bg-bg-surface/40 px-4 py-3 text-xs text-text-tertiary">
                  <Link
                    href={`/login?next=${encodeURIComponent(`/sets/${setId}/print`)}`}
                    className="font-semibold text-accent-yellow hover:underline"
                  >
                    Sign in
                  </Link>{" "}
                  to skip cards you already own. Without an account every card
                  in the set prints ({cards.length} placeholders).
                </div>
              )}

              <div className="mb-4">
                <div className="mb-2 text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
                  Pick your binder layout
                </div>
                <div className="flex flex-col gap-2">
                  {([9, 16, 25] as Layout[]).map((n) => (
                    <button
                      key={n}
                      type="button"
                      onClick={() => setLayout(n)}
                      className={
                        "flex items-center justify-between rounded-lg border px-4 py-3 text-left transition-colors " +
                        (layout === n
                          ? "border-accent-yellow bg-accent-yellow/10 text-text-primary"
                          : "border-border bg-bg-surface/40 text-text-secondary hover:border-accent-yellow/40")
                      }
                    >
                      <div>
                        <div className="text-lg font-extrabold leading-none">
                          {LAYOUT_META[n].label}
                          <span className="ml-2 text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
                            {LAYOUT_META[n].hint}
                          </span>
                        </div>
                        <div className="mt-1 text-[11px] text-text-tertiary">
                          {LAYOUT_META[n].cost}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-2xl font-extrabold leading-none">
                          {n}
                        </div>
                        <div className="text-[9px] font-mono uppercase tracking-wider text-text-tertiary">
                          per page
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <button
                type="button"
                onClick={() => window.print()}
                className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-full bg-accent-yellow px-6 py-3.5 text-base font-bold text-gray-900 shadow-md shadow-accent-yellow/25 transition hover:brightness-105"
              >
                <Printer className="h-5 w-5" />
                Send to printer — {totalSheets} sheet
                {totalSheets === 1 ? "" : "s"}
              </button>
              <div className="mt-2 flex items-center justify-between text-[11px] text-text-tertiary">
                <span>{filteredCards.length} placeholders</span>
                <span>{totalSheets} pages of letter paper</span>
              </div>
            </div>

            {/* Right: live preview strip */}
            <div className="rounded-card border border-border bg-bg-surface/40 p-4">
              <div className="mb-3 flex items-baseline justify-between">
                <span className="text-[10px] font-mono uppercase tracking-widest text-text-tertiary">
                  Live preview · first {previewCards.length}
                </span>
                <span className="text-[10px] font-mono text-text-tertiary">
                  {LAYOUT_META[layout].label}
                </span>
              </div>
              {previewCards.length > 0 ? (
                <div
                  className="grid gap-2"
                  style={{
                    gridTemplateColumns: `repeat(${LAYOUT_COLS[layout]}, 1fr)`,
                  }}
                >
                  {previewCards.map((c, idx) => (
                    <PreviewTile key={c.id} card={c} idx={idx + 1} />
                  ))}
                </div>
              ) : (
                <div className="rounded-lg border border-dashed border-border/60 bg-bg/30 p-8 text-center text-xs text-text-tertiary">
                  You already own every card in this set. Nothing to print!
                </div>
              )}
              <div className="mt-3 flex items-center gap-2 text-[10px] leading-relaxed text-text-tertiary">
                <span className="inline-flex h-1.5 w-1.5 rounded-full bg-accent-yellow" />
                Each placeholder shows the card&apos;s name, set number, and
                the exact binder position (page · slot · row/col) so you can
                slot it in without thinking.
              </div>
            </div>
          </div>
        </main>
      </div>

      {/* Print body — the site chrome is display:none at print, only
          this section renders on paper. */}
      <div className="hidden print:block">
        {pages.map((page, i) => (
          <div
            key={i}
            className={`print-sheet print-sheet-cols-${LAYOUT_COLS[layout]}`}
          >
            <div className="print-sheet-header">
              Sheet {i + 1} of {totalSheets} · {set.name} · pulllist.org
            </div>
            <div
              className={`print-sheet-grid print-grid-cols-${LAYOUT_COLS[layout]}`}
            >
              {page.map((card, idx) => {
                const positionInPage = idx + 1;
                const cols = LAYOUT_COLS[layout];
                const row = Math.floor(idx / cols) + 1;
                const col = (idx % cols) + 1;
                return (
                  <div key={card.id} className="print-card">
                    {card.image_small ? (
                      // Plain <img> (not next/image) — the print media
                      // needs images to be in the layout pass BEFORE
                      // the browser lays out pages, so we can't have
                      // any lazy loading kicking in. loading="eager"
                      // + fetchpriority forces the browser to have
                      // pixels ready when @media print fires.
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={card.image_small}
                        alt={card.name}
                        className="print-card-image"
                        loading="eager"
                        // @ts-expect-error fetchpriority landed in the
                        // DOM spec after React's type defs
                        fetchpriority="high"
                        decoding="sync"
                      />
                    ) : (
                      <div className="print-card-image print-card-image-empty">
                        {card.name}
                      </div>
                    )}
                    <div className="print-card-meta">
                      <div className="print-card-name">{card.name}</div>
                      <div className="print-card-numbers">
                        <span className="print-card-number">
                          #{card.number ?? "—"}
                        </span>
                        <span className="print-card-position">
                          p.{i + 1}s.{positionInPage} · r{row} c{col}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <style jsx global>{`
        /* Standard US letter is 8.5in × 11in = 215.9mm × 279.4mm.
           @page margin 6mm leaves 203.9mm × 267.4mm usable.
           Sheet header takes ~6mm, so cards get ~260mm of vertical
           space. Card art aspect ratio is 245:342 (~0.716). Per
           layout we solve for the largest card image whose tile
           (image + 4mm label block) fits three-across or four-across
           or five-across within the sheet:
             3×3 → image w ≈ 62mm  → tile h ≈ 91mm
             4×4 → image w ≈ 46mm  → tile h ≈ 68mm
             5×5 → image w ≈ 36mm  → tile h ≈ 55mm
           Widths are held via fixed-column-width grid template so
           browsers don't reflow when a font-size changes. */
        .print-sheet {
          display: block;
          padding: 0;
          page-break-after: always;
          break-after: page;
          overflow: hidden;
        }
        .print-sheet:last-child {
          page-break-after: auto;
          break-after: auto;
        }
        .print-sheet-header {
          font-size: 9pt;
          color: #666;
          margin-bottom: 3mm;
        }
        .print-sheet-grid {
          display: grid;
          gap: 4mm;
        }
        .print-grid-cols-3 {
          grid-template-columns: repeat(3, 62mm);
        }
        .print-grid-cols-4 {
          grid-template-columns: repeat(4, 46mm);
        }
        .print-grid-cols-5 {
          grid-template-columns: repeat(5, 36mm);
        }
        .print-card {
          display: flex;
          flex-direction: column;
          align-items: stretch;
          break-inside: avoid;
          page-break-inside: avoid;
        }
        .print-card-image {
          display: block;
          width: 100%;
          aspect-ratio: 245 / 342;
          object-fit: contain;
          background: #eee;
          border: 1px solid #ccc;
          /* Grayscale renders regardless of ink budget. */
          filter: grayscale(1) contrast(1.05);
        }
        .print-card-image-empty {
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 8pt;
          color: #555;
          text-align: center;
          padding: 2mm;
        }
        .print-card-meta {
          margin-top: 1mm;
          font-family: -apple-system, BlinkMacSystemFont, sans-serif;
          font-size: 7pt;
          color: #333;
          line-height: 1.15;
        }
        .print-card-name {
          font-weight: 700;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .print-card-numbers {
          margin-top: 0.5mm;
          display: flex;
          justify-content: space-between;
          font-size: 6pt;
          color: #666;
        }
        .print-card-number {
          font-family: ui-monospace, SFMono-Regular, monospace;
          font-weight: 700;
        }
        .print-card-position {
          font-family: ui-monospace, SFMono-Regular, monospace;
        }

        @media print {
          @page {
            size: letter;
            margin: 6mm;
          }
          html,
          body {
            background: #fff !important;
            margin: 0 !important;
            padding: 0 !important;
          }
        }
      `}</style>
    </>
  );
}

/**
 * Grayscale preview tile — matches how the printed card will look,
 * miniature. Doesn't need to be interactive; just gives the user a
 * confidence check before they burn ink.
 */
function PreviewTile({ card, idx }: { card: Card; idx: number }) {
  return (
    <div className="relative overflow-hidden rounded-md border border-border bg-bg">
      <div
        className="relative"
        style={{ aspectRatio: "245 / 342", filter: "grayscale(1) contrast(1.03)" }}
      >
        {card.image_small ? (
          <Image
            src={card.image_small}
            alt={card.name}
            fill
            unoptimized
            sizes="160px"
            className="object-contain"
          />
        ) : (
          <div className="flex h-full items-center justify-center px-2 text-center text-[9px] text-text-tertiary">
            {card.name}
          </div>
        )}
      </div>
      <div className="absolute left-1 top-1 rounded bg-black/70 px-1 py-0.5 text-[8px] font-mono font-bold text-white">
        #{card.number ?? "—"}
      </div>
      <div className="absolute right-1 top-1 rounded bg-accent-yellow px-1 py-0.5 text-[8px] font-mono font-bold text-gray-900">
        {idx}
      </div>
    </div>
  );
}
