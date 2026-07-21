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

type SlabStyle = "bgs" | "psa";

type GradeService = "PSA" | "BGS" | "CGC" | "TAG";

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
};

// Frame-specific overlay coordinates. All values are % of the frame
// image dimensions so they scale with any container width. Tune here
// (or via debug outlines) to match the physical wells in each PNG.
const FRAME_META: Record<
  SlabStyle,
  {
    src: string;
    aspectRatio: string;
    flip: { top: string; left: string; right: string; height: string };
    card: { top: string; left: string; right: string; bottom: string };
    /** Text tone on the flip label — the flip is gold on BGS, red-
     *  bordered white on PSA, so contrast direction flips. */
    flipTone: "on-gold" | "on-white";
  }
> = {
  bgs: {
    src: "/slab-frame-bgs.png",
    aspectRatio: "797 / 1344",
    flip: { top: "3.5%", left: "20%", right: "17%", height: "12%" },
    card: { top: "24%", left: "13.5%", right: "13.5%", bottom: "10%" },
    flipTone: "on-gold",
  },
  psa: {
    src: "/slab-frame-psa.png",
    aspectRatio: "816 / 1285",
    flip: { top: "4.5%", left: "6%", right: "38%", height: "13%" },
    card: { top: "24%", left: "11%", right: "11%", bottom: "5%" },
    flipTone: "on-white",
  },
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
}: SlabProps) {
  const meta = FRAME_META[style];
  const accent = SERVICE_ACCENT[service];
  const isPerfect10 = grade.trim().startsWith("10");
  const flipTextColor = meta.flipTone === "on-gold" ? "#1a1a1a" : "#1a1a1a";
  const flipMutedColor = meta.flipTone === "on-gold" ? "#4a3f20" : "#6a5f4a";

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

      {/* Card image sits INSIDE the card well */}
      {cardImage && (
        <div
          className="absolute overflow-hidden"
          style={{
            top: meta.card.top,
            left: meta.card.left,
            right: meta.card.right,
            bottom: meta.card.bottom,
            zIndex: 2,
            borderRadius: "4px",
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
      )}

      {/* Flip label overlay — year/set + grade badge */}
      <div
        className="absolute flex items-center gap-2 px-2"
        style={{
          top: meta.flip.top,
          left: meta.flip.left,
          right: meta.flip.right,
          height: meta.flip.height,
          zIndex: 3,
        }}
      >
        <div className="flex flex-col justify-center min-w-0 flex-1">
          <span
            className="font-mono text-[7px] uppercase tracking-[0.12em] truncate leading-tight"
            style={{ color: flipMutedColor }}
          >
            {yearSet}
          </span>
          <span
            className="font-bold text-[10px] uppercase truncate leading-tight"
            style={{
              color: flipTextColor,
              fontFamily: "'Bodoni Moda', Georgia, serif",
              letterSpacing: "-0.005em",
            }}
          >
            {cardName}
          </span>
        </div>
        <div
          className="flex flex-col items-center justify-center px-1.5 rounded-sm shrink-0"
          style={{
            background: "#101013",
            color: accent,
            boxShadow: `inset 0 0 0 1px ${accent}, 0 0 6px -3px ${accent}`,
            minWidth: "32px",
            padding: "1px 6px 2px",
          }}
        >
          <span
            className="font-bold text-[6px] tracking-[0.18em] leading-none"
            style={{ color: accent }}
          >
            {service}
          </span>
          <span
            className="font-bold text-[15px] leading-none tabular-nums"
            style={{
              color: accent,
              fontFamily: "'Bodoni Moda', Georgia, serif",
              letterSpacing: "-0.02em",
              marginTop: "1px",
            }}
          >
            {grade}
          </span>
          {suffix && (
            <span
              className="text-[5px] tracking-[0.14em] uppercase leading-none opacity-80"
              style={{ color: accent, marginTop: "1px" }}
            >
              {suffix}
            </span>
          )}
        </div>
      </div>

      {/* BGS subgrades — small strip below flip label */}
      {subgrades && (
        <div
          className="absolute grid grid-cols-4"
          style={{
            top: `calc(${meta.flip.top} + ${meta.flip.height} + 1%)`,
            left: meta.flip.left,
            right: meta.flip.right,
            height: "5%",
            zIndex: 3,
          }}
        >
          {(["Cen", "Cor", "Edg", "Sur"] as const).map((label, i) => (
            <div
              key={label}
              className="flex flex-col items-center justify-center leading-none"
            >
              <span
                className="font-mono text-[5px] uppercase tracking-[0.1em]"
                style={{ color: flipMutedColor }}
              >
                {label}
              </span>
              <span
                className="font-bold text-[8px] tabular-nums"
                style={{
                  color: flipTextColor,
                  fontFamily: "'Bodoni Moda', Georgia, serif",
                }}
              >
                {subgrades[i]}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Debug overlays — dashed outlines around wells for coordinate tuning */}
      {debug && (
        <>
          <div
            aria-hidden
            className="absolute pointer-events-none"
            style={{
              top: meta.flip.top,
              left: meta.flip.left,
              right: meta.flip.right,
              height: meta.flip.height,
              border: "1px dashed rgba(255, 0, 128, 0.9)",
              zIndex: 10,
            }}
          />
          <div
            aria-hidden
            className="absolute pointer-events-none"
            style={{
              top: meta.card.top,
              left: meta.card.left,
              right: meta.card.right,
              bottom: meta.card.bottom,
              border: "1px dashed rgba(0, 200, 255, 0.9)",
              zIndex: 10,
            }}
          />
        </>
      )}
    </div>
  );
}
