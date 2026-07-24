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
export type BadgeRect = { top: string; left: string; right: string; height: string };

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
  badgeOverride?: BadgeRect;
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
    /** Card info well — year/set + card name lives here (pink outline
     *  in debug). No longer contains the grade badge. */
    flip: FlipRect;
    card: CardRect;
    /** Shared PullList mascot emblem overlay position. */
    emblem: EmblemRect;
    /** Grade + service badge well — its own absolute rect so it can be
     *  positioned independently of the card info well (orange outline
     *  in debug). Default drops it into the right side of the current
     *  flip footprint so out-of-the-box it looks familiar. */
    badge: BadgeRect;
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
    badge: { top: "7%", left: "70%", right: "9.5%", height: "12%" },
    flipTone: "on-gold",
  },
  psa: {
    src: "/slab-frame-psa.png",
    aspectRatio: "816 / 1285",
    flip: { top: "4%", left: "10%", right: "11%", height: "14%" },
    card: { top: "20%", left: "1.5%", right: "2.5%", bottom: "2%" },
    emblem: { bottom: "3%", left: "3%", width: "12%" },
    badge: { top: "4%", left: "76%", right: "11%", height: "14%" },
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
    badge: { top: "7%", left: "76%", right: "11%", height: "14.5%" },
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

// Real grader logo lockups shipped under /public/graders/. Consumers
// (e.g. the caption row under a rendered slab on /portfolio/slabs)
// import this map to render "[LOGO] · Gem Mint" style captions. The
// slab badge itself renders just the grade number now — the grader
// identity lives on the caption line instead so it can be actually
// visible at a size users can read.
export const SERVICE_LOGO: Record<GradeService, string> = {
  PSA: "/graders/psa.png",
  BGS: "/graders/bgs.svg",
  CGC: "/graders/cgc.svg",
  TAG: "/graders/tag.png",
};

// Per-grader caption pill background. BGS's official Beckett SVG is
// solid #1C1B1E dark text on transparent — it becomes invisible on
// the dark theme, so a light pill wraps it. TAG carries a black
// rectangle already; PSA/CGC render on their own opaque brand chrome
// so they stay bare.
export const SERVICE_LOGO_PILL_CLASS: Record<GradeService, string> = {
  PSA: "",
  BGS: "bg-white rounded px-1.5",
  CGC: "",
  TAG: "",
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
  badgeOverride,
  cardInsetPct = 0,
}: SlabProps) {
  const meta = FRAME_META[style];
  const flipRect = flipOverride ?? meta.flip;
  const cardRect = cardOverride ?? meta.card;
  const emblemRect = emblemOverride ?? meta.emblem;
  const badgeRect = badgeOverride ?? meta.badge;
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
      {/* Card info well — year/set + card name.
          Standalone rect (pink debug outline). Card name wraps to 2
          lines via -webkit-line-clamp so long names like "Mega
          Charizard ex" don't truncate mid-word. */}
      <div
        className="absolute flex flex-col justify-center gap-0.5 rounded-sm px-1.5 py-1"
        style={{
          top: flipRect.top,
          left: flipRect.left,
          right: flipRect.right,
          height: flipRect.height,
          zIndex: 3,
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
            fontFamily: "var(--font-noto-sans), system-ui, sans-serif",
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

      {/* Grade badge — own rect (orange debug outline). Displays JUST
          the grade number now, centered. Service identity + suffix
          moved to the slab's external caption so the badge stays
          crisp and readable at any size. Grade digit fills the rect
          via a fluid font-size so a bigger badge = bigger number. */}
      <div
        className="absolute flex items-center justify-center rounded-sm overflow-hidden"
        style={{
          top: badgeRect.top,
          left: badgeRect.left,
          right: badgeRect.right,
          height: badgeRect.height,
          zIndex: 3,
          background: "#101013",
          color: accent,
          boxShadow: `inset 0 0 0 1.5px ${accent}, 0 0 6px -3px ${accent}`,
        }}
      >
        <span
          className="font-bold leading-none tabular-nums"
          style={{
            color: accent,
            fontFamily: "var(--font-noto-sans), system-ui, sans-serif",
            letterSpacing: "-0.02em",
            fontSize: "clamp(18px, 5vw, 42px)",
          }}
        >
          {grade}
        </span>
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
          <div
            aria-hidden
            className="absolute pointer-events-none"
            style={{
              top: badgeRect.top,
              left: badgeRect.left,
              right: badgeRect.right,
              height: badgeRect.height,
              border: "1px dashed rgba(255, 165, 0, 0.9)",
              zIndex: 10,
            }}
          />
        </>
      )}
    </div>
  );
}
