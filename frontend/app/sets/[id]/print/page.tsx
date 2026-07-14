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
 * The layout is print-optimised: `@media print` shrinks margins,
 * hides the site chrome, forces page breaks between sheets, and
 * de-tints backgrounds. Browsers' native Print dialog handles the
 * PDF export.
 */

import Image from "next/image";
import Link from "next/link";
import { notFound, useParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { ArrowLeft, Printer } from "lucide-react";

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
const LAYOUT_LABEL: Record<Layout, string> = {
  9: "3×3",
  16: "4×4",
  25: "5×5",
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
    <main className="mx-auto max-w-[100rem] px-4 py-8">
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
        const result = await browseCards(
          { set_id: setId, sort: "number_asc", page_size: 500 },
          token,
        );
        if (!cancelled) setCards(result.items);
      } catch (e) {
        if (!cancelled)
          setError(e instanceof Error ? e.message : "Unknown error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [setId, user]);

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

  return (
    <>
      {/* Chrome + controls — hidden when printing. */}
      <div className="print:hidden">
        <main className="mx-auto max-w-4xl px-4 py-8">
          <nav className="mb-6 text-sm text-text-secondary">
            <Link
              href={`/sets/${setId}`}
              className="inline-flex items-center gap-1 hover:text-text-primary"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to {set.name}
            </Link>
          </nav>

          <header className="mb-6">
            <div className="mb-1 text-[10px] font-mono uppercase tracking-widest text-text-tertiary">
              Print checklist
            </div>
            <h1 className="text-3xl font-extrabold tracking-tight">
              {set.name}
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-text-secondary">
              Print grayscale card placeholders that slot into your physical
              binder — cut along the card edges and drop into empty pockets so
              your still-need list is visible at a glance.
            </p>
          </header>

          {user ? (
            <label className="mb-4 inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-bg-surface px-4 py-2 text-sm">
              <input
                type="checkbox"
                checked={onlyMissing}
                onChange={(e) => setOnlyMissing(e.target.checked)}
                className="h-4 w-4 accent-accent-yellow"
              />
              <span>Only cards missing from my collection</span>
              <span className="ml-2 font-mono text-xs text-text-tertiary">
                ({filteredCards.length}/{cards.length})
              </span>
            </label>
          ) : (
            <div className="mb-4 rounded-full border border-dashed border-border/60 bg-bg-surface/40 px-4 py-2 text-xs text-text-tertiary">
              <Link
                href={`/login?next=${encodeURIComponent(`/sets/${setId}/print`)}`}
                className="text-accent-yellow hover:underline"
              >
                Sign in
              </Link>{" "}
              to filter to only cards you don&apos;t already own. Without an
              account, every card in the set prints.
            </div>
          )}

          <div className="mb-6 rounded-card border border-border bg-bg-surface p-4">
            <div className="mb-2 text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
              Binder pocket layout
            </div>
            <div className="grid grid-cols-3 gap-2">
              {([9, 16, 25] as Layout[]).map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setLayout(n)}
                  className={
                    "rounded-md border py-3 text-center transition-colors " +
                    (layout === n
                      ? "border-accent-yellow bg-accent-yellow/10 text-text-primary"
                      : "border-border bg-bg text-text-secondary hover:border-accent-yellow/40")
                  }
                >
                  <div className="text-lg font-extrabold">
                    {LAYOUT_LABEL[n]}
                  </div>
                  <div className="mt-0.5 text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
                    {n} pockets
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="mb-6 rounded-card border border-border bg-bg-surface/50 p-4 text-xs leading-relaxed text-text-secondary">
            <span className="font-semibold text-text-primary">
              What you&apos;ll get:
            </span>{" "}
            Grayscale card images printed {layout}-per-page (fits standard
            printer paper). Each card shows its name, set number, and binder
            position. Cut along the card edges and use as binder placeholders.
          </div>

          <button
            type="button"
            onClick={() => window.print()}
            className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-accent-yellow px-6 py-3 text-base font-bold text-gray-900 shadow-md shadow-accent-yellow/20 transition hover:brightness-105"
          >
            <Printer className="h-5 w-5" />
            Preview &amp; Print {filteredCards.length} card
            {filteredCards.length === 1 ? "" : "s"}
          </button>
          <div className="mt-2 text-center text-xs text-text-tertiary">
            {totalSheets} sheet{totalSheets === 1 ? "" : "s"} of paper
          </div>
        </main>
      </div>

      {/* Print body — the site chrome is `display: none` at print, only
          this section renders on paper. */}
      <div className="hidden print:block">
        {pages.map((page, i) => (
          <div
            key={i}
            className="print-sheet"
            style={
              {
                gridTemplateColumns: `repeat(${LAYOUT_COLS[layout]}, 1fr)`,
              } as React.CSSProperties
            }
          >
            <div className="print-sheet-header">
              Sheet {i + 1} of {totalSheets} · {set.name}
            </div>
            {page.map((card, idx) => {
              const positionInPage = idx + 1;
              const cols = LAYOUT_COLS[layout];
              const row = Math.floor(idx / cols) + 1;
              const col = (idx % cols) + 1;
              return (
                <div key={card.id} className="print-card">
                  {card.image_small ? (
                    <div className="print-card-image">
                      <Image
                        src={card.image_small}
                        alt={card.name}
                        fill
                        unoptimized
                        className="object-contain"
                        sizes="200px"
                      />
                    </div>
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
        ))}
      </div>

      <style jsx global>{`
        .print-sheet {
          display: grid;
          gap: 6mm;
          padding: 8mm;
          page-break-after: always;
        }
        .print-sheet:last-child {
          page-break-after: auto;
        }
        .print-sheet-header {
          grid-column: 1 / -1;
          font-size: 9pt;
          color: #666;
          margin-bottom: 2mm;
        }
        .print-card {
          display: flex;
          flex-direction: column;
          align-items: stretch;
          break-inside: avoid;
        }
        .print-card-image {
          position: relative;
          width: 100%;
          aspect-ratio: 245 / 342;
          background: #eee;
          border: 1px solid #ccc;
          overflow: hidden;
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
          font-size: 8pt;
          color: #333;
        }
        .print-card-name {
          font-weight: 700;
          line-height: 1.15;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .print-card-numbers {
          margin-top: 0.5mm;
          display: flex;
          justify-content: space-between;
          font-size: 7pt;
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
          body {
            background: #fff !important;
          }
        }
      `}</style>
    </>
  );
}
