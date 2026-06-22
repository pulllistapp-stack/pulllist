"use client";

import Image from "next/image";
import { useEffect, useState } from "react";

/**
 * Centred mascot + rotating status phrase. Replaces blank skeletons on
 * full-page loads so the wait reads as personality rather than dead air.
 *
 * Four animated APNG variants:
 *   - idle: sitting + blinking + holding card (default for in-page data)
 *   - fly:  flying diagonally + wings flapping (route transitions)
 *   - pack: opening a booster pack (trending/drops — fresh-data vibes)
 *   - sleep: lying curled with floating z's (long-running work, big lists)
 *
 * The APNGs carry their own per-frame motion, so we deliberately skip the
 * CSS bounce keyframe — stacking the two looks twitchy.
 */

const PHRASES = [
  "Counting your pulls...",
  "Calling the trainer...",
  "Checking the prices...",
];

const ROTATION_MS = 2400;

type Size = "sm" | "md" | "lg";
type Variant = "idle" | "fly" | "pack" | "sleep";

const SIZE_CFG: Record<Size, { px: number; text: string }> = {
  sm: { px: 56, text: "text-xs" },
  md: { px: 96, text: "text-sm" },
  lg: { px: 144, text: "text-base" },
};

const VARIANT_SRC: Record<Variant, string> = {
  idle: "/pullist-mascot.png",
  fly: "/pullist-mascot-fly.png",
  pack: "/pullist-mascot-pack.png",
  sleep: "/pullist-mascot-sleep.png",
};

export function MascotLoader({
  size = "md",
  variant = "idle",
  className = "",
}: {
  size?: Size;
  variant?: Variant;
  className?: string;
}) {
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setIdx((p) => (p + 1) % PHRASES.length);
    }, ROTATION_MS);
    return () => clearInterval(id);
  }, []);

  const cfg = SIZE_CFG[size];

  return (
    <div
      className={`flex flex-col items-center justify-center gap-3 py-8 ${className}`}
      role="status"
      aria-live="polite"
    >
      <div
        className="relative"
        style={{ width: cfg.px, height: cfg.px }}
      >
        <Image
          src={VARIANT_SRC[variant]}
          alt=""
          fill
          sizes={`${cfg.px}px`}
          className="object-contain drop-shadow-lg"
          priority
          unoptimized
        />
      </div>
      <p
        key={idx}
        className={`${cfg.text} text-text-secondary font-medium animate-mascot-fade tabular-nums`}
      >
        {PHRASES[idx]}
      </p>
    </div>
  );
}
