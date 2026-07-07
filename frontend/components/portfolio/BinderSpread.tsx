"use client";

/**
 * BinderSpread — closed-cover → open-spread binder scene for a master set.
 *
 * v2 rewrite (per LO 2026-07-06):
 *   • Closed cover first — mascot centered (or custom image), set name,
 *     tap to open. Same click also swings the front cover away.
 *   • Simpler charcoal shell reference from LO's physical binder photo,
 *     less "grandma leather", more "modern zip binder".
 *   • Real bottom Prev/Next buttons + wider edge zones with a visible
 *     chevron on hover — the previous invisible 10% strip was
 *     un-discoverable.
 *   • preserve-3d moved off the outer container onto the flip motion.div
 *     only — buttons at z-40 were being defeated by the parent's 3D
 *     stacking context.
 *   • Content swap during flip: both left and right pages jump to the
 *     destination spread at the midpoint (when the flipping sheet is
 *     edge-on and invisible) so the arc never reveals a stale state.
 *     Back face of the flipping sheet renders the destination-left page
 *     for a physical-book feel instead of a blank card.
 *   • Longer, gentler flip (900ms cubic-bezier) + a shadow-follow div
 *     that darkens the resting spread as the sheet rises.
 *
 * Cover upload / clear are wired through props so the parent page owns
 * the API call (matches the mode/sort PATCH pattern).
 */

import Image from "next/image";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import {
  ChevronLeft,
  ChevronRight,
  ImageIcon,
  Loader2,
  Trash2,
  X,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

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
  setName,
  coverImageUrl,
  initialSpreadIndex = 0,
  onSpreadChange,
  onUploadCover,
  onClearCover,
  uploadBusy,
}: {
  slots: BinderSlot[];
  gridSize: BinderSize;
  setName: string;
  coverImageUrl: string | null;
  initialSpreadIndex?: number;
  onSpreadChange?: (index: number) => void;
  /** Async — resize + POST live in the parent page. */
  onUploadCover?: (file: File) => Promise<void>;
  onClearCover?: () => Promise<void>;
  uploadBusy?: boolean;
}) {
  const slotsPerPage = SLOTS_PER_PAGE[gridSize];
  const slotsPerSpread = slotsPerPage * 2;
  const totalSpreads = Math.max(1, Math.ceil(slots.length / slotsPerSpread));

  const [coverOpen, setCoverOpen] = useState(false);
  const [spreadIndex, setSpreadIndex] = useState(initialSpreadIndex);
  const [destIndex, setDestIndex] = useState<number | null>(null);
  const [flipping, setFlipping] = useState(false);
  const [direction, setDirection] = useState<Direction>(0);
  const [query, setQuery] = useState("");
  const fileRef = useRef<HTMLInputElement | null>(null);

  // Snapshot the OUTGOING pages at the moment a flip starts. Without
  // this, once the midpoint swap fires and `current` re-derives against
  // the new spreadIndex, the flipping sheet's front face would suddenly
  // render the *incoming* content instead of the page it was already
  // showing. Refs (not state) so updating them doesn't retrigger the
  // motion animation.
  const outgoingRef = useRef<{ left: (BinderSlot | null)[]; right: (BinderSlot | null)[] } | null>(null);
  const outgoingPageRef = useRef<{ left: number; right: number } | null>(null);

  useEffect(() => {
    if (spreadIndex >= totalSpreads) {
      setSpreadIndex(totalSpreads - 1);
    }
  }, [gridSize, spreadIndex, totalSpreads]);

  const spreadFor = useCallback(
    (index: number) => {
      const start = index * slotsPerSpread;
      const chunk = slots.slice(start, start + slotsPerSpread);
      return {
        left: padTo(chunk.slice(0, slotsPerPage), slotsPerPage),
        right: padTo(chunk.slice(slotsPerPage, slotsPerSpread), slotsPerPage),
      };
    },
    [slots, slotsPerPage, slotsPerSpread],
  );

  const current = useMemo(() => spreadFor(spreadIndex), [spreadFor, spreadIndex]);
  const destination = useMemo(
    () => (destIndex !== null ? spreadFor(destIndex) : null),
    [destIndex, spreadFor],
  );

  const goToSpread = useCallback(
    (next: number) => {
      const clamped = Math.max(0, Math.min(totalSpreads - 1, next));
      if (clamped === spreadIndex || flipping) return;
      // Snapshot the pages we're leaving BEFORE the flip starts so
      // the motion.div can render them stably even after we swap the
      // static spread mid-flip.
      const start = spreadIndex * slotsPerSpread;
      const chunk = slots.slice(start, start + slotsPerSpread);
      outgoingRef.current = {
        left: padTo(chunk.slice(0, slotsPerPage), slotsPerPage),
        right: padTo(chunk.slice(slotsPerPage, slotsPerSpread), slotsPerPage),
      };
      outgoingPageRef.current = {
        left: spreadIndex * 2 + 1,
        right: spreadIndex * 2 + 2,
      };
      setDestIndex(clamped);
      setDirection(clamped > spreadIndex ? 1 : -1);
      setFlipping(true);
      // Midpoint swap: sheet is edge-on and invisible at rotateY(±90°).
      // Move the underlying spread to the destination here so the tail
      // half of the flip animation lands over the correct next content.
      window.setTimeout(() => {
        setSpreadIndex(clamped);
        onSpreadChange?.(clamped);
      }, 450);
      window.setTimeout(() => {
        setFlipping(false);
        setDirection(0);
        setDestIndex(null);
        outgoingRef.current = null;
        outgoingPageRef.current = null;
      }, 900);
    },
    [spreadIndex, flipping, totalSpreads, onSpreadChange, slots, slotsPerPage, slotsPerSpread],
  );

  const handleNext = useCallback(() => {
    if (spreadIndex < totalSpreads - 1) goToSpread(spreadIndex + 1);
  }, [spreadIndex, totalSpreads, goToSpread]);

  const handlePrev = useCallback(() => {
    if (spreadIndex > 0) goToSpread(spreadIndex - 1);
  }, [spreadIndex, goToSpread]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA"))
        return;
      if (!coverOpen) {
        // While the cover is showing, Enter / → opens it.
        if (e.key === "Enter" || e.key === "ArrowRight") setCoverOpen(true);
        return;
      }
      if (e.key === "ArrowRight") handleNext();
      else if (e.key === "ArrowLeft") handlePrev();
      else if (e.key === "Home") goToSpread(0);
      else if (e.key === "End") goToSpread(totalSpreads - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [coverOpen, handleNext, handlePrev, goToSpread, totalSpreads]);

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

  const onCoverFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && onUploadCover) await onUploadCover(file);
    if (fileRef.current) fileRef.current.value = "";
  };

  return (
    <div className="w-full flex flex-col items-center">
      {/* Cover view — hides the spread until the user opens the binder. */}
      {!coverOpen ? (
        <CoverPage
          setName={setName}
          coverImageUrl={coverImageUrl}
          gridSize={gridSize}
          onOpen={() => setCoverOpen(true)}
          onPickImage={() => fileRef.current?.click()}
          onClearCover={onClearCover}
          uploadBusy={uploadBusy}
        />
      ) : (
        <>
          {/* Header row: cover-close + spread counter + search */}
          <div className="mb-4 flex w-full max-w-5xl items-center justify-between gap-3 flex-wrap">
            <button
              type="button"
              onClick={() => setCoverOpen(false)}
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-bg-surface px-3 py-1.5 text-xs font-semibold text-text-secondary hover:text-text-primary hover:border-text-tertiary"
            >
              <X className="h-3.5 w-3.5" />
              Close binder
            </button>
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
                className="bg-bg-surface border border-border rounded-full py-2 pl-9 pr-4 text-sm w-56 focus:outline-none focus:border-accent-yellow/50"
              />
            </div>
          </div>

          {/* Binder scene */}
          <div
            className="relative w-full max-w-5xl"
            style={{ perspective: "1800px" }}
          >
            {/* Charcoal outer shell */}
            <div
              className="absolute inset-x-[-1.5%] inset-y-[-3%] rounded-[24px] -z-10 shadow-[0_30px_60px_-20px_rgba(0,0,0,0.55)]"
              style={{
                background:
                  "linear-gradient(160deg, #1a1a1a 0%, #0d0d0d 55%, #1a1a1a 100%)",
              }}
              aria-hidden
            >
              {/* subtle nylon-weave noise */}
              <div
                className="absolute inset-0 opacity-25 mix-blend-overlay pointer-events-none rounded-[24px]"
                style={{
                  backgroundImage:
                    "repeating-linear-gradient(45deg, rgba(255,255,255,0.06) 0 1px, transparent 1px 3px), repeating-linear-gradient(-45deg, rgba(0,0,0,0.15) 0 1px, transparent 1px 3px)",
                }}
              />
              {/* Zip-around: real card-guardian style. Four zipper
                  strips hug the perimeter (top / right / bottom / left)
                  with the horizontal strips reserving a small gap on
                  the ends so the vertical strips can meet them at the
                  corners without overlapping. Pull tab sits at the
                  center-bottom, matching where the chain would come
                  together on a physical zip binder. */}
              <ZipperStrip orientation="horizontal" edge="top" />
              <ZipperStrip orientation="horizontal" edge="bottom" />
              <ZipperStrip orientation="vertical" edge="left" />
              <ZipperStrip orientation="vertical" edge="right" />
              {/* Pull tab — center-bottom, hangs slightly below the
                  bottom zipper line. */}
              <div
                className="absolute pointer-events-none z-10"
                style={{
                  left: "50%",
                  bottom: "-4px",
                  transform: "translateX(-50%)",
                  width: "12px",
                  height: "20px",
                  background:
                    "linear-gradient(180deg, #e0e0e0 0%, #7a7a7a 45%, #a8a8a8 60%, #6a6a6a 100%)",
                  borderRadius: "3px",
                  boxShadow:
                    "0 3px 4px rgba(0,0,0,0.7), inset 0 1px 0 rgba(255,255,255,0.4), inset 0 -1px 0 rgba(0,0,0,0.4)",
                }}
                aria-hidden
              >
                {/* Pinhole for the ring attachment */}
                <div
                  className="absolute top-1.5 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full"
                  style={{
                    background: "#0a0a0a",
                    boxShadow:
                      "inset 0 1px 1px rgba(0,0,0,0.8), 0 0 1px rgba(255,255,255,0.2)",
                  }}
                />
              </div>
            </div>

            <div
              className="relative w-full flex items-stretch justify-center"
              style={{
                aspectRatio: gridSize === "4x4" ? "3 / 2.6" : "3 / 2.1",
              }}
            >
              {/* Static pages beneath the flip */}
              <PageBase
                slots={current.left}
                pageNumber={spreadIndex * 2 + 1}
                gridSize={gridSize}
                side="left"
              />
              <PageBase
                slots={current.right}
                pageNumber={spreadIndex * 2 + 2}
                gridSize={gridSize}
                side="right"
              />

              {/* Ambient shadow that darkens the resting spread while a
                  flip is in progress. Adds perceived depth without
                  needing per-page 3D shadows. */}
              <motion.div
                className="pointer-events-none absolute inset-0 bg-black z-25"
                initial={false}
                animate={{ opacity: flipping ? 0.18 : 0 }}
                transition={{ duration: 0.2 }}
                aria-hidden
              />

              {/* Flipping sheet.
                    KEY BUG FIX (LO 2026-07-06): the previous key of
                    `flip-${spreadIndex}-${direction}` changed when
                    `spreadIndex` was swapped mid-flip at 450ms →
                    AnimatePresence unmounted the old motion.div and
                    mounted a fresh one, which restarted the rotateY
                    animation from 0 for its remaining 450ms. Visually
                    this read as *two* pages flipping in sequence.
                    Keying on `destIndex` keeps the identity stable for
                    the entire flip because destIndex is set at start,
                    doesn't change mid-flip, and is only cleared after
                    the animation ends. Snapshot the outgoing pages at
                    flip start too, so mid-flip re-renders don't yank
                    the front face's content out from under the arc. */}
              <AnimatePresence>
                {flipping && direction !== 0 && destination && (
                  <FlippingSheet
                    key={`flip-${destIndex}-${direction}`}
                    direction={direction}
                    gridSize={gridSize}
                    outgoingLeft={outgoingRef.current?.left ?? current.left}
                    outgoingRight={outgoingRef.current?.right ?? current.right}
                    outgoingLeftPage={outgoingPageRef.current?.left ?? 0}
                    outgoingRightPage={outgoingPageRef.current?.right ?? 0}
                    destinationLeft={destination.left}
                    destinationRight={destination.right}
                    destinationLeftPage={destIndex! * 2 + 1}
                    destinationRightPage={destIndex! * 2 + 2}
                  />
                )}
              </AnimatePresence>

              {/* Center spine groove — no rings, per LO's reference
                  photo (just a subtle valley where the two pages meet).
                  A thin dark strip with an inset shadow reads as a
                  crease without competing with the cards for attention. */}
              <div
                className="pointer-events-none absolute left-1/2 top-[5%] bottom-[5%] w-[10px] -translate-x-1/2 z-20"
                style={{
                  background:
                    "linear-gradient(90deg, rgba(0,0,0,0) 0%, rgba(0,0,0,0.55) 40%, rgba(0,0,0,0.75) 50%, rgba(0,0,0,0.55) 60%, rgba(0,0,0,0) 100%)",
                  borderRadius: "6px",
                  boxShadow: "inset 0 0 6px rgba(0,0,0,0.7)",
                }}
                aria-hidden
              />
              {/* Faint highlight along the spine edges — catches light
                  where the fabric folds around the groove. */}
              <div
                className="pointer-events-none absolute left-1/2 top-[5%] bottom-[5%] w-[10px] -translate-x-1/2 z-20"
                style={{
                  background:
                    "linear-gradient(90deg, transparent 0%, transparent 15%, rgba(255,255,255,0.06) 22%, transparent 32%, transparent 68%, rgba(255,255,255,0.06) 78%, transparent 85%, transparent 100%)",
                }}
                aria-hidden
              />

              {/* Wider edge zones with a persistent chevron affordance
                  on hover. z-40 sits above pages + rings without needing
                  the parent's preserve-3d (which was breaking clicks). */}
              <EdgeButton
                side="left"
                onClick={handlePrev}
                disabled={spreadIndex === 0 || flipping}
                label="Previous spread"
              />
              <EdgeButton
                side="right"
                onClick={handleNext}
                disabled={spreadIndex >= totalSpreads - 1 || flipping}
                label="Next spread"
              />
            </div>
          </div>

          {/* Explicit nav — LO called out the earlier hints strip
              looked clickable but wasn't. These are real buttons. */}
          <div className="mt-5 flex items-center gap-2">
            <button
              type="button"
              onClick={handlePrev}
              disabled={spreadIndex === 0 || flipping}
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-bg-surface px-4 py-2 text-sm font-semibold text-text-primary hover:border-accent-yellow/50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="h-4 w-4" />
              Prev
            </button>
            <div className="min-w-[6ch] text-center font-mono text-xs text-text-tertiary tabular-nums">
              {spreadIndex + 1} / {totalSpreads}
            </div>
            <button
              type="button"
              onClick={handleNext}
              disabled={spreadIndex >= totalSpreads - 1 || flipping}
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-bg-surface px-4 py-2 text-sm font-semibold text-text-primary hover:border-accent-yellow/50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-2 text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
            Also works with{" "}
            <kbd className="rounded bg-bg-surface border border-border px-1 py-0.5 mx-0.5">
              ←
            </kbd>{" "}
            /{" "}
            <kbd className="rounded bg-bg-surface border border-border px-1 py-0.5 mx-0.5">
              →
            </kbd>
          </div>
        </>
      )}

      {/* Hidden file input — triggered from the cover page's picker btn */}
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        onChange={onCoverFile}
        className="hidden"
      />
    </div>
  );
}

const COVER_MAX_WIDTH: Record<BinderSize, string> = {
  // Sized to feel like the same physical binder about to open into
  // the spread. LO tuned this by eye:
  //   3x3 at 36rem read perfectly matched.
  //   4x3 at 42rem read smaller than the open binder → 44rem.
  //   4x4 at 48rem read bigger than the open binder → 44rem.
  "3x3": "36rem", // ~576px
  "4x3": "44rem", // ~704px
  "4x4": "44rem", // ~704px
};

function CoverPage({
  setName,
  coverImageUrl,
  gridSize,
  onOpen,
  onPickImage,
  onClearCover,
  uploadBusy,
}: {
  setName: string;
  coverImageUrl: string | null;
  gridSize: BinderSize;
  onOpen: () => void;
  onPickImage: () => void;
  onClearCover?: () => Promise<void>;
  uploadBusy?: boolean;
}) {
  const [clearing, setClearing] = useState(false);
  return (
    <div className="w-full flex flex-col items-center">
      <div
        className="relative w-full cursor-pointer group"
        style={{ perspective: "1600px", maxWidth: COVER_MAX_WIDTH[gridSize] }}
        onClick={onOpen}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") onOpen();
        }}
        aria-label="Open binder"
      >
        <motion.div
          initial={{ rotateY: 0 }}
          whileHover={{ rotateY: -8 }}
          transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
          className="relative aspect-[3/4] w-full rounded-[18px] overflow-hidden shadow-[0_30px_60px_-20px_rgba(0,0,0,0.6)]"
          style={{
            background:
              "linear-gradient(160deg, #1a1a1a 0%, #0d0d0d 55%, #222222 100%)",
            transformOrigin: "left center",
          }}
        >
          {/* nylon weave overlay */}
          <div
            className="absolute inset-0 opacity-25 mix-blend-overlay pointer-events-none"
            style={{
              backgroundImage:
                "repeating-linear-gradient(45deg, rgba(255,255,255,0.06) 0 1px, transparent 1px 3px), repeating-linear-gradient(-45deg, rgba(0,0,0,0.15) 0 1px, transparent 1px 3px)",
            }}
            aria-hidden
          />
          {/* zip along the right */}
          <div
            className="absolute top-4 bottom-4 right-2 w-[3px] rounded-full opacity-70 pointer-events-none"
            style={{
              background:
                "linear-gradient(180deg, transparent 0%, #3a3a3a 6%, #3a3a3a 94%, transparent 100%)",
            }}
            aria-hidden
          />
          {/* Cover background — the layer the quilted texture lands on.
              For an uploaded photo, the whole photo is the "material"
              and takes the quilt. For the default state, we leave the
              dark nylon shell showing through (no background image
              here) and render the mascot + title on TOP of the quilt
              layer further down so it doesn't get patterned over.

              Two-layer image treatment for uploads:
                (1) Blurred, oversized `object-cover` fill so the shell
                    behind the letterbox reads as an extension of the
                    photo instead of a plain black gap.
                (2) Sharp `object-contain` foreground shows the FULL
                    uploaded photo without cropping — LO's fix for the
                    "some parts get cut off" complaint. */}
          {coverImageUrl && (
            // LO's latest ask: image should hit every edge — no
            // letterbox, no atmospheric blur behind. Switched from
            // object-contain (letterboxed the full image) to
            // object-cover (fills the whole cover, minor edges trim).
            // The old two-layer blur-fill trick is gone with the
            // letterbox it was covering up.
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={coverImageUrl}
              alt="Binder cover"
              className="absolute inset-0 h-full w-full object-cover"
            />
          )}

          {/* Diamond-quilted PU-leather texture overlay — sits above
              whatever cover art is showing so uploaded photos take on
              a "real binder material" feel. Two crossing repeating
              linear-gradients give the diamond grid; the dark bands
              read as stitch grooves + the tight bright band next to
              each one reads as the puffed leather ridge catching light.
              Multiply blend keeps darker underlying pixels dark and
              softens the effect on white backgrounds so it works on
              any cover image without a per-image tune. */}
          <div
            className="absolute inset-0 pointer-events-none z-20 rounded-[18px] mix-blend-multiply opacity-75"
            aria-hidden
            style={{
              backgroundImage: [
                "repeating-linear-gradient(45deg, rgba(0,0,0,0.4) 0px, rgba(0,0,0,0.4) 0.6px, transparent 0.6px, transparent 5px)",
                "repeating-linear-gradient(-45deg, rgba(0,0,0,0.4) 0px, rgba(0,0,0,0.4) 0.6px, transparent 0.6px, transparent 5px)",
              ].join(", "),
            }}
          />
          <div
            className="absolute inset-0 pointer-events-none z-20 rounded-[18px] mix-blend-screen opacity-55"
            aria-hidden
            style={{
              backgroundImage: [
                "repeating-linear-gradient(45deg, transparent 0.6px, rgba(255,255,255,0.45) 0.6px, rgba(255,255,255,0.45) 1.4px, transparent 1.4px, transparent 5px)",
                "repeating-linear-gradient(-45deg, transparent 0.6px, rgba(255,255,255,0.45) 0.6px, rgba(255,255,255,0.45) 1.4px, transparent 1.4px, transparent 5px)",
              ].join(", "),
            }}
          />

          {/* Default-cover foreground — mascot + set name. Renders
              ONLY when there's no uploaded image. Placed above the
              quilted texture (z-25 > z-20) so the material stitching
              stays on the shell and doesn't crawl over the mascot. */}
          {!coverImageUrl && (
            <div className="absolute inset-0 z-[25] flex flex-col items-center justify-center pointer-events-none">
              <div className="relative h-40 w-40 mb-4 opacity-95">
                <Image
                  src="/pullist-mascot.png"
                  alt="Mascot"
                  fill
                  className="object-contain drop-shadow-[0_4px_12px_rgba(0,0,0,0.5)]"
                  sizes="160px"
                  unoptimized
                />
              </div>
              <div className="text-center px-6">
                <div className="text-[10px] font-semibold uppercase tracking-[0.3em] text-white/60 mb-2">
                  Master Set
                </div>
                <div className="text-white text-2xl font-bold tracking-tight drop-shadow-md">
                  {setName}
                </div>
              </div>
            </div>
          )}

          {/* Stitching — always on top of whatever cover art is showing.
              Two layers: a dark shadow underneath + light thread on top
              so the dashes read on both bright and dim covers (matches
              LO's Sylveon reference). CSS dashed border gives the
              stitch cadence; z-30 keeps it above the image + weave. */}
          <div
            className="absolute inset-[10px] rounded-[12px] pointer-events-none z-30"
            style={{
              border: "2px dashed rgba(0,0,0,0.4)",
              transform: "translate(0.6px, 0.6px)",
            }}
            aria-hidden
          />
          <div
            className="absolute inset-[10px] rounded-[12px] pointer-events-none z-30"
            style={{ border: "2px dashed rgba(255,255,255,0.55)" }}
            aria-hidden
          />

          {/* hover hint */}
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full bg-white/95 text-black text-xs font-semibold px-4 py-1.5 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-40">
            Tap to open
          </div>
        </motion.div>
      </div>

      {/* Cover management controls */}
      <div className="mt-4 flex items-center gap-2 flex-wrap justify-center">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onPickImage();
          }}
          disabled={uploadBusy}
          className="inline-flex items-center gap-1.5 rounded-full border border-border bg-bg-surface px-4 py-2 text-xs font-semibold text-text-primary hover:border-accent-yellow/50 disabled:opacity-50"
        >
          {uploadBusy ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <ImageIcon className="h-3.5 w-3.5" />
          )}
          {coverImageUrl ? "Replace cover" : "Upload cover"}
        </button>
        {coverImageUrl && onClearCover && (
          <button
            type="button"
            onClick={async (e) => {
              e.stopPropagation();
              if (!confirm("Remove custom cover?")) return;
              setClearing(true);
              try {
                await onClearCover();
              } finally {
                setClearing(false);
              }
            }}
            disabled={clearing || uploadBusy}
            className="inline-flex items-center gap-1.5 rounded-full border border-border bg-bg-surface px-4 py-2 text-xs font-semibold text-text-secondary hover:text-accent-red hover:border-accent-red/40 disabled:opacity-50"
          >
            {clearing ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Trash2 className="h-3.5 w-3.5" />
            )}
            Remove
          </button>
        )}
      </div>
      <p className="mt-2 text-[10px] uppercase tracking-wider text-text-tertiary">
        Tap the binder to open · custom cover resized locally
      </p>
    </div>
  );
}

/**
 * The rotating page. Snapshots outgoing + destination content as props
 * so the parent can swap its static spread mid-flip without disturbing
 * what this component is rendering. Independent motion.div children
 * animate a subtle self-shadow so the page catches light through the
 * arc — the arc looks flat without it.
 */
function FlippingSheet({
  direction,
  gridSize,
  outgoingLeft,
  outgoingRight,
  outgoingLeftPage,
  outgoingRightPage,
  destinationLeft,
  destinationRight,
  destinationLeftPage,
  destinationRightPage,
}: {
  direction: 1 | -1;
  gridSize: BinderSize;
  outgoingLeft: (BinderSlot | null)[];
  outgoingRight: (BinderSlot | null)[];
  outgoingLeftPage: number;
  outgoingRightPage: number;
  destinationLeft: (BinderSlot | null)[];
  destinationRight: (BinderSlot | null)[];
  destinationLeftPage: number;
  destinationRightPage: number;
}) {
  const frontSlots = direction === 1 ? outgoingRight : outgoingLeft;
  const frontPage = direction === 1 ? outgoingRightPage : outgoingLeftPage;
  const backSlots = direction === 1 ? destinationLeft : destinationRight;
  const backPage = direction === 1 ? destinationLeftPage : destinationRightPage;

  return (
    <motion.div
      className="absolute top-0 h-full w-1/2 z-30 pointer-events-none"
      style={{
        left: direction === 1 ? "50%" : "0%",
        transformOrigin: direction === 1 ? "left center" : "right center",
        transformStyle: "preserve-3d",
      }}
      initial={{ rotateY: 0 }}
      animate={{ rotateY: direction === 1 ? -180 : 180 }}
      transition={{ duration: 0.9, ease: [0.65, 0, 0.35, 1] }}
    >
      {/* Front face — the outgoing page catches less light as it
          rotates away, so we crossfade a black overlay from 0 → ~0.55
          over the first half of the arc. */}
      <div
        className="absolute inset-0"
        style={{
          backfaceVisibility: "hidden",
          WebkitBackfaceVisibility: "hidden",
        }}
      >
        <PageBase
          slots={frontSlots}
          pageNumber={frontPage}
          gridSize={gridSize}
          side={direction === 1 ? "right" : "left"}
          floating
        />
        <motion.div
          className="absolute inset-0 bg-black pointer-events-none rounded-[10px]"
          initial={{ opacity: 0 }}
          animate={{ opacity: [0, 0.55] }}
          transition={{ duration: 0.45, ease: "easeIn" }}
          aria-hidden
        />
      </div>
      {/* Back face — the incoming page starts shadowed and clears to
          nothing as it lands. Rotated 180° so it reads right-way-up. */}
      <div
        className="absolute inset-0"
        style={{
          backfaceVisibility: "hidden",
          WebkitBackfaceVisibility: "hidden",
          transform: "rotateY(180deg)",
        }}
      >
        <PageBase
          slots={backSlots}
          pageNumber={backPage}
          gridSize={gridSize}
          side={direction === 1 ? "left" : "right"}
          floating
        />
        <motion.div
          className="absolute inset-0 bg-black pointer-events-none rounded-[10px]"
          initial={{ opacity: 0.55 }}
          animate={{ opacity: [0.55, 0] }}
          transition={{
            duration: 0.45,
            delay: 0.45,
            ease: "easeOut",
          }}
          aria-hidden
        />
      </div>
    </motion.div>
  );
}

function EdgeButton({
  side,
  onClick,
  disabled,
  label,
}: {
  side: "left" | "right";
  onClick: () => void;
  disabled: boolean;
  label: string;
}) {
  const isLeft = side === "left";
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      className={
        "group absolute top-[8%] bottom-[8%] w-[12%] z-40 flex items-center justify-center cursor-pointer disabled:cursor-default " +
        (isLeft ? "left-0" : "right-0")
      }
    >
      <span
        className={
          "absolute inset-y-0 w-full transition-opacity opacity-0 group-hover:opacity-100 group-disabled:opacity-0 " +
          (isLeft
            ? "left-0 bg-gradient-to-r from-black/25 to-transparent"
            : "right-0 bg-gradient-to-l from-black/25 to-transparent")
        }
      />
      <span className="relative flex h-9 w-9 items-center justify-center rounded-full bg-white/90 text-black shadow-md opacity-0 group-hover:opacity-100 group-disabled:opacity-0 transition-opacity">
        {isLeft ? (
          <ChevronLeft className="h-5 w-5" />
        ) : (
          <ChevronRight className="h-5 w-5" />
        )}
      </span>
    </button>
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
  const positionClass = floating ? "absolute inset-0" : "flex-1 h-full";
  return (
    <div
      className={
        "flex flex-col p-[3.5%] " +
        positionClass +
        " " +
        (isLeft ? "rounded-l-[10px]" : "rounded-r-[10px]")
      }
      style={{
        // Perforated ballistic-nylon interior — two offset radial-gradient
        // dot layers over a near-black base gives the fine mesh weave you
        // see on real card-binder inner pages. Second layer is dimmer +
        // half-step offset so the pattern reads as woven, not gridded.
        backgroundColor: "#0a0a0a",
        backgroundImage: [
          "radial-gradient(rgba(255,255,255,0.075) 0.6px, transparent 1.3px)",
          "radial-gradient(rgba(255,255,255,0.04) 0.5px, transparent 1.1px)",
          "linear-gradient(160deg, rgba(255,255,255,0.02) 0%, transparent 100%)",
        ].join(", "),
        backgroundSize: "6px 6px, 6px 6px, 100% 100%",
        backgroundPosition: "0 0, 3px 3px, 0 0",
        boxShadow: floating
          ? "0 25px 45px -12px rgba(0,0,0,0.55)"
          : undefined,
      }}
    >
      <div
        className={
          "absolute top-3 text-[9px] font-bold text-white/40 tracking-[0.25em] uppercase pointer-events-none " +
          (isLeft ? "left-5" : "right-5")
        }
      >
        Page {pageNumber}
      </div>

      {/* Gutter shadow near the spine — deeper black falling into the
          center crease so it reads as a fold, not a seam. */}
      <div
        className={
          "pointer-events-none absolute top-0 bottom-0 w-8 " +
          (isLeft
            ? "right-0 bg-gradient-to-l from-black/70 to-transparent"
            : "left-0 bg-gradient-to-r from-black/70 to-transparent")
        }
        aria-hidden
      />

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
        // Near-black pocket base so cards pop against it, with a
        // darker inset shadow for the recessed sleeve feel and a
        // 1px lifted highlight at the bottom.
        backgroundColor: "#0e0e0e",
        boxShadow:
          "inset 0 2px 4px rgba(0,0,0,0.7), inset 0 -1px 0 rgba(255,255,255,0.04)",
      }}
    >
      {/* Plastic-sleeve gloss — lower intensity so it reads as a
          subtle sheen on black plastic instead of a milky wash. */}
      <div
        className="pointer-events-none absolute inset-0 z-10 opacity-60"
        style={{
          background:
            "linear-gradient(135deg, rgba(255,255,255,0.35) 0%, rgba(255,255,255,0) 45%, rgba(255,255,255,0) 100%)",
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

  return (
    <Link
      href={`/cards/${slot.card_id}`}
      title={`${slot.name}${slot.owned ? " · owned" : ""}`}
      className="absolute inset-0 block"
    >
      <div
        className={
          "relative w-full h-full transition-[filter,opacity] duration-500 " +
          (slot.owned ? "" : "grayscale opacity-40")
        }
      >
        {slot.image_small ? (
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
    </Link>
  );
}

function EmptyPocketMark() {
  return (
    <div className="absolute inset-1 flex items-center justify-center rounded-sm border border-dashed border-white/10">
      <span className="text-white/25 text-sm" aria-hidden>
        +
      </span>
    </div>
  );
}

/**
 * Zipper strip along one edge of the outer shell. Horizontal strips
 * (top/bottom) leave a 6% margin on each end so the vertical strips
 * (left/right) can meet them at the corners without overlapping their
 * teeth. Fabric-tape edges + a chromed-teeth center bar; three layers
 * total, all CSS.
 */
function ZipperStrip({
  orientation,
  edge,
}: {
  orientation: "horizontal" | "vertical";
  edge: "top" | "bottom" | "left" | "right";
}) {
  const horizontal = orientation === "horizontal";

  // Container placement per edge.
  const containerStyle: React.CSSProperties = horizontal
    ? {
        left: "6%",
        right: "6%",
        height: "11px",
        top: edge === "top" ? "1px" : undefined,
        bottom: edge === "bottom" ? "1px" : undefined,
      }
    : {
        top: "3%",
        bottom: "3%",
        width: "11px",
        left: edge === "left" ? "1px" : undefined,
        right: edge === "right" ? "1px" : undefined,
      };

  // Teeth pattern rotates 90° for vertical strips so they interlock
  // along the axis instead of across it.
  const teethBackground = horizontal
    ? "repeating-linear-gradient(90deg, #c8c8c8 0px, #c8c8c8 2px, #7a7a7a 2px, #7a7a7a 3px, #4a4a4a 3px, #4a4a4a 4px)"
    : "repeating-linear-gradient(180deg, #c8c8c8 0px, #c8c8c8 2px, #7a7a7a 2px, #7a7a7a 3px, #4a4a4a 3px, #4a4a4a 4px)";

  return (
    <div
      className={horizontal ? "absolute flex flex-col pointer-events-none" : "absolute flex flex-row pointer-events-none"}
      style={containerStyle}
      aria-hidden
    >
      {/* Outer fabric tape (side facing the edge of the binder) */}
      <div
        className={horizontal ? "h-[3px]" : "w-[3px]"}
        style={{
          background: horizontal
            ? "linear-gradient(180deg, #1a1a1a 0%, #0f0f0f 100%)"
            : "linear-gradient(90deg, #1a1a1a 0%, #0f0f0f 100%)",
          boxShadow: horizontal
            ? "inset 0 1px 1px rgba(255,255,255,0.06)"
            : "inset 1px 0 1px rgba(255,255,255,0.06)",
        }}
      />
      {/* Metal teeth */}
      <div
        className={horizontal ? "h-[5px]" : "w-[5px]"}
        style={{
          backgroundImage: teethBackground,
          boxShadow: horizontal
            ? "inset 0 1px 1px rgba(255,255,255,0.25), inset 0 -1px 1px rgba(0,0,0,0.6), 0 1px 1px rgba(0,0,0,0.4)"
            : "inset 1px 0 1px rgba(255,255,255,0.25), inset -1px 0 1px rgba(0,0,0,0.6), 1px 0 1px rgba(0,0,0,0.4)",
        }}
      />
      {/* Inner fabric tape (side facing the pages) */}
      <div
        className={horizontal ? "h-[3px]" : "w-[3px]"}
        style={{
          background: horizontal
            ? "linear-gradient(180deg, #0f0f0f 0%, #1a1a1a 100%)"
            : "linear-gradient(90deg, #0f0f0f 0%, #1a1a1a 100%)",
          boxShadow: horizontal
            ? "inset 0 -1px 1px rgba(255,255,255,0.06)"
            : "inset -1px 0 1px rgba(255,255,255,0.06)",
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
