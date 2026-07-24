"use client";

/**
 * SlabFrame — renders a graded slab using one of the AI-generated frame
 * PNGs sitting in /public. The frame is a static asset; everything the
 * user actually cares about (card art, grade badge, card name) is CSS
 * overlaid on top at percentage coordinates relative to the frame.
 *
 * Two styles for now:
 *   - "bgs"  → slab-frame-bgs.png (dark textured frame, gold flip well)
 *   - "psa"  → slab-frame-psa.png (clear acrylic, red-border white flip)
 *
 * Coordinates below are eyeballed from the source PNGs. Tune on live
 * preview — open /portfolio/slabs-preview, inspect the debug outline
 * (Cmd+click any slab to toggle), adjust percentages until badge/card
 * sit flush inside the physical wells.
 */

import Image from "next/image";

type SlabStyle = "bgs" | "psa" | "clean";

type GradeService = "PSA" | "BGS" | "CGC" | "TAG";

export type FlipRect = { top: string; left: string; right: string; height: string };
export type CardRect = { top: string; left: string; right: string; bottom: string };
export type EmblemRect = { bottom: string; left: string; width: string };

export type SlabProps = {
  style?: SlabStyle;
  cardName: string;
  cardImage?: string | null;
  yearSet: string; // "2024 Mega Evolution · #125"
  number?: string;
  service: GradeService;
  grade: string; // "10", "9.5", "10 BL", "10 Pristine"
  suffix?: string; // "Gem Mint", "Pristine", "Black Label"
  /** BGS-only subgrades (Cen / Cor / Edg / Sur) */
  subgrades?: [number, number, number, number];
  /** Toggle to render dashed outlines over flip well + card well —
   *  useful when tuning the coordinate percentages. */
  debug?: boolean;
  /** Live-tuning overrides — when passed, these WIN over FRAME_META
   *  defaults. The slabs-preview page wires sliders to these so the
   *  layout can be tuned without an edit-commit-deploy loop. */
  flipOverride?: FlipRect;
  cardOverride?: CardRect;
  emblemOverride?: EmblemRect;
  /** Extra breathing room around the card image WITHIN the card well,
   *  as a % of the well's shorter side. 0 = card fills well edge-to-
   *  edge (default); 5 = card shrinks 5% on each side, revealing a
   *  frame of the underlying slab acrylic. Useful when the well
   *  rectangle is a bit larger than a real card outline so cards
   *  don't spill onto the plastic. */
  cardInsetPct?: number;
};

// Frame-specific overlay coordinates. All values are % of the frame
// image dimensions so they scale with any container width. Tune here
// (or via debug outlines) to match the physical wells in each PNG.
export const FRAME_META: Record<
  SlabStyle,
  {
    src: string;
    aspectRatio: string;
    flip: FlipRect;
    card: CardRect;
    /** Shared PullList mascot emblem overlay position — sits in the
     *  bottom-left "manufacturer mark" corner across all three styles. */
    emblem: EmblemRect;
    /** Text tone on the flip label — the flip is gold on BGS, red-
     *  bordered white on PSA, black on the minimal Clean frame. */
    flipTone: "on-gold" | "on-white" | "on-black";
  }
> = {
  bgs: {
    src: "/slab-frame-bgs.png",
    aspectRatio: "797 / 1344",
    flip: { top: "7%", left: "24%", right: "9.5%", height: "12%" },
    card: { top: "22%", left: "3.5%", right: "5%", bottom: "8.5%" },
    emblem: { bottom: "3%", left: "3%", width: "12%" },
    flipTone: "on-gold",
  },
  psa: {
    src: "/slab-frame-psa.png",
    aspectRatio: "816 / 1285",
    flip: { top: "4%", left: "10%", right: "11%", height: "14%" },
    card: { top: "20%", left: "1.5%", right: "2.5%", bottom: "2%" },
    emblem: { bottom: "3%", left: "3%", width: "12%" },
    flipTone: "on-white",
  },
  clean: {
    // Third frame — minimal transparent acrylic with black wells. Flip
    // well sits top-left as a compact rectangle; card well fills most
    // of the interior. Both wells have dark backgrounds so the flip
    // text needs light-on-dark tone rendering.
    src: "/slab-frame-clean.png",
    aspectRatio: "5 / 8",
    flip: { top: "7%", left: "12.5%", right: "11%", height: "14.5%" },
    card: { top: "22%", left: "5%", right: "5%", bottom: "3%" },
    emblem: { bottom: "3%", left: "3%", width: "12%" },
    flipTone: "on-black",
  },
};

// Emblem inversion — PSA slab keeps the original black silhouette
// (reads well on the cream-colored PSA flip and clear acrylic body);
// BGS + Clean have darker slab tones so we invert to white via CSS
// filter. The source PNG stays one file — the invert happens per
// render based on the active style.
const EMBLEM_INVERT: Record<SlabStyle, boolean> = {
  bgs: true,
  psa: false,
  clean: true,
};

// Grader accent — badge outline + perfect-10 halo tint.
const SERVICE_ACCENT: Record<GradeService, string> = {
  PSA: "#c8102e",
  BGS: "#c9a94a",
  CGC: "#17b8b6",
  TAG: "#e0447a",
};

export function SlabFrame({
  style = "bgs",
  cardName,
  cardImage,
  yearSet,
  service,
  grade,
  suffix,
  subgrades,
  debug = false,
  flipOverride,
  cardOverride,
  emblemOverride,
  cardInsetPct = 0,
}: SlabProps) {
  const meta = FRAME_META[style];
  const flipRect = flipOverride ?? meta.flip;
  const cardRect = cardOverride ?? meta.card;
  const emblemRect = emblemOverride ?? meta.emblem;
  const cardPadding = `${cardInsetPct}%`;
  const accent = SERVICE_ACCENT[service];
  const isPerfect10 = grade.trim().startsWith("10");
  const flipTextColor =
    meta.flipTone === "on-black" ? "#f0eee6" : "#1a1a1a";
  const flipMutedColor =
    meta.flipTone === "on-black"
      ? "#9a9790"
      : meta.flipTone === "on-gold"
      ? "#4a3f20"
      : "#6a5f4a";

  return (
    <div
      className="relative w-full select-none"
      style={{ aspectRatio: meta.aspectRatio }}
    >
      {/* Perfect-10 halo — sits behind the frame, radiates in accent */}
      {isPerfect10 && (
        <div
          aria-hidden
          className="absolute pointer-events-none"
          style={{
            inset: "-6%",
            background: `radial-gradient(ellipse at 50% 0%, ${accent} 0%, transparent 55%)`,
            opacity: 0.18,
            filter: "blur(14px)",
            zIndex: 0,
          }}
        />
      )}

      {/* Static frame PNG */}
      <Image
        src={meta.src}
        alt=""
        fill
        priority
        sizes="(max-width: 640px) 100vw, 320px"
        className="object-contain pointer-events-none select-none"
        style={{ zIndex: 1 }}
      />

      {/* Card image sits INSIDE the card well.
          - Outer container positions to cardRect and applies the
            optional cardInsetPct % padding on all sides — this shrinks
            the effective card area inward without moving the well.
          - Inner wrapper carries the border-radius + overflow:hidden
            so the img gets clipped to a rounded rectangle (matching
            real TCG cards) INSIDE the padded area. */}
      {cardImage && (
        <div
          className="absolute"
          style={{
            top: cardRect.top,
            left: cardRect.left,
            right: cardRect.right,
            bottom: cardRect.bottom,
            zIndex: 2,
            padding: cardPadding,
          }}
        >
          <div
            className="relative w-full h-full overflow-hidden"
            style={{
              // Real TCG cards round at ~4-5% of their width. Using %
              // keeps the profile constant across display sizes; fixed
              // px would flatten small and over-round large.
              borderRadius: "3.5%",
            }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={cardImage}
              alt={cardName}
              className="w-full h-full object-cover"
              style={{
                boxShadow: "inset 0 0 0 1px rgba(0,0,0,0.15)",
              }}
            />
          </div>
        </div>
      )}

      {/* Flip label overlay — year/set + grade badge */}
      {/* Flip content — two visually distinct boxes side by side inside
          the flip well:
          - LEFT: card info box (year/set + card name, card name wraps
            to 2 lines if too long — no more mid-name truncation like
            "MEGA CHARIZA…").
          - RIGHT: grade+service badge box with its own background/
            border so it reads as a separate "certification stamp".
          Both are noticeably larger than the previous inline row —
          the flip well is wide enough to afford the extra bulk. */}
      <div
        className="absolute flex items-stretch gap-1.5 p-1"
        style={{
          top: flipRect.top,
          left: flipRect.left,
          right: flipRect.right,
          height: flipRect.height,
          zIndex: 3,
        }}
      >
        <div
          className="flex-1 min-w-0 flex flex-col justify-center gap-0.5 px-1.5 py-1 rounded-sm"
          style={{
            background:
              meta.flipTone === "on-black"
                ? "rgba(20, 20, 24, 0.55)"
                : meta.flipTone === "on-gold"
                ? "rgba(255, 250, 235, 0.35)"
                : "rgba(255, 255, 255, 0.6)",
            boxShadow: "inset 0 0 0 0.5px rgba(0,0,0,0.08)",
          }}
        >
          <span
            className="font-mono text-[7.5px] uppercase tracking-[0.1em] truncate leading-none"
            style={{ color: flipMutedColor }}
          >
            {yearSet}
          </span>
          <span
            className="font-bold text-[11px] uppercase leading-tight overflow-hidden"
            style={{
              color: flipTextColor,
              fontFamily: "'Bodoni Moda', Georgia, serif",
              letterSpacing: "-0.005em",
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              wordBreak: "break-word",
            }}
          >
            {cardName}
          </span>
        </div>
        <div
          className="flex flex-col items-center justify-center rounded-sm shrink-0 px-2"
          style={{
            background: "#101013",
            color: accent,
            boxShadow: `inset 0 0 0 1.5px ${accent}, 0 0 6px -3px ${accent}`,
            minWidth: "38px",
            padding: "3px 8px 4px",
          }}
        >
          <span
            className="font-bold text-[7px] tracking-[0.2em] leading-none"
            style={{ color: accent }}
          >
            {service}
          </span>
          <span
            className="font-bold text-[17px] leading-none tabular-nums"
            style={{
              color: accent,
              fontFamily: "'Bodoni Moda', Georgia, serif",
              letterSpacing: "-0.02em",
              marginTop: "2px",
            }}
          >
            {grade}
          </span>
          {suffix && (
            <span
              className="text-[6px] tracking-[0.14em] uppercase leading-none opacity-85"
              style={{ color: accent, marginTop: "2px" }}
            >
              {suffix}
            </span>
          )}
        </div>
      </div>

      {/* BGS subgrades intentionally NOT rendered inside the slab
          visual — neither frame PNG has a natural slot for them, so
          overlaying spills messily over the card art. The 9.5 badge
          already communicates the tier; full subgrade breakdown lives
          in the item detail modal / row hover. The `subgrades` prop
          stays part of the API so we can wire it up if a future
          BGS-specific frame gains a dedicated subgrade strip. */}

      {/* Brand emblem — PullList mascot silhouette in the bottom-left
          "manufacturer mark" corner. Single source PNG (solid black
          silhouette on transparent); per-style CSS filter flips it to
          white on the darker frames (BGS textured / Clean black wells)
          while PSA keeps the original black on its cream+clear body. */}
      <div
        className="absolute pointer-events-none"
        style={{
          bottom: emblemRect.bottom,
          left: emblemRect.left,
          width: emblemRect.width,
          aspectRatio: "1 / 1",
          zIndex: 4,
          filter: EMBLEM_INVERT[style] ? "invert(1)" : "none",
        }}
      >
        <Image
          src="/slab-emblem.png"
          alt=""
          fill
          sizes="80px"
          style={{ objectFit: "contain" }}
        />
      </div>

      {/* Debug overlays — dashed outlines around wells for coordinate tuning */}
      {debug && (
        <>
          <div
            aria-hidden
            className="absolute pointer-events-none"
            style={{
              top: flipRect.top,
              left: flipRect.left,
              right: flipRect.right,
              height: flipRect.height,
              border: "1px dashed rgba(255, 0, 128, 0.9)",
              zIndex: 10,
            }}
          />
          <div
            aria-hidden
            className="absolute pointer-events-none"
            style={{
              top: cardRect.top,
              left: cardRect.left,
              right: cardRect.right,
              bottom: cardRect.bottom,
              border: "1px dashed rgba(0, 200, 255, 0.9)",
              zIndex: 10,
            }}
          />
          <div
            aria-hidden
            className="absolute pointer-events-none"
            style={{
              bottom: emblemRect.bottom,
              left: emblemRect.left,
              width: emblemRect.width,
              aspectRatio: "1 / 1",
              border: "1px dashed rgba(180, 255, 100, 0.9)",
              zIndex: 10,
            }}
          />
        </>
      )}
    </div>
  );
}
