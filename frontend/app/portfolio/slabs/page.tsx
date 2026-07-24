"use client";

/**
 * /portfolio/slabs — user's graded cards rendered inside SlabFrame.
 *
 * Reuses listMyItems() and filters is_graded=true. The grade field is
 * stored as "PSA 10" / "BGS 9.5" etc. — same split logic as the edit
 * modal. Top-of-page toggle switches the frame PNG (BGS vs PSA); the
 * grader shown on each slab still reflects what the item actually is.
 */

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ButtonHTMLAttributes, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { MascotLoader } from "@/components/MascotLoader";
import { PortfolioTabs } from "@/components/portfolio/PortfolioTabs";
import {
  SERVICE_LOGO,
  SERVICE_LOGO_PILL_CLASS,
  SlabFrame,
} from "@/components/portfolio/SlabFrame";
import { CollectionItemDetail, listMyItems } from "@/lib/auth";

type FrameStyle = "bgs" | "psa" | "clean";
type GradeService = "PSA" | "BGS" | "CGC" | "TAG";

const SERVICE_SET = new Set<GradeService>(["PSA", "BGS", "CGC", "TAG"]);

// LO's mapping: each graded item uses the slab frame that matches its
// grading service. CGC + TAG both ride on the minimal Clean frame; PSA
// + BGS get their own dedicated frames. No user-facing toggle — the
// service the user picked at collection-time chooses the frame.
const SERVICE_FRAME: Record<GradeService, FrameStyle> = {
  PSA: "psa",
  BGS: "bgs",
  CGC: "clean",
  TAG: "clean",
};

const GRADE_SUFFIX: Record<string, string> = {
  "10": "Gem Mint",
  "9.5": "Mint+",
  "9": "Mint",
};

// Slab pagination — LO wants 3 slabs per page (bigger tiles), with a
// number pager that shows at most 5 page buttons then ellipsizes.
const SLABS_PER_PAGE = 3;
const MAX_PAGE_BUTTONS = 5;

function splitGrade(grade: string | null): {
  service: GradeService;
  value: string;
  suffix?: string;
} {
  const fallback = { service: "PSA" as const, value: "10", suffix: GRADE_SUFFIX["10"] };
  if (!grade?.trim()) return fallback;
  // Match "PSA 10", "BGS 9.5 Gem Mint", "Ace 9", etc. The optional
  // trailing group captures a written-out suffix if one was stored.
  const m = grade.trim().match(/^(\S+)\s+(\S+)(?:\s+(.+))?$/);
  if (!m) return { service: "PSA", value: grade.trim() };
  const svcRaw = m[1].toUpperCase();
  const svc: GradeService = SERVICE_SET.has(svcRaw as GradeService)
    ? (svcRaw as GradeService)
    : "PSA";
  const value = m[2];
  const suffix = m[3]?.trim() || GRADE_SUFFIX[value];
  return { service: svc, value, suffix };
}

function fmtPrice(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1000) return `$${Math.round(v).toLocaleString()}`;
  return `$${v.toFixed(2)}`;
}

export default function SlabsPortfolioPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [items, setItems] = useState<CollectionItemDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.replace("/login?next=/portfolio/slabs");
      return;
    }
    let cancelled = false;
    setLoading(true);
    listMyItems()
      .then((rows) => {
        if (!cancelled) setItems(rows.filter((r) => r.is_graded));
      })
      .catch(() => {
        if (!cancelled) setItems([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user, authLoading, router]);

  const totalValue = useMemo(
    () => items.reduce((sum, it) => sum + (it.market_price_usd ?? 0) * it.qty, 0),
    [items],
  );

  const totalPages = Math.max(1, Math.ceil(items.length / SLABS_PER_PAGE));
  // Clamp page whenever the item count shrinks below what's on it
  // (e.g. user deletes a card) so we don't render an empty page.
  const currentPage = Math.min(page, totalPages);
  const pageItems = useMemo(
    () =>
      items.slice(
        (currentPage - 1) * SLABS_PER_PAGE,
        currentPage * SLABS_PER_PAGE,
      ),
    [items, currentPage],
  );

  if (authLoading || loading) {
    return (
      <main className="mx-auto max-w-[100rem] px-4 py-8">
        <PortfolioTabs active="slabs" />
        <div className="flex justify-center py-16">
          <MascotLoader />
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-[100rem] px-4 py-8">
      <PortfolioTabs active="slabs" />

      <header className="mb-6 rounded-card border border-border bg-bg-surface/70 p-5">
        <div className="flex flex-wrap items-baseline gap-8">
          <div>
            <div className="text-3xl font-extrabold text-text-primary">
              {items.length}
            </div>
            <div className="mt-1 text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
              Graded cards
            </div>
          </div>
          <div>
            <div className="text-3xl font-extrabold text-accent-green">
              {fmtPrice(totalValue)}
            </div>
            <div className="mt-1 text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
              Est. value
            </div>
          </div>
        </div>
      </header>

      {items.length === 0 ? (
        <div className="rounded-card border border-dashed border-border/60 bg-bg-surface/40 p-8 text-center">
          <div className="text-sm font-semibold text-text-secondary">
            No graded cards yet
          </div>
          <div className="mt-1 text-xs text-text-tertiary">
            Mark any collection item as graded (with a PSA / BGS / CGC / TAG grade) and it shows up slabbed here.
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-3 max-w-5xl mx-auto">
          {pageItems.map((it) => {
            const { service, value, suffix } = splitGrade(it.grade);
            const setName = (it.set_name || it.set_id).toUpperCase();
            const yearSet = it.card_number
              ? `${setName} · #${it.card_number}`
              : setName;
            const frameStyle = SERVICE_FRAME[service];
            return (
              <Link
                key={it.id}
                href={`/cards/${it.card_id}`}
                className="group block"
              >
                <SlabFrame
                  style={frameStyle}
                  cardName={it.card_name}
                  cardImage={it.image_large ?? it.image_small ?? undefined}
                  yearSet={yearSet}
                  service={service}
                  grade={value}
                  suffix={suffix}
                />
                <div className="mt-1.5 flex items-center justify-between gap-2 px-1">
                  <div className="flex items-center gap-2 min-w-0">
                    <div
                      className={
                        "relative h-6 w-14 shrink-0 flex items-center " +
                        SERVICE_LOGO_PILL_CLASS[service]
                      }
                    >
                      <Image
                        src={SERVICE_LOGO[service]}
                        alt={service}
                        fill
                        sizes="56px"
                        quality={100}
                        style={{ objectFit: "contain", objectPosition: "left center" }}
                      />
                    </div>
                    <span className="text-[12px] font-mono uppercase tracking-[0.1em] text-text-secondary tabular-nums truncate">
                      · {value}
                      {suffix ? ` ${suffix}` : ""}
                    </span>
                    {it.qty > 1 && (
                      <span className="text-[11px] font-mono text-accent-yellow shrink-0">
                        ×{it.qty}
                      </span>
                    )}
                  </div>
                  <span className="text-[13px] font-mono font-bold text-accent-green tabular-nums shrink-0">
                    {fmtPrice(it.market_price_usd)}
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      )}

      {items.length > SLABS_PER_PAGE && (
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={setPage}
        />
      )}
    </main>
  );
}

/**
 * Number pager — page 1..totalPages plus prev/next arrows. Shows at
 * most MAX_PAGE_BUTTONS number buttons around the current page, with
 * ellipses when we drop leading/trailing ranges (`1 … 4 5 6 … 12`).
 */
function Pagination({
  currentPage,
  totalPages,
  onPageChange,
}: {
  currentPage: number;
  totalPages: number;
  onPageChange: (p: number) => void;
}) {
  // Windowed range around currentPage. Half of MAX_PAGE_BUTTONS on
  // each side, clamped so we don't overflow the [1, totalPages] bounds.
  const half = Math.floor(MAX_PAGE_BUTTONS / 2);
  let start = Math.max(1, currentPage - half);
  const end = Math.min(totalPages, start + MAX_PAGE_BUTTONS - 1);
  start = Math.max(1, end - MAX_PAGE_BUTTONS + 1);

  const pages: number[] = [];
  for (let i = start; i <= end; i++) pages.push(i);

  const showLeadingEllipsis = start > 1;
  const showTrailingEllipsis = end < totalPages;

  return (
    <nav
      aria-label="Slab pagination"
      className="mt-10 flex items-center justify-center gap-1 flex-wrap"
    >
      <PageButton
        disabled={currentPage === 1}
        onClick={() => onPageChange(currentPage - 1)}
        aria-label="Previous page"
      >
        ‹
      </PageButton>
      {showLeadingEllipsis && (
        <>
          <PageButton onClick={() => onPageChange(1)}>1</PageButton>
          <span className="px-2 text-text-tertiary font-mono">…</span>
        </>
      )}
      {pages.map((p) => (
        <PageButton
          key={p}
          active={p === currentPage}
          onClick={() => onPageChange(p)}
          aria-current={p === currentPage ? "page" : undefined}
        >
          {p}
        </PageButton>
      ))}
      {showTrailingEllipsis && (
        <>
          <span className="px-2 text-text-tertiary font-mono">…</span>
          <PageButton onClick={() => onPageChange(totalPages)}>
            {totalPages}
          </PageButton>
        </>
      )}
      <PageButton
        disabled={currentPage === totalPages}
        onClick={() => onPageChange(currentPage + 1)}
        aria-label="Next page"
      >
        ›
      </PageButton>
    </nav>
  );
}

function PageButton({
  children,
  active,
  disabled,
  onClick,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { active?: boolean }) {
  return (
    <button
      {...rest}
      onClick={onClick}
      disabled={disabled}
      className={
        "min-w-[36px] h-9 px-2 text-sm font-mono rounded-btn border transition-colors " +
        (active
          ? "bg-accent-yellow border-accent-yellow text-gray-900 font-bold"
          : disabled
            ? "bg-bg-surface border-border text-text-tertiary/40 cursor-not-allowed"
            : "bg-bg-surface border-border text-text-secondary hover:text-text-primary hover:border-accent-yellow/40")
      }
    >
      {children}
    </button>
  );
}
