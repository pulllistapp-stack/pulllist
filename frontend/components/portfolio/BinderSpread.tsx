"use client";

/**
 * BinderSpread — the physical open-binder scene for a master set.
 *
 * Ports the layout Variant produced (leather shell + brass rings + page
 * thickness + rotateY page-flip animation) into our project, wired to
 * our BinderSlot type. The surrounding chrome — breadcrumbs, tabs,
 * progress bar, mode/sort toggles — lives on the parent page, so this
 * component intentionally does NOT re-implement any of them; it renders
 * the spread scene, click-to-flip edges, and keyboard nav only.
 *
 * External texture URLs from the Variant draft are removed on purpose:
 * they'd need next.config.mjs remotePatterns just to load a decorative
 * background. Cream + subtle CSS gradient reads close enough at this
 * viewing distance and keeps the component self-contained.
 */

import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { BinderSize, BinderSlot } from "@/lib/api";

const SLOTS_PER_PAGE: Record<BinderSize, number> = {
  "3x3": 9,
  "4x3": 12,
  "4x4": 16,
};

const GRID_COLS: Record<BinderSize, string> = {
  "3x3": "grid-cols-3",
  "4x3": "grid-cols-4",
  "4x4": "grid-cols-4",
};

const GRID_ROWS: Record<BinderSize, string> = {
  "3x3": "grid-rows-3",
  "4x3": "grid-rows-3",
  "4x4": "grid-rows-4",
};

type Direction = 1 | -1 | 0;

export function BinderSpread({
  slots,
  gridSize,
  initialSpreadIndex = 0,
  onSpreadChange,
}: {
  slots: BinderSlot[];
  gridSize: BinderSize;
  initialSpreadIndex?: number;
  onSpreadChange?: (index: number) => void;
}) {
  const slotsPerPage = SLOTS_PER_PAGE[gridSize];
  const slotsPerSpread = slotsPerPage * 2;
  const totalSpreads = Math.max(1, Math.ceil(slots.length / slotsPerSpread));

  const [spreadIndex, setSpreadIndex] = useState(initialSpreadIndex);
  const [flipping, setFlipping] = useState(false);
  const [direction, setDirection] = useState<Direction>(0);
  const [query, setQuery] = useState("");

  // Grid size may change while user's on a later spread than the new
  // grid can reach; clamp to keep the spread pointer valid.
  useEffect(() => {
    if (spreadIndex >= totalSpreads) {
      setSpreadIndex(totalSpreads - 1);
    }
  }, [gridSize, spreadIndex, totalSpreads]);

  const { leftSlots, rightSlots } = useMemo(() => {
    const start = spreadIndex * slotsPerSpread;
    const chunk = slots.slice(start, start + slotsPerSpread);
    return {
      leftSlots: padTo(chunk.slice(0, slotsPerPage), slotsPerPage),
      rightSlots: padTo(chunk.slice(slotsPerPage, slotsPerSpread), slotsPerPage),
    };
  }, [slots, spreadIndex, slotsPerPage, slotsPerSpread]);

  const goToSpread = useCallback(
    (next: number) => {
      const clamped = Math.max(0, Math.min(totalSpreads - 1, next));
      if (clamped === spreadIndex || flipping) return;
      setDirection(clamped > spreadIndex ? 1 : -1);
      setFlipping(true);
      // Swap the page contents at the midpoint of the flip so the arc
      // never reveals a stale spread. 300ms of 600ms feels natural.
      window.setTimeout(() => {
        setSpreadIndex(clamped);
        onSpreadChange?.(clamped);
      }, 300);
      window.setTimeout(() => {
        setFlipping(false);
        setDirection(0);
      }, 600);
    },
    [spreadIndex, flipping, totalSpreads, onSpreadChange],
  );

  const handleNext = useCallback(() => {
    if (spreadIndex < totalSpreads - 1) goToSpread(spreadIndex + 1);
  }, [spreadIndex, totalSpreads, goToSpread]);

  const handlePrev = useCallback(() => {
    if (spreadIndex > 0) goToSpread(spreadIndex - 1);
  }, [spreadIndex, goToSpread]);

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setQuery(value);
    const needle = value.trim().toLowerCase();
    if (needle.length < 2) return;
    const idx = slots.findIndex((s) => s.name.toLowerCase().includes(needle));
    if (idx >= 0) {
      const targetSpread = Math.floor(idx / slotsPerSpread);
      if (targetSpread !== spreadIndex) goToSpread(targetSpread);
    }
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Don't hijack arrow keys while the user is typing in an input.
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA"))
        return;
      if (e.key === "ArrowRight") handleNext();
      else if (e.key === "ArrowLeft") handlePrev();
      else if (e.key === "Home") goToSpread(0);
      else if (e.key === "End") goToSpread(totalSpreads - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handleNext, handlePrev, goToSpread, totalSpreads]);

  const leftPageNum = spreadIndex * 2 + 1;
  const rightPageNum = spreadIndex * 2 + 2;

  return (
    <div className="w-full flex flex-col items-center">
      {/* Search + spread counter */}
      <div className="mb-4 flex w-full max-w-5xl items-center justify-between gap-3 flex-wrap">
        <div className="text-xs font-semibold uppercase tracking-widest text-text-tertiary">
          Spread {spreadIndex + 1} of {totalSpreads}
        </div>
        <div className="relative">
          <span
            aria-hidden
            className="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary text-sm"
          >
            🔍
          </span>
          <input
            type="text"
            value={query}
            onChange={handleSearch}
            placeholder="Jump to card…"
            className="bg-bg-surface border border-border rounded-full py-2 pl-9 pr-4 text-sm w-64 focus:outline-none focus:border-accent-yellow/50"
          />
        </div>
      </div>

      {/* Binder scene */}
      <div
        className="relative w-full max-w-5xl"
        style={{ perspective: "1600px" }}
      >
        {/* Leather shell */}
        <div
          className="absolute inset-x-[-1.5%] inset-y-[-3%] rounded-[28px] -z-10 shadow-[0_30px_60px_-20px_rgba(0,0,0,0.35)]"
          style={{
            background:
              "radial-gradient(circle at 30% 20%, #6b4a35 0%, #4a3020 60%, #2d1c10 100%)",
          }}
          aria-hidden
        />

        <div
          className="relative w-full flex items-stretch justify-center"
          style={{
            aspectRatio: gridSize === "4x4" ? "3 / 2.6" : "3 / 2.1",
            transformStyle: "preserve-3d",
          }}
        >
          {/* Left page (static base under the flipping overlay) */}
          <PageBase
            slots={leftSlots}
            pageNumber={leftPageNum}
            gridSize={gridSize}
            side="left"
          />
          {/* Right page (static base) */}
          <PageBase
            slots={rightSlots}
            pageNumber={rightPageNum}
            gridSize={gridSize}
            side="right"
          />

          {/* Flipping-page overlay */}
          <AnimatePresence>
            {flipping && direction !== 0 && (
              <motion.div
                key={`flip-${spreadIndex}-${direction}`}
                className="absolute top-0 h-full w-1/2 z-30 pointer-events-none"
                style={{
                  left: direction === 1 ? "50%" : "0%",
                  transformOrigin: direction === 1 ? "left center" : "right center",
                  transformStyle: "preserve-3d",
                }}
                initial={{ rotateY: 0 }}
                animate={{ rotateY: direction === 1 ? -180 : 180 }}
                transition={{ duration: 0.6, ease: [0.4, 0, 0.2, 1] }}
              >
                {/* Front face — the outgoing page */}
                <div
                  className="absolute inset-0"
                  style={{ backfaceVisibility: "hidden" }}
                >
                  <PageBase
                    slots={direction === 1 ? rightSlots : leftSlots}
                    pageNumber={direction === 1 ? rightPageNum : leftPageNum}
                    gridSize={gridSize}
                    side={direction === 1 ? "right" : "left"}
                    floating
                  />
                </div>
                {/* Back face — a blank next page (contents rendered by
                    the base layer once the flip completes). */}
                <div
                  className="absolute inset-0"
                  style={{
                    backfaceVisibility: "hidden",
                    transform: "rotateY(180deg)",
                  }}
                >
                  <PageBase
                    slots={padTo([], slotsPerPage)}
                    pageNumber={
                      direction === 1 ? rightPageNum + 1 : leftPageNum - 1
                    }
                    gridSize={gridSize}
                    side={direction === 1 ? "left" : "right"}
                    floating
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Brass rings (in front of pages, behind the flip overlay) */}
          <div
            className="pointer-events-none absolute left-1/2 top-0 h-full w-16 -translate-x-1/2 z-20 flex flex-col items-center justify-around py-[8%]"
            aria-hidden
          >
            {[0, 1, 2].map((i) => (
              <Ring key={i} />
            ))}
          </div>

          {/* Click-to-flip edges */}
          <button
            type="button"
            onClick={handlePrev}
            disabled={spreadIndex === 0 || flipping}
            aria-label="Previous spread"
            className="absolute left-0 top-[10%] bottom-[10%] w-[10%] z-40 cursor-pointer group disabled:cursor-default"
          >
            <span className="absolute inset-y-0 left-0 w-full opacity-0 group-hover:opacity-100 group-disabled:opacity-0 transition-opacity bg-gradient-to-r from-black/10 to-transparent" />
          </button>
          <button
            type="button"
            onClick={handleNext}
            disabled={spreadIndex >= totalSpreads - 1 || flipping}
            aria-label="Next spread"
            className="absolute right-0 top-[10%] bottom-[10%] w-[10%] z-40 cursor-pointer group disabled:cursor-default"
          >
            <span className="absolute inset-y-0 right-0 w-full opacity-0 group-hover:opacity-100 group-disabled:opacity-0 transition-opacity bg-gradient-to-l from-black/10 to-transparent" />
          </button>
        </div>
      </div>

      {/* Keyboard hint strip */}
      <div className="mt-6 flex items-center gap-3 text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
        <span className="flex items-center gap-1">
          <kbd className="rounded bg-bg-surface border border-border px-1 py-0.5">
            ←
          </kbd>
          Prev
        </span>
        <span className="text-text-tertiary/60">·</span>
        <span>Click page edge to flip</span>
        <span className="text-text-tertiary/60">·</span>
        <span className="flex items-center gap-1">
          Next
          <kbd className="rounded bg-bg-surface border border-border px-1 py-0.5">
            →
          </kbd>
        </span>
      </div>
    </div>
  );
}

function PageBase({
  slots,
  pageNumber,
  gridSize,
  side,
  floating,
}: {
  slots: (BinderSlot | null)[];
  pageNumber: number;
  gridSize: BinderSize;
  side: "left" | "right";
  floating?: boolean;
}) {
  const isLeft = side === "left";
  return (
    <div
      className={
        "relative flex flex-col p-[3.5%] " +
        (floating
          ? "absolute inset-0"
          : "flex-1 h-full ") +
        (isLeft ? "rounded-l-lg" : "rounded-r-lg")
      }
      style={{
        // Warm cream page with a subtle radial gradient for depth so the
        // outer edges read slightly cooler than the center — mimics a
        // page catching soft overhead light.
        background:
          "radial-gradient(circle at 50% 40%, #fdf7e6 0%, #f5ecd6 100%)",
        boxShadow: floating
          ? "0 20px 40px -10px rgba(0,0,0,0.3)"
          : undefined,
      }}
    >
      {/* Page number in outer corner */}
      <div
        className={
          "absolute top-2 text-[9px] font-bold text-stone-500/70 tracking-[0.2em] uppercase " +
          (isLeft ? "left-4" : "right-4")
        }
      >
        Page {pageNumber}
      </div>

      {/* Gutter shadow near the spine (fades to nothing at the outer edge) */}
      <div
        className={
          "pointer-events-none absolute top-0 bottom-0 w-8 " +
          (isLeft
            ? "right-0 bg-gradient-to-l from-black/15 to-transparent"
            : "left-0 bg-gradient-to-r from-black/15 to-transparent")
        }
        aria-hidden
      />

      {/* Slot grid */}
      <div
        className={
          "mt-4 grid gap-[2.5%] flex-1 " +
          GRID_COLS[gridSize] +
          " " +
          GRID_ROWS[gridSize]
        }
      >
        {slots.map((slot, idx) => (
          <Pocket key={idx} slot={slot} />
        ))}
      </div>
    </div>
  );
}

function Pocket({ slot }: { slot: BinderSlot | null }) {
  return (
    <div
      className="relative aspect-[3/4] w-full rounded-[3px] overflow-hidden"
      style={{
        backgroundColor: "#efe7d4",
        boxShadow:
          "inset 0 2px 4px rgba(70, 50, 20, 0.15), inset 0 -1px 2px rgba(255, 255, 255, 0.4)",
      }}
    >
      {/* Plastic-sleeve gloss */}
      <div
        className="pointer-events-none absolute inset-0 z-10 opacity-70"
        style={{
          background:
            "linear-gradient(135deg, rgba(255,255,255,0.45) 0%, rgba(255,255,255,0) 35%, rgba(255,255,255,0) 100%)",
        }}
        aria-hidden
      />

      {slot ? <SlotContents slot={slot} /> : <EmptyPocketMark />}
    </div>
  );
}

function SlotContents({ slot }: { slot: BinderSlot }) {
  const variantLabel =
    slot.variant === "base"
      ? null
      : slot.variant === "reverseHolofoil"
        ? "Rev"
        : slot.variant === "holofoil"
          ? "Holo"
          : slot.variant === "1stEdition"
            ? "1st"
            : slot.variant === "1stEditionHolofoil"
              ? "1st H"
              : slot.variant === "unlimitedHolofoil"
                ? "Unl H"
                : slot.variant === "unlimited"
                  ? "Unl"
                  : slot.variant.slice(0, 4);

  const body = (
    <div
      className={
        "relative w-full h-full transition-[filter,opacity] duration-500 " +
        (slot.owned ? "" : "grayscale opacity-40")
      }
    >
      {slot.image_small ? (
        // Plain <img> instead of next/image — we render dozens of slots
        // per spread and every card image is on a next-config allowlisted
        // hostname anyway. Avoids the optimizer paying per-slot ping cost.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={slot.image_small}
          alt={slot.name}
          className="w-full h-full object-contain"
          loading="lazy"
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center p-1 text-center">
          <div className="text-[9px] font-mono text-stone-600/70 leading-tight">
            {slot.number ?? "—"}
            <br />
            {slot.name.slice(0, 16)}
          </div>
        </div>
      )}
      {slot.number && (
        <span className="absolute left-1 top-1 rounded bg-black/60 px-1 py-0.5 text-[8px] font-mono text-white z-10">
          {slot.number}
        </span>
      )}
      {variantLabel && (
        <span className="absolute right-1 top-1 rounded bg-amber-500/90 px-1 py-0.5 text-[8px] font-semibold uppercase text-stone-900 tracking-wider z-10">
          {variantLabel}
        </span>
      )}
      {slot.owned && (
        <span
          className="absolute bottom-1 right-1 flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500 text-white text-[10px] shadow border border-white/50 z-10"
          aria-label="Owned"
        >
          ✓
        </span>
      )}
    </div>
  );

  return (
    <Link
      href={`/cards/${slot.card_id}`}
      title={`${slot.name}${slot.owned ? " · owned" : ""}`}
      className="absolute inset-0 block"
    >
      {body}
    </Link>
  );
}

function EmptyPocketMark() {
  return (
    <div className="absolute inset-1 flex items-center justify-center rounded-sm border-2 border-dashed border-stone-400/30">
      <span className="text-stone-400/60 text-lg" aria-hidden>
        +
      </span>
    </div>
  );
}

function Ring() {
  return (
    <div
      className="relative w-8 h-14"
      aria-hidden
      style={{
        background: "linear-gradient(90deg, #8a7345 0%, #d4b877 50%, #8a7345 100%)",
        borderRadius: "8px",
        boxShadow:
          "inset 0 1px 2px rgba(255,255,255,0.4), 0 3px 6px rgba(0,0,0,0.3)",
      }}
    >
      <div
        className="absolute inset-y-2 left-1/2 -translate-x-1/2 w-[70%] rounded-full"
        style={{
          background:
            "linear-gradient(180deg, rgba(0,0,0,0.2) 0%, rgba(0,0,0,0.05) 100%)",
        }}
      />
    </div>
  );
}

function padTo<T>(arr: T[], n: number): (T | null)[] {
  if (arr.length >= n) return arr.slice(0, n);
  const out: (T | null)[] = [...arr];
  while (out.length < n) out.push(null);
  return out;
}
